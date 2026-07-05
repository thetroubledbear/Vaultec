"""Search, ask (RAG), reprocessing, and provider status routes."""

import logging
from typing import List, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import ai, pipeline, crypto
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user, require_unlocked
from app.models import User, Document, Extraction, Embedding

logger = logging.getLogger("vaultec")
router = APIRouter()


class ProviderStatusResponse(BaseModel):
    """AI provider status response."""

    embed_provider: str
    embed_model: str
    chat_provider: str
    chat_model: str
    anthropic_key_set: bool
    openai_key_set: bool
    active_docs: int
    docs_with_extraction: int
    docs_with_embeddings: int
    pending_docs: int


class SearchResult(BaseModel):
    """Single search result."""

    document_id: str
    title: str
    snippet: str
    score: float
    match: str  # "keyword" | "semantic" | "both"


class SearchResponse(BaseModel):
    """Search results response."""

    results: List[SearchResult]


class AskRequest(BaseModel):
    """Ask (RAG) request."""

    question: str


class AskResponse(BaseModel):
    """Ask (RAG) response."""

    answer: str
    sources: List[dict]  # [{document_id, title, snippet}]


class ReprocessResponse(BaseModel):
    """Reprocess response."""

    status: str
    chunks: int = 0


def _can_view_doc(doc: Document, current_user: User) -> bool:
    """Check if user can view this document."""
    if current_user.role == "admin":
        return True
    if doc.household_id is None:
        return False
    return doc.household_id == current_user.household_id


def _can_edit_doc(doc: Document, current_user: User) -> bool:
    """Check if user can edit/reprocess this document."""
    if current_user.role == "admin":
        return True
    return doc.owner_id == current_user.id


def _get_visible_doc_filter(current_user: User) -> sa.sql.expression.BinaryExpression:
    """Return a SQLAlchemy filter for documents visible to the user."""
    if current_user.role == "admin":
        return Document.status == "active"
    else:
        return sa.and_(
            Document.status == "active",
            Document.household_id == current_user.household_id,
        )


@router.get("/status", response_model=ProviderStatusResponse)
def status_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderStatusResponse:
    """
    Get AI provider status and document processing counts.

    Returns configured providers, models, API key status (booleans only),
    and counts of visible documents by processing state.

    Args:
        current_user: authenticated user
        db: database session

    Returns:
        ProviderStatusResponse with provider info and counts
    """
    settings = get_settings()
    status_dict = ai.provider_status()

    # Count visible docs
    visible_filter = _get_visible_doc_filter(current_user)

    active_docs = db.query(Document).filter(visible_filter).count()

    docs_with_extraction = (
        db.query(Document)
        .join(Extraction)
        .filter(visible_filter)
        .distinct()
        .count()
    )

    docs_with_embeddings = (
        db.query(Document)
        .join(Extraction)
        .join(Embedding)
        .filter(visible_filter)
        .distinct()
        .count()
    )

    pending_docs = (
        db.query(Document)
        .filter(visible_filter)
        .outerjoin(Extraction)
        .filter(Extraction.id == None)
        .count()
    )

    return ProviderStatusResponse(
        embed_provider=status_dict["embed_provider"],
        embed_model=status_dict["embed_model"],
        chat_provider=status_dict["chat_provider"],
        chat_model=status_dict["chat_model"],
        anthropic_key_set=status_dict["anthropic_key_set"],
        openai_key_set=status_dict["openai_key_set"],
        active_docs=active_docs,
        docs_with_extraction=docs_with_extraction,
        docs_with_embeddings=docs_with_embeddings,
        pending_docs=pending_docs,
    )


