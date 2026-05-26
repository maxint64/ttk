"""member availability settings

Revision ID: 20260525_0002
Revises: 20260525_0001
Create Date: 2026-05-25 00:00:01.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260525_0002"
down_revision = "20260525_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS role_member_skips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
            UNIQUE (activity_id, role_id, member_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS role_member_skips")
