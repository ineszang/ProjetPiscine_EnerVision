from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.models.energy import Reading, Site
from app.repositories.reading import ReadingRepository
from app.repositories.site import SiteRepository

CapteurStatus = Literal["ok", "failing"]
OverallStatus = Literal["ok", "degraded", "critical"]

QUALITES_CONNUES: frozenset[str] = frozenset({"good", "partial", "degraded", "critical"})

RAISON_VERS_CAPTEUR: dict[str, str] = {
    "consumption_sensor_failure": "consumption",
    "electrical_sensor_failure": "electrical",
    "temperature_sensor_failure": "temperature",
    "humidity_sensor_failure": "humidity",
    "network_loss": "network",
}

CHAMPS_PAR_CAPTEUR: dict[str, tuple[str, ...]] = {
    "consumption": ("consumption_kw",),
    "electrical": ("voltage_v", "current_a", "power_factor"),
    "temperature": ("temperature_celsius",),
    "humidity": ("humidity_percent",),
}


@dataclass(frozen=True, slots=True)
class DiagnosticCapteur:
    status: CapteurStatus
    since: datetime | None


@dataclass(frozen=True, slots=True)
class SanteCapteurs:
    consumption: DiagnosticCapteur
    electrical: DiagnosticCapteur
    temperature: DiagnosticCapteur
    humidity: DiagnosticCapteur
    network: DiagnosticCapteur


@dataclass(frozen=True, slots=True)
class SanteSite:
    site_id: str
    site_name: str
    sensors: SanteCapteurs
    overall: OverallStatus


@dataclass(frozen=True, slots=True)
class EtatCapteurs:
    timestamp: datetime
    sites: list[SanteSite]


class SensorService:
    def __init__(self, sites: SiteRepository, readings: ReadingRepository) -> None:
        self._sites = sites
        self._readings = readings

    async def status(self) -> EtatCapteurs:
        sites = await self._sites.list_all()
        dernieres = {lecture.site_id: lecture for lecture in await self._readings.latest_by_site()}

        return EtatCapteurs(
            timestamp=datetime.now(UTC),
            sites=[_sante_site(site, dernieres.get(site.site_id)) for site in sites],
        )


def _sante_site(site: Site, derniere: Reading | None) -> SanteSite:
    if derniere is None:
        return SanteSite(
            site_id=site.site_id,
            site_name=site.site_name,
            sensors=_tout_en_echec(since=None),
            overall="critical",
        )

    qualite = derniere.data_quality if derniere.data_quality in QUALITES_CONNUES else "critical"
    overall = _overall_depuis_qualite(qualite)

    if overall == "critical":
        return SanteSite(
            site_id=site.site_id,
            site_name=site.site_name,
            sensors=_tout_en_echec(since=derniere.timestamp),
            overall="critical",
        )

    raisons_signalees = {
        RAISON_VERS_CAPTEUR[raison]
        for raison in (derniere.null_reasons or [])
        if raison in RAISON_VERS_CAPTEUR
    }

    return SanteSite(
        site_id=site.site_id,
        site_name=site.site_name,
        sensors=SanteCapteurs(
            consumption=_diagnostic("consumption", derniere, raisons_signalees),
            electrical=_diagnostic("electrical", derniere, raisons_signalees),
            temperature=_diagnostic("temperature", derniere, raisons_signalees),
            humidity=_diagnostic("humidity", derniere, raisons_signalees),
            network=_diagnostic("network", derniere, raisons_signalees),
        ),
        overall=overall,
    )


def _overall_depuis_qualite(qualite: str) -> OverallStatus:
    if qualite == "good":
        return "ok"
    if qualite in ("partial", "degraded"):
        return "degraded"
    return "critical"


def _diagnostic(capteur: str, derniere: Reading, raisons_signalees: set[str]) -> DiagnosticCapteur:
    champs = CHAMPS_PAR_CAPTEUR.get(capteur, ())
    en_echec = capteur in raisons_signalees or any(
        getattr(derniere, champ) is None for champ in champs
    )
    return DiagnosticCapteur(
        status="failing" if en_echec else "ok",
        since=derniere.timestamp if en_echec else None,
    )


def _tout_en_echec(since: datetime | None) -> SanteCapteurs:
    echec = DiagnosticCapteur(status="failing", since=since)
    return SanteCapteurs(
        consumption=echec, electrical=echec, temperature=echec, humidity=echec, network=echec
    )
