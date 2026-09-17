# Pourquoi : même séparation que `login_attempt` par rapport à `audit_log` : ce compteur est
# piloté par l'attaquant (une campagne de demandes) et se purge, l'audit log est en ajout seul.
# Piège : la tentative est enregistrée même quand l'email est inconnu, sinon le 429 apprendrait
# qu'un compte existe.

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Index, String, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PasswordResetAttempt(Base):
    __tablename__ = "password_reset_attempt"
    __table_args__ = (
        Index("ix_password_reset_attempt_email_date", "email_tried", "occurred_at"),
        Index("ix_password_reset_attempt_ip_date", "client_ip", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    email_tried: Mapped[str] = mapped_column(String(320), nullable=False)
    client_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
