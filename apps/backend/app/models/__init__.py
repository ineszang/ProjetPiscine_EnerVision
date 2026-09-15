# Piege : tout modele absent de ce module reste invisible de `alembic revision
# --autogenerate`, qui genererait alors un drop de sa table.

from app.models.energy import Alert, Dataset, Prediction, Reading, Recommendation, Site

__all__ = ["Alert", "Dataset", "Prediction", "Reading", "Recommendation", "Site"]
