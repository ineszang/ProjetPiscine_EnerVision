# Pourquoi : un jeton de rafraîchissement est une chaîne opaque, jamais un JWT. Il doit être
# révocable, donc cette ligne existe de toute façon ; le JWT n'ajouterait qu'un second chemin de
# signature. Surtout, la séparation devient structurelle : un JWT ne figure dans aucune ligne,
# une chaîne opaque échoue au décodage. Aucune confusion de type n'est possible.
# Piège : `expires_at` est absolu et hérité du prédécesseur à chaque rotation. S'il glissait,
# la promesse de sept jours serait fictive et une session active ne finirait jamais.

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, Text, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RevocationReason(StrEnum):
    DECONNEXION = "logout"
    ROTATION = "rotation"
    REUTILISATION = "reuse_detected"
    CHANGEMENT_MOT_DE_PASSE = "password_change"
    ADMINISTRATION = "admin"


MOTIFS_AUTORISES = ", ".join(f"'{motif.value}'" for motif in RevocationReason)


class RefreshToken(Base):
    __tablename__ = "refresh_token"
    __table_args__ = (
        CheckConstraint(
            f"revoked_reason is null or revoked_reason in ({MOTIFS_AUTORISES})",
            name="ck_refresh_token_revoked_reason",
        ),
        Index("ix_refresh_token_family", "family_id"),
        Index("ix_refresh_token_user", "user_id"),
        Index(
            "ix_refresh_token_vivants",
            "user_id",
            postgresql_where="revoked_at is null and rotated_at is null",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    family_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
