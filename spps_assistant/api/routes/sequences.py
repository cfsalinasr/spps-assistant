"""Sequence parsing route — Step 1 of the New Synthesis wizard."""

from dataclasses import asdict
from pathlib import Path

from flask import Blueprint, current_app, request

from spps_assistant.api.responses import err, ok

sequences_bp = Blueprint('sequences', __name__)


@sequences_bp.post('/sequences/parse')
def parse_sequences():
    """Parse a FASTA file (and optional materials file) into vessels."""
    from spps_assistant.application.sequence_loader import (
        build_vessels, load_materials_map, parse_and_validate_sequences,
    )

    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get('fasta_path'):
        return err('invalid_body', 'Request body must include "fasta_path"'), 400

    fasta_path = body['fasta_path']
    materials_path = body.get('materials_path')

    config_repo = current_app.config['CONFIG_REPO']
    config_defaults = config_repo.load()
    starting_num = int(config_defaults.get('starting_vessel_number', 1))
    substitution_mmol_g = float(config_defaults.get('substitution_mmol_g', 0.3))

    try:
        parsed_sequences = parse_and_validate_sequences(Path(fasta_path))
    except ValueError as exc:
        return err('parse_failed', str(exc)), 400

    vessels = build_vessels(
        parsed_sequences, starting_num, substitution_mmol_g=substitution_mmol_g,
    )

    data = {
        'vessels': [
            {
                'number': v.number,
                'name': v.name,
                'original_tokens': v.original_tokens,
                'reversed_tokens': v.reversed_tokens,
                'resin_mass_g': v.resin_mass_g,
                'substitution_mmol_g': v.substitution_mmol_g,
            }
            for v in vessels
        ]
    }

    if materials_path:
        try:
            materials_map = load_materials_map(Path(materials_path))
        except ValueError as exc:
            return err('materials_parse_failed', str(exc)), 400
        data['materials_residue_map'] = {
            token: asdict(info) for token, info in materials_map.items()
        }

    return ok(data)
