"""Synthesis-defaults configuration routes."""

from flask import Blueprint, current_app, request

from spps_assistant.api.responses import err, ok

config_bp = Blueprint('config', __name__)


@config_bp.get('/config')
def get_config():
    """Return the current synthesis defaults."""
    repo = current_app.config['CONFIG_REPO']
    return ok(repo.load())


@config_bp.post('/config')
def set_config():
    """Persist a full synthesis-defaults dict and return the saved result."""
    repo = current_app.config['CONFIG_REPO']
    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        return err('invalid_body', 'Request body must be a JSON object'), 400

    repo.save(body)
    return ok(repo.load())
