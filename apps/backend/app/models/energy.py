"""Tables du modèle de données EnerVision (CSV, API Mock et résultats ML)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        CheckConstraint("dataset_id > 0", name="ck_datasets_positive_id"),
        UniqueConstraint("archive_sha256", name="uq_datasets_archive_sha256"),
    )

    dataset_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset_name: Mapped[str] = mapped_column(Text)
    archive_sha256: Mapped[str] = mapped_column(String(64))
    storage_uri: Mapped[str] = mapped_column(Text)
    source_timezone: Mapped[str | None] = mapped_column(Text)
    # "metadata" est réservé par SQLAlchemy ; le nom SQL reste inchangé.
    dataset_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB(none_as_null=True))


class Site(Base):
    __tablename__ = "sites"

    site_id: Mapped[str] = mapped_column(Text, primary_key=True)
    site_name: Mapped[str] = mapped_column(Text)
    site_type: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    capacity_kw: Mapped[float | None] = mapped_column(Double)
    status: Mapped[str | None] = mapped_column(Text)


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        CheckConstraint(
            "source IN ('csv', 'api_current', 'api_history')", name="ck_readings_source"
        ),
        CheckConstraint(
            "(source = 'csv' AND dataset_id IS NOT NULL) OR "
            "(source IN ('api_current', 'api_history') AND dataset_id IS NULL)",
            name="ck_readings_dataset_source",
        ),
        CheckConstraint(
            "data_quality IS NULL OR data_quality IN ('good', 'partial', 'degraded', 'critical')",
            name="ck_readings_quality",
        ),
        CheckConstraint(
            "(imputed_values IS NULL AND imputation_method IS NULL) OR "
            "(imputed_values IS NOT NULL AND imputation_method IS NOT NULL)",
            name="ck_readings_imputation",
        ),
        Index("ix_readings_site_timestamp", "site_id", "timestamp"),
        Index("ix_readings_dataset_id", "dataset_id"),
    )

    reading_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sites.site_id", name="fk_readings_site", ondelete="RESTRICT")
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    dataset_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("datasets.dataset_id", name="fk_readings_dataset", ondelete="RESTRICT"),
    )
    consumption_kw: Mapped[float | None] = mapped_column(Double)
    consumption_kwh: Mapped[float | None] = mapped_column(Double)
    consumption_euros: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    voltage_v: Mapped[float | None] = mapped_column(Double)
    current_a: Mapped[float | None] = mapped_column(Double)
    power_factor: Mapped[float | None] = mapped_column(Double)
    temperature_celsius: Mapped[float | None] = mapped_column(Double)
    humidity_percent: Mapped[float | None] = mapped_column(Double)
    solar_irradiance_wm2: Mapped[float | None] = mapped_column(Double)
    is_working_hours: Mapped[bool | None] = mapped_column(Boolean)
    data_quality: Mapped[str | None] = mapped_column(Text)
    null_reasons: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    imputed_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    imputation_method: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True))


Index(
    "uq_readings_source",
    Reading.site_id,
    Reading.timestamp,
    Reading.source,
    func.coalesce(Reading.dataset_id, text("0")),
    unique=True,
)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("prediction_id", "site_id", name="uq_predictions_id_site"),
        Index("ix_predictions_site_target", "site_id", "target_at"),
        CheckConstraint(
            "target_metric IN ('consumption_kwh', 'consumption_kw')",
            name="ck_predictions_metric",
        ),
        CheckConstraint(
            "period_minutes IS NULL OR period_minutes > 0", name="ck_predictions_period"
        ),
        CheckConstraint(
            "target_metric <> 'consumption_kwh' OR period_minutes IS NOT NULL",
            name="ck_predictions_energy_period",
        ),
        CheckConstraint(
            "(status = 'available' AND predicted_value IS NOT NULL AND failure_reason IS NULL) OR "
            "(status IN ('insufficient_data', 'error') AND predicted_value IS NULL "
            "AND failure_reason IS NOT NULL)",
            name="ck_predictions_status",
        ),
    )

    prediction_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sites.site_id", name="fk_predictions_site", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    target_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_metric: Mapped[str] = mapped_column(Text)
    period_minutes: Mapped[int | None] = mapped_column(Integer)
    predicted_value: Mapped[float | None] = mapped_column(Double)
    model_reference: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("source", "site_id", "alert_id", name="uq_alerts_source_site_id"),
        Index("ix_alerts_site_timestamp", "site_id", "timestamp"),
        ForeignKeyConstraint(
            ["prediction_id", "site_id"],
            ["predictions.prediction_id", "predictions.site_id"],
            name="fk_alerts_prediction_site",
            ondelete="RESTRICT",
        ),
        CheckConstraint("source IN ('api_mock', 'enervision')", name="ck_alerts_source"),
        CheckConstraint(
            "type IN ('spike', 'threshold', 'anomaly', 'outage', 'sensor')", name="ck_alerts_type"
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')", name="ck_alerts_severity"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(Text)
    site_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sites.site_id", name="fk_alerts_site", ondelete="RESTRICT")
    )
    source: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    type: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Double)
    threshold: Mapped[float | None] = mapped_column(Double)
    metric: Mapped[str | None] = mapped_column(Text)
    prediction_id: Mapped[int | None] = mapped_column(BigInteger)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True))


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("alert_id", "rule_reference", name="uq_recommendations_alert_rule"),
    )

    recommendation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("alerts.id", name="fk_recommendations_alert", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    rule_reference: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
