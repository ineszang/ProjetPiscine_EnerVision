# Contrainte : la table s'appelle `app_user` et non `user`, qui est un mot réservé PostgreSQL,
# raccourci de `CURRENT_USER`. Le nom rappelle aussi qu'il s'agit d'un compte applicatif, par
# opposition au rôle PostgreSQL qui porte, lui, le cantonnement des accès.

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.roles import AccountKind, Role
from app.db.base import Base

ROLES_AUTORISES = ", ".join(f"'{role.value}'" for role in Role)
NATURES_AUTORISEES = ", ".join(f"'{nature.value}'" for nature in AccountKind)


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_app_user_email_minuscule"),
        CheckConstraint(f"role in ({ROLES_AUTORISES})", name="ck_app_user_role"),
        CheckConstraint(f"kind in ({NATURES_AUTORISEES})", name="ck_app_user_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'human'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Une seule colonne couvre le changement de mot de passe, le changement de rôle et la
    # désactivation : tout jeton émis avant cet instant est périmé.
    credentials_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
