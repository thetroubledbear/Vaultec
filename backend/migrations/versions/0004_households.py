"""Add households table and migrate from per-document visibility to household-based access.

Revision ID: 0004_households
Revises: 0003_document_status
Create Date: 2026-07-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '0004_households'
down_revision = '0003_document_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create households table
    op.create_table(
        'households',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Add household_id to users
    op.add_column(
        'users',
        sa.Column('household_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_users_household_id',
        'users',
        'households',
        ['household_id'],
        ['id'],
    )
    op.create_index('ix_users_household_id', 'users', ['household_id'])

    # Add household_id to documents
    op.add_column(
        'documents',
        sa.Column('household_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_documents_household_id',
        'documents',
        'households',
        ['household_id'],
        ['id'],
    )
    op.create_index('ix_documents_household_id', 'documents', ['household_id'])

    # Data migration: create default household
    connection = op.get_bind()
    default_hid = str(uuid.uuid4())

    # Insert default household
    connection.execute(
        sa.text(
            "INSERT INTO households (id, name, created_at) VALUES (:id, :name, NOW())"
        ),
        {"id": default_hid, "name": "Home"}
    )

    # Assign all users to default household
    connection.execute(
        sa.text("UPDATE users SET household_id = :hid"),
        {"hid": default_hid}
    )

    # Assign all documents to the owner's household
    connection.execute(
        sa.text(
            "UPDATE documents SET household_id = (SELECT household_id FROM users WHERE users.id = documents.owner_id)"
        )
    )

    # Drop visibility index if it exists, then drop visibility column
    try:
        op.drop_index('ix_documents_visibility', table_name='documents')
    except Exception:
        pass
    op.drop_column('documents', 'visibility')


def downgrade() -> None:
    # Re-add visibility column with default 'household'
    op.add_column(
        'documents',
        sa.Column('visibility', sa.String(16), nullable=False, server_default='household'),
    )
    op.create_index('ix_documents_visibility', 'documents', ['visibility'])

    # Drop documents.household_id
    op.drop_constraint('fk_documents_household_id', 'documents', type_='foreignkey')
    op.drop_index('ix_documents_household_id', table_name='documents')
    op.drop_column('documents', 'household_id')

    # Drop users.household_id
    op.drop_constraint('fk_users_household_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_household_id', table_name='users')
    op.drop_column('users', 'household_id')

    # Drop households table
    op.drop_table('households')
