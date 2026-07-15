"""Tests for the /health route."""

import pytest

from spps_assistant import __version__


@pytest.fixture
def app(app_with_db):
    """Flask app wired to a throwaway SQLite DB, not the real user database."""
    return app_with_db


def test_health_returns_ok_envelope_with_status_and_version(app):
    client = app.test_client()

    resp = client.get('/health')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"ok": True, "data": {"status": "ok", "version": __version__}}
