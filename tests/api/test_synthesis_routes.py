"""Tests for the /synthesis/generate and /synthesis/last routes."""

from pathlib import Path

import pytest


@pytest.fixture
def app(app_with_redirected_marker):
    """Flask app wired to throwaway config/DB, with the marker file redirected
    to a tmp path so this test never touches the real
    ~/.spps_assistant/last_synthesis.json."""
    return app_with_redirected_marker


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
    assert len(list(out_dir.glob('*.xlsx'))) >= 1
    assert 'materials_xlsx' in body['data']
    assert 'materials_pdf' in body['data']


def test_generate_returns_absolute_output_paths_for_a_relative_output_directory(
    app, tmp_path, monkeypatch
):
    """A relative output_directory (e.g. the real 'spps_output' default) must
    resolve to absolute paths in output_paths — the Electron main process
    that later checks these paths runs with a different cwd than this
    sidecar process, so a relative path here would silently fail
    existsSync()/shell.openPath() on the Electron side."""
    monkeypatch.chdir(tmp_path)
    client = app.test_client()

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': 'relative_output'},
    })

    assert resp.status_code == 200
    body = resp.get_json()
    for key in ('cycle_guide_pdf', 'cycle_guide_docx', 'materials_xlsx', 'materials_pdf'):
        path = body['data'][key]
        assert Path(path).is_absolute(), f'{key} is not absolute: {path}'
        assert Path(path).exists()
        assert Path(path).is_relative_to(tmp_path)


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
    assert body['data']['current_cycle'] == 1
    assert 'cycle_guide_pdf' in body['data']['output_paths']
    assert 'cycle_guide_docx' in body['data']['output_paths']
    assert len(body['data']['cycle_guide']['cycles']) == 1
    assert body['data']['cycle_guide']['synthesis_name'] == 'TestRun'


def test_generate_persists_materials_data_in_marker(app, tmp_path):
    """POST /synthesis/generate must persist a real materials view (rows +
    summary stats) in the marker, retrievable via GET /synthesis/last."""
    client = app.test_client()
    out_dir = tmp_path / 'output'

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A', 'G'])],
        'residue_info_map': {
            'A': _residue_payload(311.3, 71.08),
            'G': _residue_payload(297.3, 57.05),
        },
        'config_overrides': {'name': 'MaterialsTest', 'output_directory': str(out_dir)},
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert 'materials_xlsx' in body['data']
    assert 'materials_pdf' in body['data']

    last_resp = client.get('/synthesis/last')
    last_body = last_resp.get_json()
    materials = last_body['data']['materials']
    assert materials['synthesis_name'] == 'MaterialsTest'
    assert materials['total_residue_types'] == 2
    assert len(materials['rows']) == 2
    assert materials['rows'][0]['token'] in ('A', 'G')
    assert isinstance(materials['config_summary'], dict)


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


def test_generate_null_residue_info_map_returns_400(app):
    """Test that residue_info_map: null returns 400, not an unhandled 500."""
    client = app.test_client()

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': None,
    })

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_generate_list_config_overrides_returns_400(app):
    """Test that config_overrides: [] returns 400, not an unhandled 500."""
    client = app.test_client()

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': [],
    })

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_generate_zero_resin_mass_returns_400(app, tmp_path):
    """Test that a vessel with resin_mass_g: 0 returns 400, not a corrupted synthesis."""
    client = app.test_client()
    out_dir = tmp_path / 'output'

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A']) | {'resin_mass_g': 0}],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_generate_negative_resin_mass_returns_400(app, tmp_path):
    """Test that a vessel with negative resin_mass_g returns 400."""
    client = app.test_client()
    out_dir = tmp_path / 'output'

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A']) | {'resin_mass_g': -0.5}],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_generate_target_yield_strategy_backcalculates_resin_mass(app, tmp_path):
    """Verify that target_average strategy actually back-calculates resin mass differently than fixed."""
    from spps_assistant.application.synthesis_guide import determine_resin_mass
    from spps_assistant.domain.models import Vessel, SynthesisConfig
    from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository

    client = app.test_client()
    out_dir = tmp_path / 'output'

    # Create a test vessel and residue to calculate expected resin mass
    test_vessel = Vessel(
        number=1, name='Pep1', original_tokens=['A'], reversed_tokens=['A'],
        resin_mass_g=0.1, substitution_mmol_g=0.3
    )

    # Generate with target strategy
    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {
            'name': 'TargetRun',
            'output_directory': str(out_dir),
            'resin_mass_strategy': 'target_average',
            'target_yield_mg': 50.0,
        },
    })

    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.get_json()}"
    assert len(list(out_dir.glob('*.pdf'))) >= 1

    # Verify that with target strategy, the calculated resin mass differs from the fixed default (0.1)
    # by actually running the domain function to confirm the real behavior
    config_repo = YAMLConfigRepository(tmp_path / 'spps_config.yaml')
    config_repo.save({'resin_mass_strategy': 'target_average', 'target_yield_mg': 50.0})
    config_defaults = config_repo.load()

    from spps_assistant.application.synthesis_guide import build_config_from_defaults
    from spps_assistant.domain.models import ResidueInfo

    config = build_config_from_defaults(config_defaults)

    # Create actual ResidueInfo object for the domain function
    residue_A = ResidueInfo(
        token='A', base_code='A', protection='',
        fmoc_mw=311.3, free_mw=71.08, stock_conc=0.5,
        density_g_ml=None, equivalents_multiplier=1.0
    )
    residue_map = {'A': residue_A}

    calculated_mass = determine_resin_mass(test_vessel, config, residue_map)

    # The calculated mass should be different from the default 0.1g when target_yield_mg is set
    assert calculated_mass > 0, "Back-calculated resin mass should be positive"
    # For a target yield of 50mg, the calculated mass should generally be larger than default
    assert calculated_mass != 0.1 or config.target_yield_mg is None, \
        "Target strategy should produce different resin mass than fixed default"


