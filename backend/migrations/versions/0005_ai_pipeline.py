"""AI pipeline: rebuild embeddings for chunked/dimensionless vectors,
extend extractions with FTS + language, add hybrid-search indexes.

Revision ID: 0002_ai_pipeline
Revises: 0001_initial
Create Date: 2026-07-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


revision = "0005_ai_pipeline"
down_revision = "0004_households"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- extractions: language + char count + full-text search vector ---
    op.add_column("extractions", sa.Column("lang", sa.String(16), nullable=True))
    op.add_column("extractions", sa.Column("char_count", sa.Integer(), nullable=True))
    op.create_index("ix_extractions_document_id", "extractions", ["document_id"])

    # Generated tsvector column for keyword search, kept in sync automatically.
    op.execute(
        "ALTER TABLE extractions ADD COLUMN tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', coalesce(extracted_text, ''))) STORED"
    )
    op.execute("CREATE INDEX ix_extractions_tsv ON extractions USING gin (tsv)")

    # --- embeddings: rebuild for per-chunk, dimensionless vectors ---
    # The 0001 table had a fixed vector(1536) and no chunk columns and holds no
    # rows yet, so a clean rebuild is simplest.
    op.drop_table("embeddings")
    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("vector", Vector(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["extraction_id"], ["extractions.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
    )
    op.create_index("ix_embeddings_extraction_id", "embeddings", ["extraction_id"])
    op.create_index("ix_embeddings_document_id", "embeddings", ["document_id"])


def downgrade() -> None:
    op.drop_table("embeddings")
    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vector", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["extraction_id"], ["extractions.id"]),
    )
    op.execute("DROP INDEX IF EXISTS ix_extractions_tsv")
    op.execute("ALTER TABLE extractions DROP COLUMN IF EXISTS tsv")
    op.drop_index("ix_extractions_document_id", table_name="extractions")
    op.drop_column("extractions", "char_count")
    op.drop_column("extractions", "lang")
