"""Shared fixtures for all API route tests."""

import pytest

from spps_assistant.api.app import create_app
from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository


@pytest.fixture
def db(tmp_path):
    """Temporary SQLite database for test isolation."""
    db_path = tmp_path / 'spps_database.db'
    return SQLiteRepository(db_path)


@pytest.fixture
def config_repo(tmp_path):
    """Temporary YAML config repository for test isolation."""
    config_path = tmp_path / 'spps_config.yaml'
    return YAMLConfigRepository(config_path)


@pytest.fixture
def app_with_db(tmp_path):
    """Flask app wired to a throwaway SQLite DB, not the real user database."""
    db_path = tmp_path / 'spps_database.db'
    db = SQLiteRepository(db_path)
    return create_app(db=db)


@pytest.fixture
def app_with_config_and_db(tmp_path):
    """Flask app wired to throwaway config/DB, not the real user config or database."""
    config_path = tmp_path / 'spps_config.yaml'
    db_path = tmp_path / 'spps_database.db'
    config_repo = YAMLConfigRepository(config_path)
    db = SQLiteRepository(db_path)
    return create_app(config_repo=config_repo, db=db)


@pytest.fixture
def app_with_redirected_marker(tmp_path, monkeypatch):
    """Flask app wired to throwaway config/DB, with the marker file redirected
    to a tmp path so tests never touch the real ~/.spps_assistant/last_synthesis.json."""
    import spps_assistant.api.routes.synthesis as synthesis_module

    config_path = tmp_path / 'spps_config.yaml'
    db_path = tmp_path / 'spps_database.db'
    marker_path = tmp_path / 'last_synthesis.json'
    monkeypatch.setattr(synthesis_module, '_MARKER_PATH', marker_path)

    config_repo = YAMLConfigRepository(config_path)
    db = SQLiteRepository(db_path)
    return create_app(config_repo=config_repo, db=db)
