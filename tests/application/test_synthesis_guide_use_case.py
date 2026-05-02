"""Tests for application/synthesis_guide.py."""

import pytest

from spps_assistant.domain.models import (
    CouplingCycle, ResidueInfo, SynthesisConfig, Vessel
)
from spps_assistant.domain.sequence import tokenize
from spps_assistant.application.synthesis_guide import (
    build_coupling_cycles, determine_resin_mass
)


def _vessel(number, name, seq, resin_mass_g=0.1, sub=0.3):
    """Build a minimal Vessel from a single-letter sequence string."""
    tokens = tokenize(seq)
    return Vessel(
        number=number, name=name,
        original_tokens=tokens,
        reversed_tokens=list(reversed(tokens)),
        resin_mass_g=resin_mass_g,
        substitution_mmol_g=sub,
    )


def _info(token, base, prot='', fmoc_mw=311.3, free_mw=71.08):
    """Build a minimal ResidueInfo for testing."""
    return ResidueInfo(
        token=token, base_code=base, protection=prot,
        fmoc_mw=fmoc_mw, free_mw=free_mw, stock_conc=0.5,
    )


def _config(**kwargs):
    """Build a SynthesisConfig with sensible test defaults."""
    defaults = dict(
        name='Test', resin_mass_strategy='fixed', fixed_resin_mass_g=0.1,
        target_yield_mg=None, aa_equivalents=3.0,
        activator_equivalents=3.0, base_equivalents=6.0,
        volume_mode='stoichiometry', activator='HBTU', base='DIEA',
    )
    defaults.update(kwargs)
    return SynthesisConfig(**defaults)


# ── build_coupling_cycles ────────────────────────────────────────────────────

class TestBuildCouplingCycles:
    def test_empty_vessels_returns_empty(self):
        """Empty vessel list yields no coupling cycles."""
        assert build_coupling_cycles([]) == []

    def test_single_residue_vessel_one_cycle(self):
        """Single-residue vessel produces exactly one coupling cycle."""
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        assert len(cycles) == 1

    def test_cycle_count_equals_longest_sequence(self):
        """Cycle count equals the length of the longest sequence."""
        v1 = _vessel(1, 'P1', 'AGW')   # 3 residues
        v2 = _vessel(2, 'P2', 'ACGK')  # 4 residues
        cycles = build_coupling_cycles([v1, v2])
        assert len(cycles) == 4

    def test_cycle_numbers_are_sequential(self):
        """Cycle numbers run from 1 to total_cycles without gaps."""
        v = _vessel(1, 'P1', 'AGW')
        cycles = build_coupling_cycles([v])
        nums = [c.cycle_number for c in cycles]
        assert nums == [1, 2, 3]

    def test_cycle_total_cycles_correct(self):
        """Each cycle's total_cycles attribute reflects the full run length."""
        v = _vessel(1, 'P1', 'AGW')
        cycles = build_coupling_cycles([v])
        assert all(c.total_cycles == 3 for c in cycles)

    def test_residues_at_position_reversed(self):
        """SPPS reversal: first coupling cycle couples the C-terminal residue."""
        # Sequence AGW reversed for SPPS is WGA
        # Cycle 1 should couple W (last residue in original)
        v = _vessel(1, 'P1', 'AGW')
        cycles = build_coupling_cycles([v])
        # Vessel's reversed_tokens = ['W', 'G', 'A']
        assert 'W' in cycles[0].residues_at_position
        assert 1 in cycles[0].residues_at_position['W']

    def test_two_vessels_same_residue_grouped(self):
        """Both vessel numbers appear under the shared residue in cycle 1."""
        v1 = _vessel(1, 'P1', 'A')
        v2 = _vessel(2, 'P2', 'A')
        cycles = build_coupling_cycles([v1, v2])
        assert 1 in cycles[0].residues_at_position['A']
        assert 2 in cycles[0].residues_at_position['A']

    def test_vessels_shorter_than_longest_end_early(self):
        """Shorter sequences do not contribute to cycles beyond their length."""
        v1 = _vessel(1, 'P1', 'A')     # 1 residue
        v2 = _vessel(2, 'P2', 'AGW')   # 3 residues
        cycles = build_coupling_cycles([v1, v2])
        assert len(cycles) == 3
        # Cycle 2: vessel 1 is done, only vessel 2 has a residue
        cycle_2_vessels = set()
        for tok, vessels in cycles[1].residues_at_position.items():
            cycle_2_vessels.update(vessels)
        assert 1 not in cycle_2_vessels
        assert 2 in cycle_2_vessels

    def test_cycle_contains_all_vessels_reference(self):
        """all_vessels list on each cycle contains every input vessel."""
        v1 = _vessel(1, 'P1', 'A')
        v2 = _vessel(2, 'P2', 'A')
        cycles = build_coupling_cycles([v1, v2])
        assert len(cycles[0].all_vessels) == 2

    def test_returns_coupling_cycle_objects(self):
        """Return type is CouplingCycle."""
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        assert isinstance(cycles[0], CouplingCycle)


# ── determine_resin_mass ──────────────────────────────────────────────────────

class TestDetermineResinMass:
    def test_fixed_strategy_returns_fixed_mass(self):
        """Fixed strategy returns the configured fixed resin mass."""
        v = _vessel(1, 'P1', 'A')
        config = _config(resin_mass_strategy='fixed', fixed_resin_mass_g=0.15)
        mass = determine_resin_mass(v, config, {})
        assert mass == pytest.approx(0.15)

    def test_target_strategy_no_target_returns_fixed(self):
        """Target strategy without a target falls back to fixed mass."""
        v = _vessel(1, 'P1', 'A')
        config = _config(resin_mass_strategy='target', target_yield_mg=None,
                         fixed_resin_mass_g=0.1)
        mass = determine_resin_mass(v, config, {})
        assert mass == pytest.approx(0.1)

    def test_target_strategy_back_calculates(self):
        """Target strategy back-calculates a positive resin mass from yield target."""
        v = _vessel(1, 'P1', 'A')
        info = {'A': _info('A', 'A', fmoc_mw=311.3, free_mw=71.08)}
        config = _config(
            resin_mass_strategy='target',
            target_yield_mg=5.0,
            fixed_resin_mass_g=0.1,
        )
        mass = determine_resin_mass(v, config, info)
        assert mass > 0
