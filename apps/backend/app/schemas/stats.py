from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SiteSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    site_id: str
    site_name: str
    current_consumption_kw: float | None
    capacity_kw: float
    load_percent: float | None
    data_quality: Literal["good", "partial", "degraded", "critical"]


class StatsSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    total_sites: int
    total_consumption_kw: float
    total_capacity_kw: float
    average_load_percent: float
    sites: list[SiteSummaryResponse]
