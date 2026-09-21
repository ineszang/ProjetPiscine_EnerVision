from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SensorDiagnosticResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["ok", "failing"]
    since: datetime | None = Field(
        description=(
            "Horodatage de la dernière lecture reçue pour ce site. Ce n'est pas le début de la "
            "panne : l'historique ne permet pas de le dater sans requête supplémentaire."
        )
    )


class SiteSensorsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consumption: SensorDiagnosticResponse
    electrical: SensorDiagnosticResponse
    temperature: SensorDiagnosticResponse
    humidity: SensorDiagnosticResponse
    network: SensorDiagnosticResponse


class SiteSensorStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    site_id: str
    site_name: str
    sensors: SiteSensorsResponse
    overall: Literal["ok", "degraded", "critical"]


class SensorStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    sites: list[SiteSensorStatusResponse]