@router.get("/search", response_model=SearchResponse)
async def search_endpoint(
    q: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Hybrid search: keyword (FTS) + semantic (vector).

    Performs both full-text search and semantic search over visible documents,
    merges results by document_id, and ranks by score. If semantic search fails
    (provider down), gracefully degrades to keyword-only.

    Args:
        q: search query
        limit: max results (default 10)
        current_user: authenticated user
        db: database session

    Returns:
        SearchResponse with merged results ranked by score
    """
    settings = get_settings()
    visible_filter = _get_visible_doc_filter(current_user)

    keyword_results = {}  # {doc_id: (title, snippet, score)}
    semantic_results = {}  # {doc_id: (title, snippet, score)}

    try:
        # Keyword search: FTS over extraction text
        tsquery = sa.func.plainto_tsquery("english", q)
        headline_func = sa.func.ts_headline(
            "english",
            Extraction.extracted_text,
            tsquery,
            "MaxWords=30, MinWords=15",
        )

        keyword_query = (
            db.query(
                Document.id,
                Document.title,
                headline_func.label("snippet"),
                sa.func.ts_rank(
                    sa.literal_column("extractions.tsv"),
                    tsquery,
                ).label("score"),
            )
            .join(Extraction)
            .filter(visible_filter)
            # Only rows that actually match the query. Uses the generated,
            # GIN-indexed tsv column — without this every extraction comes back
            # with rank 0. plainto_tsquery("") is empty and matches nothing.
            .filter(sa.literal_column("extractions.tsv").op("@@")(tsquery))
            .order_by(sa.desc("score"))
            .limit(limit * 2)
        )

        for doc_id, title, snippet, score in keyword_query:
            snippet = snippet or ""
            keyword_results[doc_id] = (title, snippet, float(score))

    except Exception as e:
        logger.warning(f"Keyword search failed: {e}")

    try:
        # Semantic search: vector similarity
        if not settings.ai_enabled:
            logger.info("AI disabled; skipping semantic search")
        else:
            query_vecs = await ai.embed_texts([q])
            if query_vecs:
                query_vec = query_vecs[0]

                semantic_query = (
                    db.query(
                        Document.id,
                        Document.title,
                        Embedding.chunk_text.label("snippet"),
                        (1.0 - Embedding.vector.cosine_distance(query_vec)).label("score"),
                    )
                    .join(Extraction)
                    .join(Embedding)
                    .join(Document)
                    .filter(visible_filter)
                    .order_by(sa.desc("score"))
                    .limit(limit * 2)
                )

                for doc_id, title, snippet, score in semantic_query:
                    snippet = snippet or ""
                    semantic_results[doc_id] = (title, snippet, float(score))

    except Exception as e:
        logger.warning(f"Semantic search failed (degrading to keyword-only): {e}")

    # Merge results
    merged = {}
    for doc_id, (title, snippet, score) in keyword_results.items():
        merged[doc_id] = {
            "title": title,
            "snippet": snippet,
            "score": score,
            "match": "keyword",
        }

    for doc_id, (title, snippet, score) in semantic_results.items():
        if doc_id in merged:
            # Keep best score, update match type
            if score > merged[doc_id]["score"]:
                merged[doc_id]["score"] = score
                merged[doc_id]["snippet"] = snippet
            merged[doc_id]["match"] = "both"
        else:
            merged[doc_id] = {
                "title": title,
                "snippet": snippet,
                "score": score,
                "match": "semantic",
            }

    # Sort by score, cap at limit
    results = sorted(
        [
            SearchResult(
                document_id=str(doc_id),
                title=data["title"],
                snippet=data["snippet"],
                score=data["score"],
                match=data["match"],
            )
            for doc_id, data in merged.items()
        ],
        key=lambda r: r.score,
        reverse=True,
    )[:limit]

    return SearchResponse(results=results)


@router.post("/ask", response_model=AskResponse)
async def ask_endpoint(
    req: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AskResponse:
    """
    Answer a question using RAG (retrieval-augmented generation).

    Embeds the question, retrieves top-k chunks from visible documents,
    constructs a context, and sends to the configured chat provider.

    Args:
        req: AskRequest with question
        current_user: authenticated user
        db: database session

    Returns:
        AskResponse with answer and source documents

    Raises:
        HTTPException 503: if AI is disabled or embedding/chat fails
    """
    settings = get_settings()

    if not settings.ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI features disabled",
        )

    try:
        visible_filter = _get_visible_doc_filter(current_user)

        # Embed question
        try:
            question_vecs = await ai.embed_texts([req.question])
            if not question_vecs:
                raise RuntimeError("No embeddings returned")
            query_vec = question_vecs[0]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Embedding failed: {e}",
            ) from e

        # Retrieve top-k chunks
        retrieval_query = (
            db.query(
                Embedding.chunk_text,
                Document.id,
                Document.title,
                (1.0 - Embedding.vector.cosine_distance(query_vec)).label("score"),
            )
            .join(Document)
            .filter(visible_filter)
            .order_by(sa.desc("score"))
            .limit(settings.rag_top_k)
            .all()
        )

        if not retrieval_query:
            # No embeddings found
            answer = (
                "I don't have any indexed documents to search. "
                "Please process some documents first."
            )
            return AskResponse(answer=answer, sources=[])

        # Build context with numbered chunks
        context_lines = []
        sources = {}  # {doc_id: {title, snippet}}

        for i, (chunk_text, doc_id, doc_title, score) in enumerate(retrieval_query, 1):
            context_lines.append(f"[{i}] ({doc_title})\n{chunk_text}")
            if doc_id not in sources:
                sources[doc_id] = {
                    "document_id": str(doc_id),
                    "title": doc_title,
                    "snippet": chunk_text[:200],  # First 200 chars
                }

        context = "\n\n".join(context_lines)

        # System prompt
        system_prompt = (
            "You are a helpful assistant. Answer questions ONLY using the provided context. "
            "Cite your sources by their [n] numbers. "
            "If the answer is not in the context, say 'I don't know' or 'This information is not available.'"
        )

        # Call chat provider
        try:
            answer = await ai.chat(
                system=system_prompt,
                user=f"Context:\n{context}\n\nQuestion: {req.question}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Chat provider failed: {e}",
            ) from e

        return AskResponse(answer=answer, sources=list(sources.values()))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ask endpoint error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider unavailable",
        )


@router.post("/reprocess/{doc_id}", response_model=ReprocessResponse)
async def reprocess_endpoint(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_unlocked),
    db: Session = Depends(get_db),
) -> ReprocessResponse:
    """
    Reprocess a document: extract text, chunk, and embed (synchronously).

    Requires the vault be unlocked. Restricts to document owner or admin.
    Deletes existing extraction and embeddings (idempotent).

    Args:
        doc_id: UUID of document to reprocess
        current_user: authenticated user
        db: database session

    Returns:
        ReprocessResponse with status and chunk count

    Raises:
        HTTPException 404: if document not found
        HTTPException 403: if user cannot edit this document
        HTTPException 423: if vault is locked
        HTTPException 503: if processing fails
    """
    try:
        # Load and check permissions
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        if not _can_edit_doc(doc, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot reprocess this document",
            )

        # Process (inline)
        try:
            await pipeline.process_document(doc_id)
        except Exception as e:
            logger.exception(f"Reprocess failed for {doc_id}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Processing failed: {e}",
            ) from e

        # Return chunk count
        extraction = db.query(Extraction).filter(
            Extraction.document_id == doc_id
        ).first()
        chunk_count = 0
        if extraction:
            chunk_count = (
                db.query(Embedding).filter(
                    Embedding.extraction_id == extraction.id
                ).count()
            )

        return ReprocessResponse(status="done", chunks=chunk_count)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Reprocess endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error",
        )
