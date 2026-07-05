"""Add documents.status for scan validation workflow.

Revision ID: 0003_document_status
Revises: 0002_visibility
Create Date: 2026-07-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_document_status'
down_revision = '0002_visibility'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add status column: 'active' (normal) | 'pending' (awaiting validation from scan)
    # Manual uploads are active; scanned docs start pending until validated.
    op.add_column(
        'documents',
        sa.Column('status', sa.String(16), nullable=False, server_default='active'),
    )
    op.create_index('ix_documents_status', 'documents', ['status'])


def downgrade() -> None:
    op.drop_index('ix_documents_status', table_name='documents')
    op.drop_column('documents', 'status')
