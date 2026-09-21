from typing import Literal

from pydantic import BaseModel


class LivenessStatus(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


# Contrainte : la sonde ne publie pas la version de TimescaleDB. Une version exacte de
# composant, servie sans authentification, est de la reconnaissance gratuite pour qui
# cherche une CVE. Elle part dans le journal, où elle sert au diagnostic.
class ReadinessStatus(BaseModel):
    status: Literal["ready"]
    database: Literal["reachable"]
    timescaledb: Literal["loaded"]
