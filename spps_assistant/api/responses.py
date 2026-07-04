"""Shared response envelope helpers for all API routes.

Every route in spps_assistant.api must return JSON shaped by one of these
two helpers so the frontend can rely on a single, consistent envelope:
  success -> {"ok": true, "data": <...>}
  failure -> {"ok": false, "error": {"code": "...", "message": "..."}}
"""

from typing import Any, Dict


def ok(data: Any) -> Dict[str, Any]:
    """Build a success envelope wrapping the given data."""
    return {"ok": True, "data": data}


def err(code: str, message: str) -> Dict[str, Any]:
    """Build a failure envelope with a machine-readable code and a message."""
    return {"ok": False, "error": {"code": code, "message": message}}
