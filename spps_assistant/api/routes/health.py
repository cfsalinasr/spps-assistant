"""Health-check route — lets a parent process confirm the sidecar is alive."""

from flask import Blueprint

from spps_assistant import __version__
from spps_assistant.api.responses import ok

health_bp = Blueprint('health', __name__)


@health_bp.get('/health')
def health():
    """Return a fixed ok envelope confirming the sidecar is responsive."""
    return ok({"status": "ok", "version": __version__})
