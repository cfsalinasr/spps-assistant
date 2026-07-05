"""Tests for the /health route."""

from spps_assistant import __version__
from spps_assistant.api.app import create_app


def test_health_returns_ok_envelope_with_status_and_version():
    app = create_app()
    client = app.test_client()

    resp = client.get('/health')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"ok": True, "data": {"status": "ok", "version": __version__}}
