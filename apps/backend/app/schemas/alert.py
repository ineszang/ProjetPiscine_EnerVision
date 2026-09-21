from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class AlertType(StrEnum):
    SPIKE = "spike"
    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    OUTAGE = "outage"
    SENSOR = "sensor"


class AlertSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: int
    site_id: str
    timestamp: datetime
    type: AlertType
    severity: AlertSeverity
    message: str
    value: float | None
    threshold: float | None
    metric: str | None
    prediction_id: int | None
