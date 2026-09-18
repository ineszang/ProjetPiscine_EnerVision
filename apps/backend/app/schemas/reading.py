from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ReadingSource(StrEnum):
    CSV = "csv"
    API_CURRENT = "api_current"
    API_HISTORY = "api_history"


class ReadingDataQuality(StrEnum):
    GOOD = "good"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class ReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reading_id: int
    site_id: str
    timestamp: datetime
    source: ReadingSource
    consumption_kw: float | None
    consumption_kwh: float | None
    # Piège : `Decimal` (miroir de `Numeric(14, 2)` en base, pour ne pas arrondir un montant)
    # sérialise en chaîne dans le JSON, pas en nombre — un consommateur qui ferait un `parseFloat`
    # naïf perdrait la précision que ce choix visait à garder.
    consumption_euros: Decimal | None
    voltage_v: float | None
    current_a: float | None
    power_factor: float | None
    temperature_celsius: float | None
    humidity_percent: float | None
    solar_irradiance_wm2: float | None
    is_working_hours: bool | None
    data_quality: ReadingDataQuality | None
    null_reasons: list[str] | None
    imputed_values: dict[str, Any] | None
    imputation_method: str | None
