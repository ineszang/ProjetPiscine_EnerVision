# Piège : l'URL de réinitialisation porte le jeton en clair. Ne jamais la journaliser :
# `send_password_reset_email()` ne logue que le destinataire, jamais `reset_url`.

from dataclasses import dataclass
from email.message import EmailMessage

import aiosmtplib

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    use_tls: bool
    from_address: str


class Mailer:
    def __init__(self, config: SmtpConfig) -> None:
        self._config = config

    async def send_password_reset_email(self, *, to: str, reset_url: str) -> None:
        message = EmailMessage()
        message["From"] = self._config.from_address
        message["To"] = to
        message["Subject"] = "Réinitialisation de votre mot de passe EnerVision"
        message.set_content(
            "Une réinitialisation de mot de passe a été demandée pour ce compte.\n\n"
            f"Ouvrez ce lien dans les 15 minutes pour choisir un nouveau mot de passe : "
            f"{reset_url}\n\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email."
        )

        _, message_recu = await aiosmtplib.send(
            message,
            hostname=self._config.host,
            port=self._config.port,
            username=self._config.username,
            password=self._config.password,
            use_tls=self._config.use_tls,
        )
        logger.info("mailer.password_reset_sent to=%s smtp_response=%s", to, message_recu)
