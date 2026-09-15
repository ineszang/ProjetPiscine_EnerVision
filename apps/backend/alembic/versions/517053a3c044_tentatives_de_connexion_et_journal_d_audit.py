"""tentatives de connexion et journal d audit

Revision ID: 517053a3c044
Revises: b1a7c3d9e240
Create Date: 2026-09-15 14:31:07.966180

Deux tables aux vocations opposees. `login_attempt` est le compteur de la limitation
de debit : son volume est pilote par l'attaquant, donc elle se purge. `audit_log` est
en ajout seul, garanti par deux declencheurs.

Le declencheur TRUNCATE n'est pas redondant : TRUNCATE ne passe pas par les
declencheurs de ligne. Et RAISE EXCEPTION plutot qu'un RETURN NULL, qui annulerait
l'operation silencieusement.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "517053a3c044"
down_revision: str | Sequence[str] | None = "b1a7c3d9e240"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FONCTION_AJOUT_SEUL = """
CREATE FUNCTION audit_log_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log est en ajout seul : % interdit', TG_OP;
END
$$ LANGUAGE plpgsql;
"""

DECLENCHEUR_LIGNE = """
CREATE TRIGGER audit_log_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
"""

DECLENCHEUR_TRUNCATE = """
CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION audit_log_append_only();
"""


def upgrade() -> None:
    op.create_table(
        "login_attempt",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("email_tried", sa.String(length=320), nullable=False),
        sa.Column("client_ip", postgresql.INET(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "outcome in ('success', 'bad_credentials', 'throttled', 'inactive')",
            name="ck_login_attempt_outcome",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_login_attempt"),
    )
    op.create_index(
        "ix_login_attempt_email_date", "login_attempt", ["email_tried", "occurred_at"]
    )
    op.create_index("ix_login_attempt_ip_date", "login_attempt", ["client_ip", "occurred_at"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("actor_email", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("client_ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("jsonb_build_object()"),
            nullable=False,
        ),
        sa.CheckConstraint("outcome in ('success', 'failure')", name="ck_audit_log_outcome"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_date", "audit_log", ["occurred_at"])
    op.create_index("ix_audit_log_action_date", "audit_log", ["action", "occurred_at"])

    op.execute(FONCTION_AJOUT_SEUL)
    op.execute(DECLENCHEUR_LIGNE)
    op.execute(DECLENCHEUR_TRUNCATE)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update_delete ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_append_only();")

    op.drop_index("ix_audit_log_action_date", table_name="audit_log")
    op.drop_index("ix_audit_log_date", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_login_attempt_ip_date", table_name="login_attempt")
    op.drop_index("ix_login_attempt_email_date", table_name="login_attempt")
    op.drop_table("login_attempt")
