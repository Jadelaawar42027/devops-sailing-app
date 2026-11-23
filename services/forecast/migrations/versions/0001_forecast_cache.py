"""Create forecast_cache.

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
        "forecast_cache",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cache_key", sa.String(100), nullable=False),
        sa.Column("payload", sa.UnicodeText, nullable=False),
        sa.Column("fetched_at", sa.DateTime, nullable=False),
    )
    op.create_index("ux_forecast_cache_key", "forecast_cache", ["cache_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_forecast_cache_key", table_name="forecast_cache")
    op.drop_table("forecast_cache")
