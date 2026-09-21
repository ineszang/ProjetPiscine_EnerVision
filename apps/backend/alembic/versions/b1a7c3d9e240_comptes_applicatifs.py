"""comptes applicatifs

Revision ID: b1a7c3d9e240
Revises: 5353c0e4f094
Create Date: 2026-09-15 14:40:00.000000

Cree `app_user`, la table des comptes humains et de service. Le nom evite `user`,
mot reserve de PostgreSQL. `gen_random_uuid()` est au coeur de PG17, aucune
extension n'est necessaire.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1a7c3d9e240"
down_revision: str | Sequence[str] | None = "5353c0e4f094"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), server_default=sa.text("'human'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "credentials_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(email)", name="ck_app_user_email_minuscule"),
        sa.CheckConstraint(
            "role in ('lecteur', 'operateur', 'admin')", name="ck_app_user_role"
        ),
        sa.CheckConstraint("kind in ('human', 'service')", name="ck_app_user_kind"),
        sa.PrimaryKeyConstraint("id", name="pk_app_user"),
        sa.UniqueConstraint("email", name="uq_app_user_email"),
    )


def downgrade() -> None:
    op.drop_table("app_user")
