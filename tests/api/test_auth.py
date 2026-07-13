"""Tests for the shared-secret sidecar authentication (X-SPPS-Sidecar-Token)."""

import pytest

from spps_assistant.api.app import AUTH_HEADER, create_app
from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository


@pytest.fixture
def db(tmp_path):
    """Temporary SQLite database for test isolation."""
    db_path = tmp_path / 'spps_database.db'
    return SQLiteRepository(db_path)


def test_no_auth_token_configured_allows_requests_without_header(db):
    app = create_app(db=db)
    client = app.test_client()

    resp = client.get('/health')

    assert resp.status_code == 200


def test_auth_token_configured_rejects_missing_header(db):
    app = create_app(auth_token='secret-token', db=db)
    client = app.test_client()

    resp = client.get('/health')

    assert resp.status_code == 401
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'unauthorized'


def test_auth_token_configured_rejects_wrong_header_value(db):
    app = create_app(auth_token='secret-token', db=db)
    client = app.test_client()

    resp = client.get('/health', headers={AUTH_HEADER: 'wrong-value'})

    assert resp.status_code == 401


def test_auth_token_configured_allows_correct_header_value(db):
    app = create_app(auth_token='secret-token', db=db)
    client = app.test_client()

    resp = client.get('/health', headers={AUTH_HEADER: 'secret-token'})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True


def test_auth_token_configured_also_protects_config_route(db):
    """The before_request hook must protect every route, not just /health."""
    app = create_app(auth_token='secret-token', db=db)
    client = app.test_client()

    resp = client.get('/config')

    assert resp.status_code == 401