def test_generate_fixed_strategy_uses_fixed_resin_mass(app, tmp_path):
    """Verify fixed strategy respects the fixed_resin_mass_g value."""
    from spps_assistant.application.synthesis_guide import determine_resin_mass
    from spps_assistant.domain.models import Vessel, ResidueInfo
    from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
    from spps_assistant.application.synthesis_guide import build_config_from_defaults

    client = app.test_client()
    out_dir = tmp_path / 'output'
    fixed_mass = 0.15

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {
            'name': 'FixedRun',
            'output_directory': str(out_dir),
            'resin_mass_strategy': 'fixed',
            'fixed_resin_mass_g': fixed_mass,
        },
    })

    assert resp.status_code == 200
    assert len(list(out_dir.glob('*.pdf'))) >= 1

    # Verify that fixed strategy actually uses the configured fixed_resin_mass_g
    test_vessel = Vessel(
        number=1, name='Pep1', original_tokens=['A'], reversed_tokens=['A'],
        resin_mass_g=0.1, substitution_mmol_g=0.3
    )

    config_repo = YAMLConfigRepository(tmp_path / 'spps_config.yaml')
    config_repo.save({'resin_mass_strategy': 'fixed', 'fixed_resin_mass_g': fixed_mass})
    config_defaults = config_repo.load()

    config = build_config_from_defaults(config_defaults)

    # Create actual ResidueInfo object for the domain function
    residue_A = ResidueInfo(
        token='A', base_code='A', protection='',
        fmoc_mw=311.3, free_mw=71.08, stock_conc=0.5,
        density_g_ml=None, equivalents_multiplier=1.0
    )
    residue_map = {'A': residue_A}

    calculated_mass = determine_resin_mass(test_vessel, config, residue_map)

    # With fixed strategy, resin mass should equal fixed_resin_mass_g
    assert calculated_mass == fixed_mass, \
        f"Fixed strategy should use fixed_resin_mass_g={fixed_mass}, got {calculated_mass}"


def test_generated_at_timestamp_is_utc_aware(app, tmp_path):
    """Verify the marker file's generated_at timestamp is UTC-aware."""
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
    generated_at = body['data']['generated_at']
    # UTC-aware ISO format should include timezone offset (e.g., +00:00)
    assert '+00:00' in generated_at, f"Expected UTC timezone in generated_at, got: {generated_at}"


def test_corrupted_marker_file_returns_500(app, tmp_path, monkeypatch):
    """Test that a corrupted/malformed marker file returns 500, not a crash."""
    import spps_assistant.api.routes.synthesis as synthesis_module

    client = app.test_client()
    out_dir = tmp_path / 'output'
    marker_path = tmp_path / 'last_synthesis.json'

    # Redirect marker path to our tmp location
    monkeypatch.setattr(synthesis_module, '_MARKER_PATH', marker_path)

    # Write invalid JSON to the marker file
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text('{ invalid json', encoding='utf-8')

    resp = client.get('/synthesis/last')

    assert resp.status_code == 500
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'marker_read_failed'


