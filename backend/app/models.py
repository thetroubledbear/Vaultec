"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    LargeBinary,
    ForeignKey,
    Text,
    Table,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.db import Base


# Association table for document-tag many-to-many
document_tags = Table(
    "document_tags",
    Base.metadata,
    Column("document_id", UUID(as_uuid=True), ForeignKey("documents.id"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id"), primary_key=True),
)


class Household(Base):
    """Households (groups of users) table."""
    __tablename__ = "households"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    members = relationship("User", back_populates="household")


class User(Base):
    """Users table."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="member")  # admin | member | viewer
    is_active = Column(Boolean, default=True, nullable=False)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    household = relationship("Household", back_populates="members")
    sessions = relationship("Session", back_populates="user")
    documents = relationship("Document", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        Index("ix_users_username", "username"),
        Index("ix_users_email", "email"),
        Index("ix_users_household_id", "household_id"),
    )


class Session(Base):
    """User sessions table."""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )


class Document(Base):
    """Documents (metadata) table."""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=True)
    # 'active' = normal (manually uploaded); 'pending' = awaiting validation (from scan)
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="documents")
    category = relationship("Category", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=document_tags, back_populates="documents")
    extractions = relationship("Extraction", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_documents_owner_id", "owner_id"),
        Index("ix_documents_category_id", "category_id"),
        Index("ix_documents_household_id", "household_id"),
    )


class DocumentVersion(Base):
    """Document versions table."""
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    blob_id = Column(UUID(as_uuid=True), ForeignKey("blobs.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="versions")
    blob = relationship("Blob", back_populates="versions")

    __table_args__ = (
        Index("ix_document_versions_document_id", "document_id"),
        Index("ix_document_versions_blob_id", "blob_id"),
    )


class Blob(Base):
    """Encrypted blobs metadata table."""
    __tablename__ = "blobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    mimetype = Column(String(255))
    wrapped_dek = Column(String, nullable=False)  # base64-encoded wrapped DEK
    dek_nonce = Column(String, nullable=False)
    blob_nonce = Column(String, nullable=False)
    plaintext_sha256 = Column(String, nullable=False)  # base64-encoded SHA256
    size_bytes = Column(Integer)
    storage_path = Column(String(512), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    versions = relationship("DocumentVersion", back_populates="blob")

    __table_args__ = (
        Index("ix_blobs_storage_path", "storage_path"),
    )


class Category(Base):
    """Document categories table."""
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    documents = relationship("Document", back_populates="category")


class Tag(Base):
    """Tags table."""
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    documents = relationship("Document", secondary=document_tags, back_populates="tags")


class Extraction(Base):
    """Extracted text from documents table."""
    __tablename__ = "extractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    extractor_type = Column(String(255), nullable=False)  # e.g. 'ocr', 'pdftext', 'plaintext'
    extracted_text = Column(Text, nullable=False)
    lang = Column(String(16))  # detected/assumed language, e.g. 'eng'
    char_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="extractions")
    embeddings = relationship("Embedding", back_populates="extraction", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_extractions_document_id", "document_id"),
    )


class Embedding(Base):
    """Vector embeddings table.

    The vector column is dimensionless (``Vector`` with no fixed size) so the
    same table works for any embedding model (nomic 768, OpenAI 1536, ...).
    At household scale exact cosine search (seq scan with ``<=>``) is plenty; a
    fixed-dim ivfflat/hnsw index can be added later if the corpus grows large.
    """
    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("extractions.id"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    chunk_no = Column(Integer, nullable=False, default=0)
    chunk_text = Column(Text, nullable=False)
    model = Column(String(128), nullable=False)  # provider:model that produced this
    dim = Column(Integer, nullable=False)
    vector = Column(Vector, nullable=False)  # dimensionless — see class docstring
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    extraction = relationship("Extraction", back_populates="embeddings")

    __table_args__ = (
        Index("ix_embeddings_extraction_id", "extraction_id"),
        Index("ix_embeddings_document_id", "document_id"),
    )


class ValidationQueue(Base):
    """Validation queue for async document processing."""
    __tablename__ = "validation_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    task_type = Column(String(255), nullable=False)  # e.g. 'ocr', 'extract_metadata'
    status = Column(String(32), default="pending", nullable=False)  # pending, processing, done, failed
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_validation_queue_status", "status"),
        Index("ix_validation_queue_document_id", "document_id"),
    )


class AuditLog(Base):
    """Append-only audit log for security events."""
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    event_type = Column(String(255), nullable=False)  # e.g. 'login', 'document_access', 'export'
    resource_type = Column(String(255))  # e.g. 'document', 'blob'
    resource_id = Column(UUID(as_uuid=True))
    details = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(String(512))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="audit_logs")


class VaultConfig(Base):
    """Vault bootstrap and master key verification table."""
    __tablename__ = "vault_config"

    id = Column(Integer, primary_key=True, default=1)
    kdf_salt = Column(LargeBinary(16), nullable=False)
    kek_check_nonce = Column(LargeBinary(12), nullable=False)
    kek_check_ct = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
