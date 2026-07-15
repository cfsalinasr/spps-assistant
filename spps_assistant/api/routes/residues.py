"""Residue MW library routes — Step 2 of the New Synthesis wizard."""

import math
from dataclasses import asdict

from flask import Blueprint, current_app, request

from spps_assistant.api.responses import err, ok

residues_bp = Blueprint('residues', __name__)


@residues_bp.get('/residues')
def list_residues():
    """Return every residue MW record in the library."""
    db = current_app.config['DB_REPO']
    return ok(db.list_residues())


@residues_bp.post('/residues')
def save_residue():
    """Upsert a single residue MW record."""
    db = current_app.config['DB_REPO']
    body = request.get_json(silent=True)

    if not isinstance(body, dict) or not body.get('token'):
        return err('invalid_body', 'Request body must include "token"'), 400

    try:
        fmoc_mw = float(body['fmoc_mw'])
        free_mw = float(body['free_mw'])
        if not math.isfinite(fmoc_mw) or fmoc_mw <= 0:
            raise ValueError('fmoc_mw must be a positive finite number')
        if not math.isfinite(free_mw) or free_mw <= 0:
            raise ValueError('free_mw must be a positive finite number')

        token = body['token']
        if not isinstance(token, str):
            raise ValueError('token must be a string')

        base_code = body.get('base_code', token)
        if not isinstance(base_code, str):
            raise ValueError('base_code must be a string')

        protection = body.get('protection', '')
        if not isinstance(protection, str):
            raise ValueError('protection must be a string')

        db.save_residue(
            token=token,
            base_code=base_code,
            protection=protection,
            fmoc_mw=fmoc_mw,
            free_mw=free_mw,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return err('invalid_body', f'Invalid residue record: {exc}'), 400

    saved = db.get_residue(body['token'])
    return ok(asdict(saved))
