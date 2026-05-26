"""add member day off type

Revision ID: 20260526_0005
Revises: 20260526_0004
Create Date: 2026-05-26 00:00:03.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260526_0005"
down_revision = "20260526_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE member_days_off
        ADD COLUMN day_off_type TEXT NOT NULL DEFAULT 'once'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE member_days_off_old (
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
    op.execute(
        """
        INSERT INTO member_days_off_old
            (id, activity_id, member_id, off_on, created_at)
        SELECT id, activity_id, member_id, off_on, created_at
        FROM member_days_off
        """
    )
    op.execute("DROP TABLE member_days_off")
    op.execute("ALTER TABLE member_days_off_old RENAME TO member_days_off")
