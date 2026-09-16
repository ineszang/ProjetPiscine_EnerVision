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
    __tablename__ = "dataset"
    __table_args__ = (
        CheckConstraint("dataset_id > 0", name="ck_dataset_positive_id"),
        UniqueConstraint("archive_sha256", name="uq_dataset_archive_sha256"),
    )

    dataset_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset_name: Mapped[str] = mapped_column(Text)
    archive_sha256: Mapped[str] = mapped_column(String(64))
    storage_uri: Mapped[str] = mapped_column(Text)
    source_timezone: Mapped[str | None] = mapped_column(Text)
    # "metadata" est réservé par SQLAlchemy ; le nom SQL reste inchangé.
    dataset_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB(none_as_null=True))


class Site(Base):
    __tablename__ = "site"

    site_id: Mapped[str] = mapped_column(Text, primary_key=True)
    site_name: Mapped[str] = mapped_column(Text)
    site_type: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    capacity_kw: Mapped[float | None] = mapped_column(Double)
    status: Mapped[str | None] = mapped_column(Text)


class Reading(Base):
    __tablename__ = "reading"
    __table_args__ = (
        CheckConstraint(
            "source IN ('csv', 'api_current', 'api_history')", name="ck_reading_source"
        ),
        CheckConstraint(
            "(source = 'csv' AND dataset_id IS NOT NULL) OR "
            "(source IN ('api_current', 'api_history') AND dataset_id IS NULL)",
            name="ck_reading_dataset_source",
        ),
        CheckConstraint(
            "data_quality IS NULL OR data_quality IN ('good', 'partial', 'degraded', 'critical')",
            name="ck_reading_quality",
        ),
        CheckConstraint(
            "(imputed_values IS NULL AND imputation_method IS NULL) OR "
            "(imputed_values IS NOT NULL AND imputation_method IS NOT NULL)",
            name="ck_reading_imputation",
        ),
        Index("ix_reading_site_timestamp", "site_id", "timestamp"),
        Index("ix_reading_dataset_id", "dataset_id"),
    )

    reading_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        Text, ForeignKey("site.site_id", name="fk_reading_site", ondelete="RESTRICT")
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    dataset_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("dataset.dataset_id", name="fk_reading_dataset", ondelete="RESTRICT"),
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
    "uq_reading_source",
    Reading.site_id,
    Reading.timestamp,
    Reading.source,
    func.coalesce(Reading.dataset_id, text("0")),
    unique=True,
)


class Prediction(Base):
    __tablename__ = "prediction"
    __table_args__ = (
        UniqueConstraint("prediction_id", "site_id", name="uq_prediction_id_site"),
        Index("ix_prediction_site_target", "site_id", "target_at"),
        CheckConstraint(
            "target_metric IN ('consumption_kwh', 'consumption_kw')",
            name="ck_prediction_metric",
        ),
        CheckConstraint(
            "period_minutes IS NULL OR period_minutes > 0", name="ck_prediction_period"
        ),
        CheckConstraint(
            "target_metric <> 'consumption_kwh' OR period_minutes IS NOT NULL",
            name="ck_prediction_energy_period",
        ),
        CheckConstraint(
            "(status = 'available' AND predicted_value IS NOT NULL AND failure_reason IS NULL) OR "
            "(status IN ('insufficient_data', 'error') AND predicted_value IS NULL "
            "AND failure_reason IS NOT NULL)",
            name="ck_prediction_status",
        ),
    )

    prediction_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        Text, ForeignKey("site.site_id", name="fk_prediction_site", ondelete="RESTRICT")
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
    __tablename__ = "alert"
    __table_args__ = (
        UniqueConstraint("source", "site_id", "source_alert_id", name="uq_alert_source_reference"),
        Index("ix_alert_site_timestamp", "site_id", "timestamp"),
        ForeignKeyConstraint(
            ["prediction_id", "site_id"],
            ["prediction.prediction_id", "prediction.site_id"],
            name="fk_alert_prediction_site",
            ondelete="RESTRICT",
        ),
        CheckConstraint("source IN ('api_mock', 'enervision')", name="ck_alert_source"),
        CheckConstraint(
            "type IN ('spike', 'threshold', 'anomaly', 'outage', 'sensor')", name="ck_alert_type"
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')", name="ck_alert_severity"
        ),
    )

    alert_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_alert_id: Mapped[str] = mapped_column(Text)
    site_id: Mapped[str] = mapped_column(
        Text, ForeignKey("site.site_id", name="fk_alert_site", ondelete="RESTRICT")
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
    __tablename__ = "recommendation"
    __table_args__ = (
        UniqueConstraint("alert_id", "rule_reference", name="uq_recommendation_alert_rule"),
    )

    recommendation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("alert.alert_id", name="fk_recommendation_alert", ondelete="RESTRICT"),
    )
    action: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    rule_reference: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
