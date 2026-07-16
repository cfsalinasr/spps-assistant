"""Tests for build_materials_view_data (application/materials.py)."""

import pytest

from spps_assistant.domain.models import (
    MaterialsViewData, MaterialsRow, ResidueInfo, SynthesisConfig, Vessel,
)
from spps_assistant.domain.sequence import tokenize
from spps_assistant.application.materials import build_materials_view_data


def _vessel(number, name, seq, resin_mass_g=0.1, sub=0.3):
    tokens = tokenize(seq)
    return Vessel(
        number=number, name=name,
        original_tokens=tokens, reversed_tokens=list(reversed(tokens)),
        resin_mass_g=resin_mass_g, substitution_mmol_g=sub,
    )


def _info(token, base, prot='', fmoc_mw=311.3, free_mw=71.08, stock_conc=0.5):
    return ResidueInfo(
        token=token, base_code=base, protection=prot,
        fmoc_mw=fmoc_mw, free_mw=free_mw, stock_conc=stock_conc,
    )


def _config(**kwargs):
    defaults = dict(
        name='TestRun', vessel_label='Vessel', vessel_method='Teabag',
        volume_mode='stoichiometry', activator='HBTU', use_oxyma=True,
        base='DIEA', deprotection_reagent='Piperidine 20%',
        aa_equivalents=3.0, activator_equivalents=3.0, base_equivalents=6.0,
        include_bb_test=True, include_kaiser_test=False,
        starting_vessel_number=1, output_directory='out',
        resin_mass_strategy='fixed', fixed_resin_mass_g=0.1, target_yield_mg=None,
    )
    defaults.update(kwargs)
    return SynthesisConfig(**defaults)


class TestBuildMaterialsViewData:
    def test_returns_materials_view_data(self):
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        result = build_materials_view_data(
            [v], {'A': _info('A', 'A'), 'G': _info('G', 'G')}, config
        )
        assert isinstance(result, MaterialsViewData)
        assert result.synthesis_name == 'TestRun'

    def test_rows_match_build_materials_rows(self):
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        residue_info_map = {'A': _info('A', 'A'), 'G': _info('G', 'G')}
        result = build_materials_view_data([v], residue_info_map, config)
        assert len(result.rows) == 2
        assert all(isinstance(r, MaterialsRow) for r in result.rows)

    def test_total_residue_types_matches_row_count(self):
        v = _vessel(1, 'P1', 'AGW')
        config = _config()
        residue_info_map = {
            'A': _info('A', 'A'), 'G': _info('G', 'G'), 'W': _info('W', 'W'),
        }
        result = build_materials_view_data([v], residue_info_map, config)
        assert result.total_residue_types == len(result.rows) == 3

    def test_total_mass_mg_is_sum_of_row_masses(self):
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        residue_info_map = {'A': _info('A', 'A'), 'G': _info('G', 'G')}
        result = build_materials_view_data([v], residue_info_map, config)
        expected = round(sum(r.mass_mg for r in result.rows), 2)
        assert result.total_mass_mg == expected

    def test_total_volume_ml_is_sum_of_row_volumes(self):
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        residue_info_map = {'A': _info('A', 'A'), 'G': _info('G', 'G')}
        result = build_materials_view_data([v], residue_info_map, config)
        expected = round(sum(r.volume_ml for r in result.rows), 3)
        assert result.total_volume_ml == expected

    def test_config_summary_has_string_values(self):
        v = _vessel(1, 'P1', 'A')
        config = _config(activator='DIC', aa_equivalents=5.0)
        result = build_materials_view_data([v], {'A': _info('A', 'A')}, config)
        assert result.config_summary['Activator'] == 'DIC'
        assert result.config_summary['AA Equivalents'] == '5.0'
        assert all(isinstance(v, str) for v in result.config_summary.values())

    def test_empty_vessels_returns_empty_view(self):
        config = _config()
        result = build_materials_view_data([], {}, config)
        assert result.rows == []
        assert result.total_residue_types == 0
        assert result.total_mass_mg == 0
        assert result.total_volume_ml == 0

    def test_unresolved_residue_is_skipped_not_crashed(self):
        """A token missing from residue_info_map is silently skipped by
        build_materials_rows (existing behavior) — the view data must not
        crash, and total_residue_types must reflect only resolved rows."""
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        result = build_materials_view_data([v], {'A': _info('A', 'A')}, config)
        assert result.total_residue_types == 1
