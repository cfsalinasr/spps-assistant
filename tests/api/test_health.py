"""Tests for the /health route."""

import pytest

from spps_assistant import __version__
from spps_assistant.api.app import create_app
from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository


@pytest.fixture
def app(tmp_path):
    """Flask app wired to a throwaway SQLite DB, not the real user database."""
    db_path = tmp_path / 'spps_database.db'
    db = SQLiteRepository(db_path)
    return create_app(db=db)


def test_health_returns_ok_envelope_with_status_and_version(app):
    client = app.test_client()

    resp = client.get('/health')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"ok": True, "data": {"status": "ok", "version": __version__}}
