"""Add matches.sheet_row for idempotent Google Sheet imports

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("matches", sa.Column("sheet_row", sa.Integer(), nullable=True))
    op.create_index("ix_matches_sheet_row", "matches", ["sheet_row"], unique=True)


def downgrade():
    op.drop_index("ix_matches_sheet_row", table_name="matches")
    op.drop_column("matches", "sheet_row")
