"""Create boats and passages.

Revision ID: 0001
Revises:
Create Date: 2026-11-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "boats",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("max_wind_kn", sa.Float, nullable=False),
        sa.Column("max_gust_kn", sa.Float, nullable=True),
        sa.Column("max_wave_m", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "passages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("boat_id", sa.Integer, sa.ForeignKey("boats.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("start_lat", sa.Float, nullable=False),
        sa.Column("start_lon", sa.Float, nullable=False),
        sa.Column("end_lat", sa.Float, nullable=False),
        sa.Column("end_lon", sa.Float, nullable=False),
        sa.Column("speed_kn", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_passages_boat_id", "passages", ["boat_id"])


def downgrade() -> None:
    op.drop_index("ix_passages_boat_id", table_name="passages")
    op.drop_table("passages")
    op.drop_table("boats")
