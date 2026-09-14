"""socle garde extension timescaledb

Revision ID: 5353c0e4f094
Revises:
Create Date: 2026-09-14 14:17:17.556764

Premiere revision du schema applicatif. Elle ne cree aucune table : elle etablit
alembic_version et refuse de s'appliquer sur une base ou l'extension TimescaleDB
manque, cas qui se produit quand db/init n'a pas ete joue.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "5353c0e4f094"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GARDE_EXTENSION = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        RAISE EXCEPTION 'extension timescaledb absente, voir db/init et db/README.md';
    END IF;
END
$$;
"""


def upgrade() -> None:
    op.execute(GARDE_EXTENSION)


def downgrade() -> None:
    pass
