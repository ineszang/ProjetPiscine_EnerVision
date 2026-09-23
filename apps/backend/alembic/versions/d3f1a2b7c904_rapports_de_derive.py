"""rapports de derive du modele de prevision

Revision ID: d3f1a2b7c904
Revises: c0adab96238c
Create Date: 2026-09-22 14:40:00.000000

`site_id` est nullable, et c'est le coeur du schema : une ligne par site, plus une ligne
globale tous sites confondus, que `NULL` designe. Un seul site qui derive est invisible dans
une moyenne d'ensemble, et une derive d'ensemble sans rupture par site signale un changement
de modele ou de saison, pas une panne.

L'unicite passe par un index a `coalesce` et non par une `UniqueConstraint` : deux lignes
globales successives ont toutes deux `site_id` a NULL, et NULL n'est egal a aucune valeur, pas
meme a lui-meme. Meme forme que `uq_reading_source`.

Les trois `CHECK` sont portees par la base, comme `ck_prediction_status` : un verdict sans
motif, ou un statut inconnu, ne doit pas dependre de la vigilance de l'appelant.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3f1a2b7c904"
down_revision: str | Sequence[str] | None = "c0adab96238c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drift_report",
        sa.Column("drift_report_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("site_id", sa.Text(), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("n_observations", sa.Integer(), nullable=False),
        sa.Column("mae", sa.Double(), nullable=True),
        sa.Column("mape", sa.Double(), nullable=True),
        sa.Column("bias", sa.Double(), nullable=True),
        sa.Column("reference_mae", sa.Double(), nullable=True),
        sa.Column("coverage_ratio", sa.Double(), nullable=True),
        sa.Column("insufficient_data_ratio", sa.Double(), nullable=True),
        sa.Column("model_references", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('stable', 'derive', 'indetermine')", name="ck_drift_report_status"
        ),
        sa.CheckConstraint(
            "status = 'stable' OR reason IS NOT NULL", name="ck_drift_report_reason"
        ),
        sa.CheckConstraint("n_observations >= 0", name="ck_drift_report_observations"),
        sa.ForeignKeyConstraint(
            ["site_id"], ["site.site_id"], name="fk_drift_report_site", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("drift_report_id"),
    )
    op.create_index(
        "ix_drift_report_site_computed", "drift_report", ["site_id", "computed_at"], unique=False
    )
    op.create_index(
        "uq_drift_report_window",
        "drift_report",
        ["window_end", sa.literal_column("coalesce(site_id, '')")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("drift_report")
