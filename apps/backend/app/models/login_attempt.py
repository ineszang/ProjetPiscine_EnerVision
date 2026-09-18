# Pourquoi : les tentatives vivent ici et non dans `audit_log`, qui est en ajout seul. Leur
# volume est piloté par l'attaquant : une force brute y écrirait des millions de lignes
# indestructibles. Cette table-ci se purge, et c'est aussi le compteur de la limitation.
# Piège : la tentative est enregistrée même quand l'email est inconnu, sinon le 429 dirait
# qu'un compte existe.

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, Index, String, Text, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginOutcome(StrEnum):
    SUCCES = "success"
    IDENTIFIANTS_INVALIDES = "bad_credentials"
    LIMITE = "throttled"
    COMPTE_INDISPONIBLE = "inactive"


ISSUES_AUTORISEES = ", ".join(f"'{issue.value}'" for issue in LoginOutcome)


class LoginAttempt(Base):
    __tablename__ = "login_attempt"
    __table_args__ = (
        CheckConstraint(f"outcome in ({ISSUES_AUTORISEES})", name="ck_login_attempt_outcome"),
        Index("ix_login_attempt_email_date", "email_tried", "occurred_at"),
        Index("ix_login_attempt_ip_date", "client_ip", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    email_tried: Mapped[str] = mapped_column(String(320), nullable=False)
    client_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
