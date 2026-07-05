"""Tests for the /config routes."""

import pytest

from spps_assistant.api.app import create_app
from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository


@pytest.fixture
def app(tmp_path):
    """Flask app wired to a throwaway YAML config file, not the real user config."""
    config_path = tmp_path / 'spps_config.yaml'
    repo = YAMLConfigRepository(config_path)
    return create_app(config_repo=repo)


def test_get_config_returns_defaults(app):
    client = app.test_client()

    resp = client.get('/config')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data']['activator'] == 'HBTU'
    assert body['data']['aa_equivalents'] == 3.0


def test_post_config_persists_and_returns_updated_values(app):
    client = app.test_client()

    resp = client.post('/config', json={'activator': 'DIC', 'name': 'TestSynthesis'})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data']['activator'] == 'DIC'
    assert body['data']['name'] == 'TestSynthesis'

    # Verify it was actually persisted, not just echoed back
    resp2 = client.get('/config')
    assert resp2.get_json()['data']['activator'] == 'DIC'


def test_post_config_rejects_non_object_body(app):
    client = app.test_client()

    resp = client.post('/config', data='not valid json', content_type='application/json')

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'
