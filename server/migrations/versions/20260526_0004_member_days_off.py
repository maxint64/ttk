"""restore member days off

Revision ID: 20260526_0004
Revises: 20260526_0003
Create Date: 2026-05-26 00:00:02.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260526_0004"
down_revision = "20260526_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS member_days_off (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            off_on TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
            UNIQUE (activity_id, member_id, off_on)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS member_days_off")
