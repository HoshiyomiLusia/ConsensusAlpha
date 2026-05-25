"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-24
"""

from alembic import op

from app.storage.tables import Base

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
