"""YAML-backed implementation of the ConfigRepository port."""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from spps_assistant.application.ports import ConfigRepository

# Default config location
_CONFIG_DIR = Path.home() / '.spps_assistant'
_CONFIG_PATH = _CONFIG_DIR / 'spps_config.yaml'

_DEFAULTS: Dict[str, Any] = {
    'name': 'MySynthesis',
    'vessel_label': 'Vessel',
    'vessel_method': 'Teabag',
    'volume_mode': 'stoichiometry',
    'activator': 'HBTU',
    'use_oxyma': True,
    'base': 'DIEA',
    'deprotection_reagent': 'Piperidine 20%',
    'aa_equivalents': 3.0,
    'activator_equivalents': 3.0,
    'base_equivalents': 6.0,
    'include_bb_test': True,
    'include_kaiser_test': False,
    'starting_vessel_number': 1,
    'output_directory': 'spps_output',
    'resin_mass_strategy': 'fixed',
    'fixed_resin_mass_g': 0.1,
    'target_yield_mg': None,
}


def _ensure_config(config_path: Path = _CONFIG_PATH) -> None:
    """Create config file with defaults if it does not exist."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(_DEFAULTS, f, default_flow_style=False, allow_unicode=True)


# Auto-initialize on module import
_ensure_config()


class YAMLConfigRepository(ConfigRepository):
    """YAML-file backed implementation of ConfigRepository.

    Config is stored at ~/.spps_assistant/spps_config.yaml by default.
    Missing keys fall back to built-in defaults.
    """

    def __init__(self, config_path: Path = _CONFIG_PATH):
        """Initialise the repository and ensure the config file exists on disk."""
        self._path = Path(config_path)
        _ensure_config(self._path)

    def load(self) -> Dict[str, Any]:
        """Load config from YAML, merging with defaults for missing keys."""
        with open(self._path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        # Merge: defaults first, then file values override
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged

    def save(self, config_dict: Dict[str, Any]) -> None:
        """Persist config dict to YAML."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

    def get_field(self, field: str) -> Any:
        """Get a single config field value."""
        data = self.load()
        return data.get(field, _DEFAULTS.get(field))

    def set_field(self, field: str, value: Any) -> None:
        """Set a single config field and persist."""
        data = self.load()
        data[field] = value
        self.save(data)