def test_generate_marker_write_failure_returns_200(app, tmp_path, monkeypatch):
    """Test that if marker write fails, synthesis still returns 200 (not 500),
    since the real output files were successfully generated."""
    import os
    import spps_assistant.api.routes.synthesis as synthesis_module

    client = app.test_client()
    out_dir = tmp_path / 'output'

    # Monkeypatch os.replace to raise OSError, simulating a marker write failure
    original_replace = os.replace
    def failing_replace(src, dst):
        if 'last_synthesis' in str(dst):
            raise OSError('Simulated marker write failure')
        return original_replace(src, dst)

    monkeypatch.setattr('os.replace', failing_replace)

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {
            'name': 'TestRun',
            'output_directory': str(out_dir),
            'resin_mass_strategy': 'fixed',
            'fixed_resin_mass_g': 0.1,
        },
    })

    # Despite marker write failure, the response should still be 200 with ok: true
    # because the actual synthesis output was generated successfully
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert 'data' in body
    assert len(body['data']) > 0  # output_paths should be present


def test_set_cycle_position_updates_marker(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A', 'G'])],
        'residue_info_map': {
            'A': _residue_payload(311.3, 71.08),
            'G': _residue_payload(297.3, 57.05),
        },
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 2})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data']['current_cycle'] == 2

    last = client.get('/synthesis/last').get_json()
    assert last['data']['current_cycle'] == 2


def test_set_cycle_position_out_of_range_returns_400(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 99})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_set_cycle_position_zero_returns_400(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 0})

    assert resp.status_code == 400


def test_set_cycle_position_no_synthesis_returns_400(app):
    client = app.test_client()

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 1})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'no_active_synthesis'


def test_set_cycle_position_non_integer_returns_400(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'
    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 'two'})

    assert resp.status_code == 400


def test_set_cycle_position_boolean_returns_400(app, tmp_path):
    """bool is a subclass of int in Python — {"cycle_number": true} must not silently pass."""
    client = app.test_client()
    out_dir = tmp_path / 'output'
    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': True})

    assert resp.status_code == 400


def test_set_cycle_position_corrupted_marker_returns_500(app, tmp_path, monkeypatch):
    """Test that a corrupted/malformed marker file returns 500, not a crash."""
    import spps_assistant.api.routes.synthesis as synthesis_module

    client = app.test_client()
    marker_path = tmp_path / 'last_synthesis.json'

    # Redirect marker path to our tmp location
    monkeypatch.setattr(synthesis_module, '_MARKER_PATH', marker_path)

    # Write invalid JSON to the marker file
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text('{ invalid json', encoding='utf-8')

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 1})

    assert resp.status_code == 500
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'marker_read_failed'


def test_set_cycle_position_marker_write_failure_returns_500(app, tmp_path, monkeypatch):
    """Test that if marker write fails, the cycle-position update returns 500 —
    unlike /synthesis/generate, this route has no real output files to fall
    back on, so a write failure IS the whole operation failing."""
    import os
    import spps_assistant.api.routes.synthesis as synthesis_module

    client = app.test_client()
    out_dir = tmp_path / 'output'

    # Establish real marker state first (no monkeypatch active yet).
    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    # Now monkeypatch os.replace to raise OSError, simulating a marker write failure
    original_replace = os.replace
    def failing_replace(src, dst):
        if 'last_synthesis' in str(dst):
            raise OSError('Simulated marker write failure')
        return original_replace(src, dst)

    monkeypatch.setattr('os.replace', failing_replace)

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 1})

    assert resp.status_code == 500
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'marker_write_failed'


def test_set_cycle_position_malformed_cycle_guide_returns_400(app, tmp_path):
    """A marker with a non-dict 'cycle_guide' (e.g. corrupted data) must be
    treated as zero cycles and rejected with a structured 400, not crash
    with an AttributeError."""
    import json
    import spps_assistant.api.routes.synthesis as synthesis_module

    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    marker_path = synthesis_module._MARKER_PATH
    marker_data = json.loads(marker_path.read_text(encoding='utf-8'))
    marker_data['cycle_guide'] = 'corrupted'
    marker_path.write_text(json.dumps(marker_data), encoding='utf-8')

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 1})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_set_cycle_position_non_list_cycles_returns_400(app, tmp_path):
    """A marker whose 'cycle_guide' is a dict but whose 'cycles' key is not
    a list (e.g. a corrupted string) must be rejected with a structured 400,
    not crash inside len()."""
    import json
    import spps_assistant.api.routes.synthesis as synthesis_module

    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    marker_path = synthesis_module._MARKER_PATH
    marker_data = json.loads(marker_path.read_text(encoding='utf-8'))
    marker_data['cycle_guide']['cycles'] = 'not-a-list'
    marker_path.write_text(json.dumps(marker_data), encoding='utf-8')

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 1})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'
