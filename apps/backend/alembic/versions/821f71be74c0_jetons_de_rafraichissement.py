"""jetons de rafraichissement

Revision ID: 821f71be74c0
Revises: 517053a3c044
Create Date: 2026-09-15 14:42:09.757949

Le jeton lui-meme n'est jamais stocke : seule son empreinte SHA-256 l'est, dans
`token_hash`. Un pg_dump qui fuiterait ne livrerait donc aucune session utilisable.

L'index partiel `ix_refresh_token_vivants` sert la revocation en cascade et la
recherche des sessions actives, qui ne regardent jamais les lignes deja tournees.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "821f71be74c0"
down_revision: str | Sequence[str] | None = "517053a3c044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MOTIFS = "'logout', 'rotation', 'reuse_detected', 'password_change', 'admin'"
JETONS_VIVANTS = "revoked_at is null and rotated_at is null"


def upgrade() -> None:
    op.create_table(
        "refresh_token",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("replaced_by", sa.UUID(), nullable=True),
        sa.Column("client_ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"revoked_reason is null or revoked_reason in ({MOTIFS})",
            name="ck_refresh_token_revoked_reason",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name="fk_refresh_token_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_token"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
    )
    op.create_index("ix_refresh_token_family", "refresh_token", ["family_id"])
    op.create_index("ix_refresh_token_user", "refresh_token", ["user_id"])
    op.create_index(
        "ix_refresh_token_vivants",
        "refresh_token",
        ["user_id"],
        postgresql_where=JETONS_VIVANTS,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_refresh_token_vivants", table_name="refresh_token", postgresql_where=JETONS_VIVANTS
    )
    op.drop_index("ix_refresh_token_user", table_name="refresh_token")
    op.drop_index("ix_refresh_token_family", table_name="refresh_token")
    op.drop_table("refresh_token")
