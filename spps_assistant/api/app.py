"""Flask app factory for the SPPS Assistant API sidecar."""

import hmac
from typing import Any, Dict, Optional, Tuple

from flask import Flask, request

from spps_assistant.api.responses import err
from spps_assistant.api.routes.config import config_bp
from spps_assistant.api.routes.health import health_bp
from spps_assistant.application.ports import ConfigRepository

AUTH_HEADER = 'X-SPPS-Sidecar-Token'


def create_app(
    config_repo: Optional[ConfigRepository] = None,
    auth_token: Optional[str] = None,
) -> Flask:
    """Build and configure the Flask application.

    Args:
        config_repo: ConfigRepository implementation to use for /config
            routes. Defaults to a real YAMLConfigRepository (constructed
            lazily to avoid importing infrastructure at module load time
            for routes that don't need it).
        auth_token: shared-secret token required on the X-SPPS-Sidecar-Token
            header of every request. When None (the default, used by tests
            and any direct create_app() call), no authentication is
            enforced. The real entrypoint (spps_assistant.api.__main__)
            always passes a randomly generated token, so every real
            deployment is protected — only direct create_app() usage is
            open by default.
    """
    app = Flask(__name__)

    if config_repo is None:
        from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
        config_repo = YAMLConfigRepository()
    app.config['CONFIG_REPO'] = config_repo

    if auth_token is not None:
        @app.before_request
        def _require_sidecar_token() -> Optional[Tuple[Dict[str, Any], int]]:
            if not hmac.compare_digest(request.headers.get(AUTH_HEADER, ''), auth_token):
                return err('unauthorized', 'Missing or invalid sidecar token'), 401
            return None

    app.register_blueprint(health_bp)
    app.register_blueprint(config_bp)

    return app
