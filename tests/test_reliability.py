from unittest.mock import Mock

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError

from api.app.agent import FixtureProvider
from api.app.config import Settings
from api.app.main import create_app, get_session
from api.app.models import Lead
from tests.conftest import VALID_LEAD


def test_replay_returns_original_without_calling_provider(client):
    provider = Mock(wraps=FixtureProvider())
    client.app.state.provider = provider
    headers = {"Idempotency-Key": "demo_1-key"}
    first = client.post("/leads", json=VALID_LEAD, headers=headers)
    replay = client.post("/leads", json={**VALID_LEAD, "budget": "0"}, headers=headers)
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert provider.generate.call_count == 1


def test_different_keys_and_missing_keys_create_distinct_leads(client):
    responses = [
        client.post("/leads", json=VALID_LEAD, headers=headers)
        for headers in ({"Idempotency-Key": "a"}, {"Idempotency-Key": "b"}, {}, {})
    ]
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 4


@pytest.mark.parametrize("key", ["", "x" * 101, "has space", "a/b", "a.b", "a\n"])
def test_invalid_idempotency_key(client, key):
    assert client.post(
        "/leads", json=VALID_LEAD, headers={"Idempotency-Key": key}
    ).status_code == 422


def test_idempotency_key_max_length(client):
    assert client.post(
        "/leads", json=VALID_LEAD, headers={"Idempotency-Key": "x" * 100}
    ).status_code == 201


def test_commit_collision_rolls_back_and_returns_winner(client, session_factory):
    headers = {"Idempotency-Key": "race"}
    winner = client.post("/leads", json=VALID_LEAD, headers=headers)
    with session_factory() as session:
        # Simulate an initial lookup before the other request committed. The insert
        # then hits the real database's unique index; the second lookup sees the winner.
        scalar = session.scalar
        calls = 0

        def lookup(statement):
            nonlocal calls
            calls += 1
            return None if calls == 1 else scalar(statement)

        session.scalar = lookup
        session.rollback = Mock(wraps=session.rollback)

        def racing_session():
            yield session

        client.app.dependency_overrides[get_session] = racing_session
        try:
            replay = client.post("/leads", json=VALID_LEAD, headers=headers)
        finally:
            client.app.dependency_overrides.clear()
        assert replay.status_code == 200
        assert replay.json() == winner.json()
        session.rollback.assert_called_once()
    with session_factory() as session:
        assert len(session.scalars(select(Lead)).all()) == 1


def test_unrelated_integrity_error_is_not_hidden(client, session_factory):
    with session_factory() as session:
        session.commit = Mock(side_effect=IntegrityError("insert", {}, Exception("failure")))
        session.rollback = Mock(wraps=session.rollback)

        def broken_session():
            yield session

        client.app.dependency_overrides[get_session] = broken_session
        try:
            with pytest.raises(IntegrityError):
                client.post("/leads", json=VALID_LEAD, headers={"Idempotency-Key": "new"})
        finally:
            client.app.dependency_overrides.clear()
        session.rollback.assert_called_once()


def test_rate_limit_and_window_reset(session_factory):
    now = [120.0]
    app = create_app(
        Settings(database_url="sqlite://", rate_limit_per_minute=2),
        session_factory=session_factory, clock=lambda: now[0],
    )
    with TestClient(app, client=("192.0.2.1", 123)) as client:
        assert client.post("/leads", json=VALID_LEAD).status_code == 201
        assert client.post("/leads", json=VALID_LEAD).status_code == 201
        now[0] = 179.1
        limited = client.post("/leads", json=VALID_LEAD)
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "1"
        assert client.get("/health").status_code == 200
        with TestClient(app, client=("192.0.2.2", 456)) as other:
            assert other.post("/leads", json=VALID_LEAD).status_code == 201
        now[0] = 180.0
        assert client.post("/leads", json=VALID_LEAD).status_code == 201


def test_rate_limit_disabled(make_client):
    with make_client(rate_limit_per_minute=0) as client:
        for _ in range(35):
            assert client.post("/leads", json=VALID_LEAD).status_code == 201


def test_rate_limit_environment(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "7")
    assert Settings.from_env().rate_limit_per_minute == 7
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    assert Settings.from_env().rate_limit_per_minute == 0


def test_migration_upgrade_and_downgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0001")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            # Existing demo rows must survive the nullable-column migration.
            connection.exec_driver_sql(
                "INSERT INTO leads (name, company, message, budget, data_label, "
                "created_at, qualification) VALUES "
                "('DEMO DATA', 'DEMO DATA', 'DEMO DATA', 0, 'DEMO DATA', "
                "CURRENT_TIMESTAMP, '{}')"
            )
        command.upgrade(config, "head")
        columns = {column["name"]: column for column in inspect(engine).get_columns("leads")}
        assert columns["idempotency_key"]["nullable"]
        assert columns["idempotency_key"]["type"].length == 100
        assert any(index["unique"] and index["column_names"] == ["idempotency_key"]
                   for index in inspect(engine).get_indexes("leads"))
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT count(*) FROM leads").scalar() == 1
        command.downgrade(config, "0001")
        assert "idempotency_key" not in {
            column["name"] for column in inspect(engine).get_columns("leads")
        }
    finally:
        engine.dispose()
