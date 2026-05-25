"""initial schema

Revision ID: 20260525_0001
Revises:
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260525_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            UNIQUE (activity_id, name)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            UNIQUE (activity_id, email)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS role_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            assigned_on TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
            UNIQUE (activity_id, role_id, member_id, assigned_on)
        )
        """
    )
    _add_members_email_if_missing()
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS roles_activity_name_unique
        ON roles (activity_id, name)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS members_activity_email_unique
        ON members (activity_id, email)
        WHERE email IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS members_activity_email_unique")
    op.execute("DROP INDEX IF EXISTS roles_activity_name_unique")
    op.execute("DROP TABLE IF EXISTS role_assignments")
    op.execute("DROP TABLE IF EXISTS members")
    op.execute("DROP TABLE IF EXISTS roles")
    op.execute("DROP TABLE IF EXISTS activities")


def _add_members_email_if_missing() -> None:
    connection = op.get_bind()
    columns = {
        row[1]
        for row in connection.exec_driver_sql("PRAGMA table_info(members)").fetchall()
    }
    if "email" not in columns:
        op.execute("ALTER TABLE members ADD COLUMN email TEXT")
