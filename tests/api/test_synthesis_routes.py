"""Tests for the /synthesis/generate and /synthesis/last routes."""

import pytest

from spps_assistant.api.app import create_app
from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app wired to throwaway config/DB, with the marker file redirected
    to a tmp path so this test never touches the real
    ~/.spps_assistant/last_synthesis.json."""
    import spps_assistant.api.routes.synthesis as synthesis_module

    config_path = tmp_path / 'spps_config.yaml'
    db_path = tmp_path / 'spps_database.db'
    marker_path = tmp_path / 'last_synthesis.json'
    monkeypatch.setattr(synthesis_module, '_MARKER_PATH', marker_path)

    config_repo = YAMLConfigRepository(config_path)
    db = SQLiteRepository(db_path)
    return create_app(config_repo=config_repo, db=db)


def _vessel_payload(number, name, tokens):
    return {
        'number': number, 'name': name,
        'original_tokens': tokens, 'reversed_tokens': list(reversed(tokens)),
        'resin_mass_g': 0.1, 'substitution_mmol_g': 0.3,
    }


def _residue_payload(fmoc_mw=311.3, free_mw=71.08):
    return {'base_code': 'A', 'protection': '', 'fmoc_mw': fmoc_mw, 'free_mw': free_mw}


def test_generate_writes_real_output_files(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A', 'G'])],
        'residue_info_map': {
            'A': _residue_payload(311.3, 71.08),
            'G': _residue_payload(297.3, 57.05),
        },
        'config_overrides': {
            'name': 'TestRun',
            'output_directory': str(out_dir),
            'resin_mass_strategy': 'fixed',
            'fixed_resin_mass_g': 0.1,
        },
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert out_dir.exists()
    assert len(list(out_dir.glob('*.pdf'))) >= 1


def test_generate_writes_last_synthesis_marker(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.get('/synthesis/last')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data']['name'] == 'TestRun'
    assert body['data']['vessel_count'] == 1


def test_last_synthesis_returns_null_when_none_generated(app):
    client = app.test_client()

    resp = client.get('/synthesis/last')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data'] is None


def test_generate_missing_vessels_returns_400(app):
    client = app.test_client()

    resp = client.post('/synthesis/generate', json={})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_generate_target_yield_strategy_backcalculates_resin_mass(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {
            'name': 'TargetRun',
            'output_directory': str(out_dir),
            'resin_mass_strategy': 'target',
            'target_yield_mg': 50.0,
        },
    })

    assert resp.status_code == 200
    assert len(list(out_dir.glob('*.pdf'))) >= 1
