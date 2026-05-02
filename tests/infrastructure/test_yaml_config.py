"""Tests for infrastructure/yaml_config.py."""

import pytest
import yaml

from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository


@pytest.fixture
def config_repo(tmp_path):
    """Provide a YAMLConfigRepository backed by a tmp config file."""
    config_path = tmp_path / 'spps_config.yaml'
    return YAMLConfigRepository(config_path=config_path)


# ── _ensure_config / init ─────────────────────────────────────────────────────

class TestInit:
    def test_creates_config_file_if_missing(self, tmp_path):
        """Config file is created when it does not exist yet."""
        config_path = tmp_path / 'new' / 'spps_config.yaml'
        YAMLConfigRepository(config_path=config_path)
        assert config_path.exists()

    def test_does_not_overwrite_existing(self, tmp_path):
        """Existing config values are preserved on re-init."""
        config_path = tmp_path / 'spps_config.yaml'
        config_path.write_text(yaml.dump({'activator': 'DIC'}), encoding='utf-8')
        repo = YAMLConfigRepository(config_path=config_path)
        data = repo.load()
        assert data['activator'] == 'DIC'


# ── load ──────────────────────────────────────────────────────────────────────

class TestLoad:
    def test_load_returns_dict(self, config_repo):
        """load() returns a dict."""
        data = config_repo.load()
        assert isinstance(data, dict)

    def test_load_has_default_activator(self, config_repo):
        """Default activator is HBTU."""
        data = config_repo.load()
        assert data['activator'] == 'HBTU'

    def test_load_merges_defaults_for_missing_keys(self, tmp_path):
        """Missing keys are filled from built-in defaults on load."""
        config_path = tmp_path / 'partial.yaml'
        config_path.write_text(yaml.dump({'activator': 'DIC'}), encoding='utf-8')
        repo = YAMLConfigRepository(config_path=config_path)
        data = repo.load()
        # 'base' is not in the file but should come from defaults
        assert data['base'] == 'DIEA'
        assert data['activator'] == 'DIC'

    def test_load_handles_empty_yaml(self, tmp_path):
        """Empty YAML file is treated as all-defaults."""
        config_path = tmp_path / 'empty.yaml'
        config_path.write_text('', encoding='utf-8')
        repo = YAMLConfigRepository(config_path=config_path)
        data = repo.load()
        assert data['activator'] == 'HBTU'

    def test_all_default_keys_present(self, config_repo):
        """All expected default keys are present after load."""
        data = config_repo.load()
        expected_keys = [
            'name', 'vessel_label', 'vessel_method', 'volume_mode',
            'activator', 'use_oxyma', 'base', 'deprotection_reagent',
            'aa_equivalents', 'activator_equivalents', 'base_equivalents',
            'include_bb_test', 'include_kaiser_test', 'starting_vessel_number',
            'output_directory', 'resin_mass_strategy', 'fixed_resin_mass_g',
            'target_yield_mg',
        ]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"


# ── save ──────────────────────────────────────────────────────────────────────

class TestSave:
    def test_save_persists_data(self, config_repo, tmp_path):
        """Saved data survives a reload."""
        data = config_repo.load()
        data['activator'] = 'DIC'
        config_repo.save(data)
        reloaded = config_repo.load()
        assert reloaded['activator'] == 'DIC'

    def test_save_creates_parent_dirs(self, tmp_path):
        """save() creates intermediate directories as needed."""
        config_path = tmp_path / 'nested' / 'dir' / 'config.yaml'
        repo = YAMLConfigRepository(config_path=config_path)
        data = repo.load()
        data['activator'] = 'DIC'
        repo.save(data)
        assert config_path.exists()


# ── get_field / set_field ─────────────────────────────────────────────────────

class TestGetSetField:
    def test_get_field_returns_default(self, config_repo):
        """get_field returns the default value for a known key."""
        assert config_repo.get_field('activator') == 'HBTU'

    def test_set_field_persists(self, config_repo):
        """set_field persists the new value to disk."""
        config_repo.set_field('activator', 'PyBOP')
        assert config_repo.get_field('activator') == 'PyBOP'

    def test_get_field_missing_key_returns_none(self, config_repo):
        """get_field returns None for an unknown key."""
        assert config_repo.get_field('nonexistent_field') is None

    def test_set_field_numeric(self, config_repo):
        """Numeric value is stored and retrieved correctly."""
        config_repo.set_field('aa_equivalents', 4.0)
        assert config_repo.get_field('aa_equivalents') == pytest.approx(4.0)

    def test_set_field_bool(self, config_repo):
        """Boolean value is stored and retrieved correctly."""
        config_repo.set_field('include_kaiser_test', True)
        assert config_repo.get_field('include_kaiser_test') is True

    def test_set_field_none(self, config_repo):
        """None value is stored and retrieved correctly."""
        config_repo.set_field('target_yield_mg', None)
        assert config_repo.get_field('target_yield_mg') is None
