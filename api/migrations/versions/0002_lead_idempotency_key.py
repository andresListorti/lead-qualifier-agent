"""Add optional unique idempotency keys to leads."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("idempotency_key", sa.String(100), nullable=True))
    op.create_index("ix_leads_idempotency_key", "leads", ["idempotency_key"], unique=True)


def downgrade():
    op.drop_index("ix_leads_idempotency_key", table_name="leads")
    op.drop_column("leads", "idempotency_key")
