"""jetons et tentatives de reinitialisation de mot de passe

Revision ID: c0adab96238c
Revises: e6d2026091501
Create Date: 2026-09-17 10:37:12.571314

Meme schema que `refresh_token` pour `password_reset_token` : seule l'empreinte SHA-256 du
jeton est stockee, jamais le jeton lui-meme, pour la meme raison (revocation en cascade,
aucune session utilisable dans un pg_dump qui fuiterait).

`password_reset_attempt` vit hors de `audit_log`, comme `login_attempt`, car son volume est
pilote par l'attaquant : une campagne de demandes y ecrirait des lignes que l'audit, en ajout
seul, ne devrait jamais purger.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c0adab96238c"
down_revision: str | Sequence[str] | None = "e6d2026091501"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JETONS_VIVANTS = "consumed_at is null"


def upgrade() -> None:
    op.create_table(
        "password_reset_attempt",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("email_tried", sa.String(length=320), nullable=False),
        sa.Column("client_ip", postgresql.INET(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_attempt"),
    )
    op.create_index(
        "ix_password_reset_attempt_email_date",
        "password_reset_attempt",
        ["email_tried", "occurred_at"],
    )
    op.create_index(
        "ix_password_reset_attempt_ip_date", "password_reset_attempt", ["client_ip", "occurred_at"]
    )

    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name="fk_password_reset_token_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_token"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_token_hash"),
    )
    op.create_index("ix_password_reset_token_user", "password_reset_token", ["user_id"])
    op.create_index(
        "ix_password_reset_token_vivants",
        "password_reset_token",
        ["user_id"],
        postgresql_where=JETONS_VIVANTS,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_token_vivants",
        table_name="password_reset_token",
        postgresql_where=JETONS_VIVANTS,
    )
    op.drop_index("ix_password_reset_token_user", table_name="password_reset_token")
    op.drop_table("password_reset_token")
    op.drop_index("ix_password_reset_attempt_ip_date", table_name="password_reset_attempt")
    op.drop_index("ix_password_reset_attempt_email_date", table_name="password_reset_attempt")
    op.drop_table("password_reset_attempt")
