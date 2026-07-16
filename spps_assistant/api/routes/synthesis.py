"""Synthesis generation routes — final steps of the New Synthesis wizard."""

import json
import logging
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, request

from spps_assistant.api.responses import err, ok
from spps_assistant.domain.models import ResidueInfo, Vessel

logger = logging.getLogger(__name__)

synthesis_bp = Blueprint('synthesis', __name__)

_MARKER_PATH = Path.home() / '.spps_assistant' / 'last_synthesis.json'


def _vessel_from_dict(data: dict) -> Vessel:
    resin_mass_g = float(data.get('resin_mass_g', 0.1))
    substitution_mmol_g = float(data.get('substitution_mmol_g', 0.3))
    if resin_mass_g <= 0:
        raise ValueError('Vessel field must be positive: resin_mass_g must be > 0')
    if substitution_mmol_g <= 0:
        raise ValueError('Vessel field must be positive: substitution_mmol_g must be > 0')
    return Vessel(
        number=data['number'],
        name=data['name'],
        original_tokens=data['original_tokens'],
        reversed_tokens=data['reversed_tokens'],
        resin_mass_g=resin_mass_g,
        substitution_mmol_g=substitution_mmol_g,
    )


def _residue_info_from_dict(token: str, data: dict) -> ResidueInfo:
    fmoc_mw = float(data['fmoc_mw'])
    free_mw = float(data['free_mw'])
    stock_conc = float(data.get('stock_conc', 0.5))
    if fmoc_mw <= 0:
        raise ValueError(f'Residue field must be positive: {token} fmoc_mw must be > 0')
    if free_mw <= 0:
        raise ValueError(f'Residue field must be positive: {token} free_mw must be > 0')
    if stock_conc <= 0:
        raise ValueError(f'Residue field must be positive: {token} stock_conc must be > 0')
    return ResidueInfo(
        token=token,
        base_code=data.get('base_code', token),
        protection=data.get('protection', ''),
        fmoc_mw=fmoc_mw,
        free_mw=free_mw,
        stock_conc=stock_conc,
        density_g_ml=data.get('density_g_ml'),
        equivalents_multiplier=float(data.get('equivalents_multiplier', 1.0)),
    )


@synthesis_bp.post('/synthesis/generate')
def generate_synthesis():
    """Run the full synthesis guide generation workflow and write real output files."""
    from spps_assistant.application.synthesis_guide import (
        SynthesisGuideUseCase, apply_target_resin_mass,
        build_config_from_defaults, calc_yields_and_solubility,
    )

    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get('vessels'):
        return err('invalid_body', 'Request body must include "vessels"'), 400

    residue_info_payload = body.get('residue_info_map', {})
    config_overrides = body.get('config_overrides', {})
    if not isinstance(residue_info_payload, dict) or not isinstance(config_overrides, dict):
        return err('invalid_body', 'residue_info_map and config_overrides must be objects'), 400

    try:
        vessels = [_vessel_from_dict(v) for v in body['vessels']]
        residue_info_map = {
            token: _residue_info_from_dict(token, data)
            for token, data in residue_info_payload.items()
        }
    except (KeyError, TypeError, ValueError) as exc:
        return err('invalid_body', f'Invalid vessel or residue data: {exc}'), 400

    config_repo = current_app.config['CONFIG_REPO']
    db = current_app.config['DB_REPO']
    merged_defaults = {**config_repo.load(), **config_overrides}

    try:
        config = build_config_from_defaults(merged_defaults)
    except ValueError as exc:
        return err('invalid_config', str(exc)), 400

    if config.resin_mass_strategy != 'fixed' and config.target_yield_mg:
        try:
            apply_target_resin_mass(vessels, config, residue_info_map)
        except ValueError as exc:
            return err('resin_mass_failed', str(exc)), 400

    yield_results, solubility_results = calc_yields_and_solubility(vessels, residue_info_map)

    use_case = SynthesisGuideUseCase(db=db, config_repo=config_repo)
    try:
        output_paths, cycle_guide_data = use_case.run(
            output_dir=config.output_directory,
            config=config,
            residue_info_map=residue_info_map,
            vessels=vessels,
            yield_results=yield_results,
            solubility_results=solubility_results,
        )
    except Exception as exc:  # noqa: BLE001 - surface any generation failure to the caller
        logger.exception('Synthesis generation failed')
        return err('generate_failed', 'Synthesis generation failed. Check server logs for details.'), 500

    _MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        'name': config.name,
        'output_directory': config.output_directory,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'vessel_count': len(vessels),
        'output_paths': output_paths,
        'current_cycle': 1,
        'cycle_guide': asdict(cycle_guide_data),
    }

    tmp_path = None
    try:
        # Write atomically: temp file in the same directory, then rename.
        # This prevents partial/corrupted marker files on write interruption.
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=_MARKER_PATH.parent,
            delete=False,
            encoding='utf-8',
            suffix='.tmp',
        ) as tmp_file:
            tmp_path = tmp_file.name
            json.dump(marker_data, tmp_file)

        os.replace(tmp_path, _MARKER_PATH)
        tmp_path = None  # replaced successfully, nothing left to clean up
    except OSError:
        # Marker write failed, but synthesis generation succeeded.
        # Log the failure server-side but return success to client
        # since the real output files were genuinely created.
        logger.exception('Failed to write synthesis marker file')
    finally:
        # os.replace() failing (or never being reached) leaves the temp
        # file behind — clean it up so repeated failures don't leak files.
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning('Failed to remove temporary synthesis marker file', exc_info=True)

    return ok(output_paths)


@synthesis_bp.get('/synthesis/last')
def last_synthesis():
    """Return the most recently generated synthesis's marker data, if any."""
    if not _MARKER_PATH.exists():
        return ok(None)
    try:
        marker_data = json.loads(_MARKER_PATH.read_text(encoding='utf-8'))
        return ok(marker_data)
    except (json.JSONDecodeError, OSError) as exc:
        logger.exception('Failed to read last synthesis marker')
        return err('marker_read_failed', 'Could not read the last synthesis marker.'), 500
