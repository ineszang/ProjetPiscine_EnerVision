# Piège : tout modèle absent de ce module reste invisible de `alembic revision
# --autogenerate`, qui générerait alors un drop de sa table.

from app.models.audit_log import AuditLog
from app.models.energy import (
    Alert,
    Dataset,
    DriftReport,
    Prediction,
    Reading,
    Recommendation,
    Site,
)
from app.models.login_attempt import LoginAttempt
from app.models.password_reset_attempt import PasswordResetAttempt
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import AppUser

__all__ = [
    "Alert",
    "AppUser",
    "AuditLog",
    "Dataset",
    "DriftReport",
    "LoginAttempt",
    "PasswordResetAttempt",
    "PasswordResetToken",
    "Prediction",
    "Reading",
    "Recommendation",
    "RefreshToken",
    "Site",
]
