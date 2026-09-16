from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.config import get_settings
from app.models.energy import Alert, Dataset, Prediction, Reading, Recommendation, Site

pytestmark = pytest.mark.integration
MOMENT = datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture
async def data_connection() -> AsyncIterator[AsyncConnection]:
    url = make_url(get_settings().database_url)
    if url.database != "enervision_test":
        pytest.fail("Ces tests exigent DATABASE_URL vers enervision_test.")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                yield connection
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
async def data_site(data_connection: AsyncConnection) -> str:
    site_id = f"TEST-{uuid4()}"
    await data_connection.execute(
        insert(Site).values(site_id=site_id, site_name="Site de test", site_type="office")
    )
    return site_id


async def test_reading_is_a_time_hypertable_when_migrated(
    data_connection: AsyncConnection,
) -> None:
    query = text(
        "SELECT column_name FROM timescaledb_information.dimensions "
        "WHERE hypertable_schema = 'public' AND hypertable_name = 'reading'"
    )

    result = await data_connection.execute(query)

    assert result.scalars().all() == ["timestamp"]


async def test_reading_preserves_null_and_zero_when_inserted(
    data_connection: AsyncConnection, data_site: str
) -> None:
    statement = insert(Reading).values(
        site_id=data_site,
        timestamp=MOMENT,
        source="api_current",
        consumption_kw=None,
        consumption_kwh=0,
        data_quality="partial",
        null_reasons=["sensor_failure"],
        raw_data={"consumption_kw": None},
        imputed_values=None,
        imputation_method=None,
    )

    await data_connection.execute(statement)
    result = (
        await data_connection.execute(
            select(
                Reading.consumption_kw,
                Reading.consumption_kwh,
                Reading.raw_data,
                Reading.imputed_values,
            ).where(Reading.site_id == data_site)
        )
    ).one()

    assert tuple(result) == (None, 0, {"consumption_kw": None}, None)


@pytest.mark.parametrize("source", ["csv", "api_current", "api_history"])
async def test_duplicate_reading_is_rejected_when_key_matches(
    data_connection: AsyncConnection, data_site: str, source: str
) -> None:
    dataset_id = None
    if source == "csv":
        dataset_id = (
            await data_connection.execute(
                insert(Dataset.__table__)
                .values(
                    dataset_name="Archive de test",
                    archive_sha256=uuid4().hex + uuid4().hex,
                    storage_uri="test://archive",
                    metadata={},
                )
                .returning(Dataset.dataset_id)
            )
        ).scalar_one()
    statement = insert(Reading).values(
        site_id=data_site,
        timestamp=MOMENT,
        source=source,
        dataset_id=dataset_id,
        raw_data={},
    )
    await data_connection.execute(statement)

    with pytest.raises(IntegrityError):
        async with data_connection.begin_nested():
            await data_connection.execute(statement)


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "csv"},
        {"source": "unknown"},
        {"site_id": "UNKNOWN-SITE"},
        {"data_quality": "unknown"},
        {"imputed_values": {"consumption_kw": 12}},
        {"imputation_method": "mean-v1"},
    ],
    ids=[
        "csv_sans_dataset",
        "source_inconnue",
        "site_absent",
        "qualite_inconnue",
        "imputation_sans_methode",
        "methode_sans_imputation",
    ],
)
async def test_invalid_reading_is_rejected_when_constraints_fail(
    data_connection: AsyncConnection, data_site: str, changes: dict[str, object]
) -> None:
    values: dict[str, object] = {
        "site_id": data_site,
        "timestamp": MOMENT,
        "source": "api_current",
        "raw_data": {},
    }
    values.update(changes)

    with pytest.raises(IntegrityError):
        async with data_connection.begin_nested():
            await data_connection.execute(insert(Reading).values(**values))


async def test_prediction_requires_period_when_energy_is_predicted(
    data_connection: AsyncConnection, data_site: str
) -> None:
    statement = insert(Prediction).values(
        site_id=data_site,
        target_at=MOMENT,
        target_metric="consumption_kwh",
        predicted_value=12,
        status="available",
        model_reference="test-model/1",
    )

    with pytest.raises(IntegrityError):
        async with data_connection.begin_nested():
            await data_connection.execute(statement)


async def test_unavailable_prediction_preserves_null_when_inserted(
    data_connection: AsyncConnection, data_site: str
) -> None:
    statement = (
        insert(Prediction)
        .values(
            site_id=data_site,
            target_at=MOMENT,
            target_metric="consumption_kw",
            status="insufficient_data",
            failure_reason="Historique trop court",
            model_reference="test-model/1",
        )
        .returning(Prediction.predicted_value)
    )

    value = (await data_connection.execute(statement)).scalar_one()

    assert value is None


async def test_alert_rejects_prediction_when_site_differs(
    data_connection: AsyncConnection, data_site: str
) -> None:
    other_site = f"TEST-{uuid4()}"
    await data_connection.execute(
        insert(Site).values(site_id=other_site, site_name="Autre site", site_type="office")
    )
    prediction_id = (
        await data_connection.execute(
            insert(Prediction)
            .values(
                site_id=data_site,
                target_at=MOMENT,
                target_metric="consumption_kw",
                predicted_value=12,
                status="available",
                model_reference="test-model/1",
            )
            .returning(Prediction.prediction_id)
        )
    ).scalar_one()

    with pytest.raises(IntegrityError):
        async with data_connection.begin_nested():
            await data_connection.execute(
                insert(Alert).values(
                    source_alert_id=str(uuid4()),
                    site_id=other_site,
                    source="enervision",
                    timestamp=MOMENT,
                    type="spike",
                    severity="high",
                    message="Test",
                    prediction_id=prediction_id,
                    raw_data={},
                )
            )


async def test_recommendation_is_unique_when_alert_and_rule_match(
    data_connection: AsyncConnection, data_site: str
) -> None:
    alert_id = (
        await data_connection.execute(
            insert(Alert)
            .values(
                source_alert_id=str(uuid4()),
                site_id=data_site,
                source="api_mock",
                timestamp=MOMENT,
                type="spike",
                severity="high",
                message="Test",
                raw_data={},
            )
            .returning(Alert.alert_id)
        )
    ).scalar_one()
    statement = insert(Recommendation).values(
        alert_id=alert_id,
        action="Vérifier la consommation",
        explanation="Pic détecté",
        rule_reference="spike-v1",
    )
    await data_connection.execute(statement)

    with pytest.raises(IntegrityError):
        async with data_connection.begin_nested():
            await data_connection.execute(statement)
