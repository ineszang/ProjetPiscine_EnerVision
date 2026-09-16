# Pourquoi : `actor_id` ne porte volontairement aucune clé étrangère. Une contrainte
# `ON DELETE SET NULL` déclencherait un UPDATE que le déclencheur d'ajout seul refuserait, donc
# la suppression d'un compte échouerait ; une contrainte `NO ACTION` interdirait toute
# suppression. `actor_email` et `actor_role` sont dénormalisés pour la même raison : le journal
# dit ce qui était vrai au moment de l'acte, pas ce qui est vrai aujourd'hui.

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, Index, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditOutcome(StrEnum):
    SUCCES = "success"
    ECHEC = "failure"


class AuditAction(StrEnum):
    COMPTE_CREE = "user.created"
    COMPTE_ROLE_CHANGE = "user.role_changed"
    COMPTE_DESACTIVE = "user.disabled"
    COMPTE_ACTIVE = "user.enabled"
    COMPTE_MOT_DE_PASSE_REINITIALISE = "user.password_reset_by_admin"
    COMPTE_MOT_DE_PASSE_CHANGE = "user.password_changed"
    REFRESH_REUTILISE = "auth.refresh_reuse_detected"
    SESSIONS_REVOQUEES = "auth.all_sessions_revoked"
    LIMITE_PAR_IDENTIFIANT = "auth.identifier_throttled"
    ADMIN_AMORCE = "bootstrap.admin_created"


ISSUES_AUTORISEES = ", ".join(f"'{issue.value}'" for issue in AuditOutcome)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(f"outcome in ({ISSUES_AUTORISEES})", name="ck_audit_log_outcome"),
        Index("ix_audit_log_date", "occurred_at"),
        Index("ix_audit_log_action_date", "action", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    client_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=func.jsonb_build_object()
    )
