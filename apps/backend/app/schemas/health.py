from typing import Literal

from pydantic import BaseModel


class LivenessStatus(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


class ReadinessStatus(BaseModel):
    status: Literal["ready"]
    database: Literal["reachable"]
