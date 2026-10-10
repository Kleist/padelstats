"""Initial schema: players, matches, match_sets

Revision ID: 0001
Revises:
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("played_on", sa.Date(), nullable=False, index=True),
        sa.Column("venue", sa.String(20), nullable=False),
        sa.Column("a1_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("a2_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("b1_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("b2_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "match_sets",
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("set_no", sa.Integer(), primary_key=True),
        sa.Column("games_a", sa.Integer(), nullable=False),
        sa.Column("games_b", sa.Integer(), nullable=False),
        sa.CheckConstraint("games_a >= 0 AND games_a <= 7", name="games_a_range"),
        sa.CheckConstraint("games_b >= 0 AND games_b <= 7", name="games_b_range"),
    )


def downgrade():
    op.drop_table("match_sets")
    op.drop_table("matches")
    op.drop_table("players")
