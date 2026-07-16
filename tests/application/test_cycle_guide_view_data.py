"""Tests for build_cycle_guide_view_data (application/synthesis_guide.py)."""

import pytest

from spps_assistant.domain.models import (
    CycleGuideViewData, CyclePageData, DispatchRow, GmpStep,
    ResidueInfo, SecondaryCouplingRow, SynthesisConfig, Vessel, VesselAssignment,
)
from spps_assistant.domain.sequence import tokenize
from spps_assistant.application.synthesis_guide import (
    build_coupling_cycles, build_cycle_guide_view_data,
)


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
        name='Test', vessel_label='Vessel', vessel_method='Teabag',
        volume_mode='stoichiometry', activator='HBTU', use_oxyma=True,
        base='DIEA', deprotection_reagent='Piperidine 20%',
        aa_equivalents=3.0, activator_equivalents=3.0, base_equivalents=6.0,
        include_bb_test=True, include_kaiser_test=False,
        starting_vessel_number=1, output_directory='out',
        resin_mass_strategy='fixed', fixed_resin_mass_g=0.1, target_yield_mg=None,
    )
    defaults.update(kwargs)
    return SynthesisConfig(**defaults)


class TestBuildCycleGuideViewData:
    def test_returns_cycle_guide_view_data(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        assert isinstance(result, CycleGuideViewData)
        assert result.synthesis_name == 'Test'
        assert result.date_str == '2026-01-01'

    def test_one_cycle_page_per_coupling_cycle(self):
        v = _vessel(1, 'P1', 'AGW')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data(cycles, config, {}, '2026-01-01')
        assert len(result.cycles) == len(cycles)
        assert all(isinstance(c, CyclePageData) for c in result.cycles)

    def test_cycle_page_numbers_match_coupling_cycles(self):
        v = _vessel(1, 'P1', 'AG')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data(cycles, config, {}, '2026-01-01')
        assert [c.cycle_number for c in result.cycles] == list(range(1, len(cycles) + 1))
        assert all(c.total_cycles == len(cycles) for c in result.cycles)

    def test_empty_cycles_returns_empty_view(self):
        config = _config()
        result = build_cycle_guide_view_data([], config, {}, '2026-01-01')
        assert isinstance(result, CycleGuideViewData)
        assert result.cycles == []

    def test_dispatch_row_uses_residue_info_map_values(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        info = {'A': _info('A', 'A', fmoc_mw=311.3)}
        result = build_cycle_guide_view_data(cycles, config, info, '2026-01-01')
        row = result.cycles[0].dispatch_rows[0]
        assert isinstance(row, DispatchRow)
        assert row.residue_3letter == 'Ala'
        assert row.fmoc_mw == pytest.approx(311.3)
        assert row.vessel_numbers == [1]

    def test_dispatch_row_falls_back_to_fmoc_mw_defaults_when_token_missing(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data(cycles, config, {}, '2026-01-01')
        row = result.cycles[0].dispatch_rows[0]
        assert row.fmoc_mw == pytest.approx(311.3)  # FMOC_MW_DEFAULTS['A']

    def test_dispatch_row_legacy_volume_mode(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(volume_mode='legacy')
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        row = result.cycles[0].dispatch_rows[0]
        assert row.formula_shown == 'V = 1 × 2 mL'

    def test_deprotection_steps_include_bb_test_when_enabled(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(include_bb_test=True)
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        steps = result.cycles[0].deprotection_steps
        assert any('Bromophenol' in s.detail for s in steps)
        assert all(isinstance(s, GmpStep) for s in steps)

    def test_deprotection_steps_omit_bb_test_when_disabled(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(include_bb_test=False)
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        steps = result.cycles[0].deprotection_steps
        assert not any('Bromophenol' in s.detail for s in steps)

    def test_deprotection_steps_include_kaiser_test_when_enabled(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(include_kaiser_test=True)
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        steps = result.cycles[0].deprotection_steps
        assert any('Kaiser' in s.label for s in steps)

    def test_deprotection_reagent_step_checkbox_count(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        assert result.cycles[0].deprotection_steps[0].n_checkboxes == 2
        assert result.cycles[0].deprotection_steps[1].n_checkboxes == 3

    def test_coupling_steps_has_four_repeats_plus_wash(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        steps = result.cycles[0].coupling_steps
        assert len(steps) == 5
        assert steps[0].label == '1st coupling'
        assert steps[-1].label == 'Post-coupling wash'
        assert steps[-1].n_checkboxes == 0

    def test_coupling_step_label_reflects_activator(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(activator='DIC', use_oxyma=True)
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        assert 'DIC' in result.cycles[0].coupling_steps[0].detail

    def test_vessel_assignment_shows_residue_for_active_vessel(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        va = result.cycles[0].vessel_assignments[0]
        assert isinstance(va, VesselAssignment)
        assert va.vessel_number == 1
        assert va.residue_3letter == 'Ala'

    def test_vessel_assignment_shows_none_for_out_vessel(self):
        v1 = _vessel(1, 'P1', 'A')       # 1 residue
        v2 = _vessel(2, 'P2', 'AG')      # 2 residues
        cycles = build_coupling_cycles([v1, v2])
        config = _config()
        info = {'A': _info('A', 'A'), 'G': _info('G', 'G', fmoc_mw=297.3, free_mw=57.05)}
        result = build_cycle_guide_view_data(cycles, config, info, '2026-01-01')
        cycle_2 = result.cycles[1]
        va1 = next(va for va in cycle_2.vessel_assignments if va.vessel_number == 1)
        assert va1.residue_3letter is None

    def test_secondary_coupling_rows_present_for_teabag(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(vessel_method='Teabag')
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        rows = result.cycles[0].secondary_coupling_rows
        assert rows is not None
        assert isinstance(rows[0], SecondaryCouplingRow)
        assert rows[0].residue_3letter == 'Ala'

    def test_secondary_coupling_rows_none_for_non_teabag(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(vessel_method='Column')
        result = build_cycle_guide_view_data(cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        assert result.cycles[0].secondary_coupling_rows is None
