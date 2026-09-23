from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class DriftStatus(StrEnum):
    STABLE = "stable"
    DERIVE = "derive"
    INDETERMINE = "indetermine"


class DriftReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    site_id: str | None
    computed_at: datetime
    window_start: datetime
    window_end: datetime
    reference_start: datetime | None
    reference_end: datetime | None
    n_observations: int
    mae: float | None
    mape: float | None
    bias: float | None
    reference_mae: float | None
    coverage_ratio: float | None
    insufficient_data_ratio: float | None
    model_references: list[str]
    status: DriftStatus
    reason: str | None
