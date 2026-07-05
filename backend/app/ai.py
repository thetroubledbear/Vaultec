"""Provider abstraction for embeddings and chat + local OCR extraction."""

import asyncio
import base64
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger("vaultec")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using configured provider.

    Dispatches on settings.embed_provider ("ollama" or "openai").
    - Ollama: POST to {ollama_url}/api/embeddings with one prompt per request.
    - OpenAI: POST to {openai_base_url}/embeddings with all texts in a single request.

    Args:
        texts: list of text strings to embed

    Returns:
        list of embedding vectors (each is a list of floats)

    Raises:
        RuntimeError: if provider key/config is missing or request fails
    """
    settings = get_settings()

    if settings.embed_provider == "ollama":
        return await _embed_ollama(texts, settings)
    elif settings.embed_provider == "openai":
        return await _embed_openai(texts, settings)
    else:
        raise RuntimeError(f"Unknown embed_provider: {settings.embed_provider}")


async def _embed_ollama(texts: list[str], settings) -> list[list[float]]:
    """Embed texts using Ollama API."""
    embeddings = []
    timeout = httpx.Timeout(120.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        for text in texts:
            try:
                resp = await client.post(
                    f"{settings.ollama_url}/api/embeddings",
                    json={"model": settings.ollama_embed_model, "prompt": text},
                )
                resp.raise_for_status()
                embeddings.append(resp.json()["embedding"])
            except Exception as e:
                raise RuntimeError(f"Ollama embeddings request failed: {e}") from e

    return embeddings


async def _embed_openai(texts: list[str], settings) -> list[list[float]]:
    """Embed texts using OpenAI-compatible API."""
    if not settings.openai_api_key:
        raise RuntimeError("openai_api_key not configured")

    timeout = httpx.Timeout(120.0)
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.openai_base_url}/embeddings",
                headers=headers,
                json={"model": settings.openai_embed_model, "input": texts},
            )
            resp.raise_for_status()
            return [d["embedding"] for d in resp.json()["data"]]
    except Exception as e:
        raise RuntimeError(f"OpenAI embeddings request failed: {e}") from e


async def chat(system: str, user: str) -> str:
    """
    Generate a chat response using configured provider.

    Dispatches on settings.chat_provider ("ollama" or "anthropic").
    - Ollama: POST to {ollama_url}/api/chat (streaming disabled).
    - Anthropic: use AsyncAnthropic SDK with adaptive thinking (Opus 4.8 feature).

    Args:
        system: system prompt
        user: user message

    Returns:
        model response text

    Raises:
        RuntimeError: if provider key/config is missing or request fails
    """
    settings = get_settings()

    if settings.chat_provider == "ollama":
        return await _chat_ollama(system, user, settings)
    elif settings.chat_provider == "anthropic":
        return await _chat_anthropic(system, user, settings)
    else:
        raise RuntimeError(f"Unknown chat_provider: {settings.chat_provider}")


async def _chat_ollama(system: str, user: str, settings) -> str:
    """Chat using Ollama API."""
    timeout = httpx.Timeout(120.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/chat",
                json={
                    "model": settings.ollama_chat_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Ollama chat request failed: {e}") from e


async def _chat_anthropic(system: str, user: str, settings) -> str:
    """Chat using Anthropic SDK with adaptive thinking."""
    if not settings.anthropic_api_key:
        raise RuntimeError("anthropic_api_key not configured")

    try:
        import anthropic
        import anyio

        async_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await async_client.messages.create(
            model=settings.anthropic_chat_model,
            max_tokens=1024,
            system=system,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": user}],
        )

        # Extract text blocks from response (exclude thinking blocks)
        text_parts = [
            block.text for block in resp.content if block.type == "text"
        ]
        return "".join(text_parts)
    except Exception as e:
        raise RuntimeError(f"Anthropic chat request failed: {e}") from e


def embedding_model_id() -> str:
    """
    Return a stable identifier for the embedding model.

    Used as Embedding.model column value so embeddings track which model
    generated them.

    Returns:
        string like "ollama:nomic-embed-text" or "openai:text-embedding-3-small"
    """
    settings = get_settings()
    if settings.embed_provider == "ollama":
        return f"ollama:{settings.ollama_embed_model}"
    elif settings.embed_provider == "openai":
        return f"openai:{settings.openai_embed_model}"
    else:
        return f"unknown:{settings.embed_provider}"


def provider_status() -> dict:
    """
    Return status dict describing configured AI providers.

    Contains provider names, models, and booleans indicating whether
    required API keys are present (never returns actual keys).

    Returns:
        dict with keys:
        - embed_provider: "ollama" | "openai"
        - embed_model: model name
        - chat_provider: "ollama" | "anthropic"
        - chat_model: model name
        - anthropic_key_set: bool
        - openai_key_set: bool
    """
    settings = get_settings()
    return {
        "embed_provider": settings.embed_provider,
        "embed_model": (
            settings.ollama_embed_model
            if settings.embed_provider == "ollama"
            else settings.openai_embed_model
        ),
        "chat_provider": settings.chat_provider,
        "chat_model": (
            settings.ollama_chat_model
            if settings.chat_provider == "ollama"
            else settings.anthropic_chat_model
        ),
        "anthropic_key_set": bool(settings.anthropic_api_key),
        "openai_key_set": bool(settings.openai_api_key),
    }


def extract_text(
    file_bytes: bytes, mimetype: str | None, filename: str
) -> tuple[str, str, str | None]:
    """
    Extract text from file bytes using local tools (no network calls).

    Supports:
    - Text/plaintext: UTF-8 decode
    - PDF: pdftotext (text layer), fallback to ocrmypdf for image-based PDFs
    - Images: tesseract OCR

    All temporary files written under settings.vault_tmp_dir are cleaned up
    in a finally block. On tool failure (missing binary, timeout), logs
    warning and returns empty text (not an error).

    Args:
        file_bytes: raw file content
        mimetype: MIME type string (may be None)
        filename: original filename (used for extension detection)

    Returns:
        tuple of (extracted_text, extractor_type, lang):
        - extracted_text: string (empty if unsupported or extraction failed)
        - extractor_type: "plaintext" | "pdftext" | "ocr" | "unsupported"
        - lang: "eng" (OCR/PDF) or None (plaintext)

    Raises:
        None (errors are logged; caller gets best-effort result)
    """
    settings = get_settings()
    tmp_files = []

    try:
        # Determine file type from mimetype or extension
        if mimetype and (mimetype.startswith("text/") or mimetype == "application/plain"):
            # Plain text
            try:
                text = file_bytes.decode("utf-8", errors="replace")
                return (text, "plaintext", None)
            except Exception as e:
                logger.warning(f"Failed to decode plaintext {filename}: {e}")
                return ("", "plaintext", None)

        # Check file extension as fallback
        filename_lower = (filename or "").lower()

        if filename_lower.endswith((".txt", ".md")):
            try:
                text = file_bytes.decode("utf-8", errors="replace")
                return (text, "plaintext", None)
            except Exception as e:
                logger.warning(f"Failed to decode plaintext {filename}: {e}")
                return ("", "plaintext", None)

        # PDF handling
        if (mimetype and mimetype == "application/pdf") or filename_lower.endswith(".pdf"):
            return _extract_pdf(file_bytes, filename, tmp_files, settings)

        # Image handling
        if mimetype and mimetype.startswith("image/"):
            return _extract_image(file_bytes, filename, tmp_files, settings)

        # Check common image extensions
        if any(
            filename_lower.endswith(ext)
            for ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]
        ):
            return _extract_image(file_bytes, filename, tmp_files, settings)

        # Unsupported
        return ("", "unsupported", None)

    finally:
        # Clean up temp files
        for tmp_file in tmp_files:
            try:
                os.unlink(tmp_file)
            except OSError:
                pass


def _extract_pdf(
    file_bytes: bytes, filename: str, tmp_files: list, settings
) -> tuple[str, str, str | None]:
    """Extract text from PDF: try pdftotext, fall back to OCR if needed."""
    # Write temp PDF
    tmp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=settings.vault_tmp_dir)
    tmp_pdf.write(file_bytes)
    tmp_pdf.close()
    tmp_files.append(tmp_pdf.name)

    try:
        # Try pdftotext
        try:
            result = subprocess.run(
                ["pdftotext", tmp_pdf.name, "-"],
                capture_output=True,
                timeout=120,
                text=True,
            )
            text = result.stdout.strip()

            # Check if we got meaningful text
            if len("".join(text.split())) >= 100:
                return (text, "pdftext", "eng")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"pdftotext not available or timed out: {e}")

        # Fallback to OCR
        logger.info(f"Falling back to OCR for {filename}")
        tmp_txt = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, dir=settings.vault_tmp_dir)
        tmp_txt.close()
        tmp_files.append(tmp_txt.name)

        tmp_out_pdf = tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, dir=settings.vault_tmp_dir
        )
        tmp_out_pdf.close()
        tmp_files.append(tmp_out_pdf.name)

        try:
            subprocess.run(
                [
                    "ocrmypdf",
                    "--force-ocr",
                    f"--sidecar={tmp_txt.name}",
                    f"--output-type=pdf",
                    tmp_pdf.name,
                    tmp_out_pdf.name,
                ],
                capture_output=True,
                timeout=120,
                check=False,
            )

            if os.path.exists(tmp_txt.name):
                with open(tmp_txt.name, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read().strip()
                return (text, "ocr", "eng")
            else:
                logger.warning(f"ocrmypdf did not produce sidecar for {filename}")
                return ("", "ocr", "eng")

        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"ocrmypdf not available or timed out: {e}")
            return ("", "ocr", "eng")

    except Exception as e:
        logger.warning(f"PDF extraction failed for {filename}: {e}")
        return ("", "pdftext", "eng")


def _extract_image(
    file_bytes: bytes, filename: str, tmp_files: list, settings
) -> tuple[str, str, str | None]:
    """Extract text from image using tesseract."""
    # Determine temp file extension from filename
    ext = Path(filename).suffix if filename else ".png"
    if not ext.startswith("."):
        ext = ".png"

    tmp_img = tempfile.NamedTemporaryFile(suffix=ext, delete=False, dir=settings.vault_tmp_dir)
    tmp_img.write(file_bytes)
    tmp_img.close()
    tmp_files.append(tmp_img.name)

    try:
        result = subprocess.run(
            ["tesseract", tmp_img.name, "stdout"],
            capture_output=True,
            timeout=120,
            text=True,
        )
        text = result.stdout.strip()
        return (text, "ocr", "eng")
    except FileNotFoundError:
        logger.warning("tesseract not available")
        return ("", "ocr", "eng")
    except subprocess.TimeoutExpired:
        logger.warning(f"tesseract timed out on {filename}")
        return ("", "ocr", "eng")
    except Exception as e:
        logger.warning(f"Image extraction failed for {filename}: {e}")
        return ("", "ocr", "eng")
