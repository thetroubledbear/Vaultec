from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    database_url: str
    vault_blob_dir: str = "/vault/blobs"
    vault_tmp_dir: str = "/vault/tmp"
    vault_incoming_dir: str = "/vault/incoming"
    app_env: str = "dev"
    session_cookie_name: str = "vaultec_session"

    # --- AI features (OCR + embeddings + RAG) ---
    # Master switch. When false, the processing worker stays idle and the AI
    # endpoints return 503. OCR/extraction still never leave the box.
    ai_enabled: bool = True

    # Provider selection. Each is independent so you can, e.g., embed locally
    # but answer with a cloud model (or vice-versa).
    #   embed_provider: "ollama" (local, default) | "openai"
    #   chat_provider:  "ollama" (local, default) | "anthropic"
    # SECURITY: any non-local provider sends document text off the box. This
    # deliberately breaks ARCHITECTURE principle #4 — opt in per install.
    embed_provider: str = "ollama"
    chat_provider: str = "ollama"

    # Vector dimension the embeddings column is sized for. nomic-embed-text=768,
    # OpenAI text-embedding-3-small=1536. The column is dimensionless in the DB
    # (exact cosine search, fine at household scale), so this is only used to
    # sanity-check vectors before insert. Change requires a re-embed.
    embed_dim: int = 768

    # Local (Ollama) — reachable over the compose network.
    ollama_url: str = "http://ollama:11434"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_chat_model: str = "qwen2.5:3b"

    # Cloud (opt-in). Keys empty unless the provider is selected.
    anthropic_api_key: str = ""
    anthropic_chat_model: str = "claude-opus-4-8"
    openai_api_key: str = ""
    openai_embed_model: str = "text-embedding-3-small"
    openai_base_url: str = "https://api.openai.com/v1"

    # Chunking (characters — rough proxy for ~500 tokens).
    chunk_chars: int = 2000
    chunk_overlap: int = 200
    # Retrieval-augmented generation: how many chunks to feed the model.
    rag_top_k: int = 6

    class Config:
        env_file = ".env"
        case_sensitive = False

    @field_validator("database_url")
    @classmethod
    def _force_psycopg3_driver(cls, v: str) -> str:
        """Ensure SQLAlchemy uses the installed psycopg v3 driver, not psycopg2.

        A bare ``postgresql://`` URL makes SQLAlchemy default to psycopg2, which
        is not installed. Rewrite it to the explicit psycopg (v3) dialect.
        """
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v


@lru_cache()
def get_settings() -> Settings:
    """Cached settings factory."""
    return Settings()
