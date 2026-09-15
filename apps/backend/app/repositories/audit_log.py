# Piège : `detail` passe par une liste blanche de clés et jamais par un `dict(**kwargs)`. La
# table est en ajout seul : une clé inattendue qui porterait un secret ou une donnée
# personnelle ne pourrait plus en être retirée.

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.models.audit_log import AuditAction, AuditLog, AuditOutcome

CLES_DE_DETAIL_AUTORISEES = frozenset(
    {
        "email",
        "role_avant",
        "role_apres",
        "famille",
        "motif",
        "source",
        "sessions_revoquees",
    }
)


def assemble_detail(brut: Mapping[str, Any] | None) -> dict[str, Any]:
    if not brut:
        return {}
    return {cle: valeur for cle, valeur in brut.items() if cle in CLES_DE_DETAIL_AUTORISEES}


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        action: AuditAction,
        outcome: AuditOutcome = AuditOutcome.SUCCES,
        actor: Principal | None = None,
        actor_label: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                actor_id=actor.id if actor else None,
                actor_email=actor.email if actor else actor_label,
                actor_role=actor.role.value if actor else None,
                action=action.value,
                target_type=target_type,
                target_id=target_id,
                outcome=outcome.value,
                client_ip=client_ip,
                user_agent=user_agent,
                detail=assemble_detail(detail),
            )
        )
