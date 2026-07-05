"""Add documents.visibility for household sharing.

Revision ID: 0002_visibility
Revises: 0001_initial
Create Date: 2026-07-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_visibility'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New documents default to 'household' (shared with the household). Existing
    # rows also become household-visible, matching the shared-vault intent.
    op.add_column(
        'documents',
        sa.Column('visibility', sa.String(16), nullable=False, server_default='household'),
    )
    op.create_index('ix_documents_visibility', 'documents', ['visibility'])


def downgrade() -> None:
    op.drop_index('ix_documents_visibility', table_name='documents')
    op.drop_column('documents', 'visibility')
