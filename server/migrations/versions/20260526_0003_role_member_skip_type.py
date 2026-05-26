"""add role member skip type

Revision ID: 20260526_0003
Revises: 20260525_0002
Create Date: 2026-05-26 00:00:01.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260526_0003"
down_revision = "20260525_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE role_member_skips
        ADD COLUMN skip_type TEXT NOT NULL DEFAULT 'once'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE role_member_skips_old (
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
    op.execute(
        """
        INSERT INTO role_member_skips_old
            (id, activity_id, role_id, member_id, created_at)
        SELECT id, activity_id, role_id, member_id, created_at
        FROM role_member_skips
        """
    )
    op.execute("DROP TABLE role_member_skips")
    op.execute("ALTER TABLE role_member_skips_old RENAME TO role_member_skips")
