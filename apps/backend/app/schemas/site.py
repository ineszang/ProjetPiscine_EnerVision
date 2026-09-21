from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    site_id: str
    site_name: str
    site_type: str
    location: str | None
    capacity_kw: float | None
    status: str | None


class SiteCurrentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime | None
    site_id: str
    site_type: str
    consumption_kw: float | None
    consumption_kwh: float | None
    voltage_v: float | None
    current_a: float | None
    power_factor: float | None
    temperature_celsius: float | None
    humidity_percent: float | None
    null_reasons: list[str]
    data_quality: Literal["good", "partial", "degraded", "critical"]
