from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class PredictionTargetMetric(StrEnum):
    CONSUMPTION_KWH = "consumption_kwh"
    CONSUMPTION_KW = "consumption_kw"


class PredictionStatus(StrEnum):
    AVAILABLE = "available"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


class SitePredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_at: datetime
    target_metric: PredictionTargetMetric
    period_minutes: int | None
    predicted_value: float | None
    status: PredictionStatus
    failure_reason: str | None
    model_reference: str
    created_at: datetime


class SitePredictionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    site_id: str
    site_name: str
    prediction: SitePredictionResponse | None


class PredictionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    sites: list[SitePredictionSummaryResponse]
