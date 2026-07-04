"""Flask app factory for the SPPS Assistant API sidecar."""

from typing import Optional

from flask import Flask

from spps_assistant.api.routes.health import health_bp
from spps_assistant.application.ports import ConfigRepository


def create_app(config_repo: Optional[ConfigRepository] = None) -> Flask:
    """Build and configure the Flask application.

    Args:
        config_repo: ConfigRepository implementation to use for /config
            routes. Defaults to a real YAMLConfigRepository (constructed
            lazily to avoid importing infrastructure at module load time
            for routes that don't need it).
    """
    app = Flask(__name__)

    if config_repo is None:
        from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
        config_repo = YAMLConfigRepository()
    app.config['CONFIG_REPO'] = config_repo

    app.register_blueprint(health_bp)

    return app
