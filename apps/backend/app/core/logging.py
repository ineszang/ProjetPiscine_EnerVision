# Pourquoi : `RedactingFilter` est la troisième ligne de défense, pas la première. La première
# est de ne jamais passer un secret au logger, la deuxième de ne jamais mettre un jeton dans
# une URL, que le journal d'accès enregistrerait de toute façon. Le filtre rattrape l'erreur
# que personne n'a relue, notamment l'écho SQL quand `debug` est actif.

import logging
import re
from logging.config import dictConfig
from typing import Final

from app.core.config import Settings

CAVIARDAGE: Final = "[expurgé]"

REMPLACEMENTS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{20,}=*"), f"Bearer {CAVIARDAGE}"),
    (re.compile(r"eyJ[A-Za-z0-9._-]{20,}"), CAVIARDAGE),
    (re.compile(r"\$argon2[a-z0-9]*\$\S+"), CAVIARDAGE),
    (
        re.compile(r'("?(?:password|mot_de_passe|secret|token)"?\s*[:=]\s*")[^"]*(")'),
        rf"\1{CAVIARDAGE}\2",
    ),
    (
        re.compile(r"((?:password|mot_de_passe|secret|token)[A-Za-z_]*=)[^&\s;\"]+"),
        rf"\1{CAVIARDAGE}",
    ),
    (re.compile(r"(ev_refresh=)[^;\s]+"), rf"\1{CAVIARDAGE}"),
)


def redact(message: str) -> str:
    for motif, remplacement in REMPLACEMENTS:
        message = motif.sub(remplacement, message)
    return message


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        expurge = redact(message)
        if expurge != message:
            record.msg = expurge
            record.args = ()
        return True


def configure_logging(settings: Settings) -> None:
    formatter = "json" if settings.is_production else "console"
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "redaction": {"()": "app.core.logging.RedactingFilter"},
            },
            "formatters": {
                "console": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s %(message)s",
                },
                "json": {
                    "()": "pythonjsonlogger.json.JsonFormatter",
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter,
                    "filters": ["redaction"],
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"handlers": ["default"], "level": settings.log_level},
            "loggers": {
                "uvicorn": {
                    "handlers": ["default"],
                    "level": settings.log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["default"],
                    "level": settings.log_level,
                    "propagate": False,
                },
                "sqlalchemy.engine": {"level": "WARNING"},
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
