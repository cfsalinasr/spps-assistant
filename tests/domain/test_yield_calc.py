"""Tests for domain.yield_calc module."""

import pytest

from spps_assistant.domain.yield_calc import (
    calc_peptide_mw,
    calc_theoretical_yield,
    back_calc_resin_mass,
    build_yield_formula,
)
from spps_assistant.domain.constants import FREE_RESIDUE_MW


def test_peptide_mw_simple():
    """GWMQ: sum of free residue MWs + H2O."""
    # G=57.05, W=186.21, M=131.20, Q=128.13, H2O=18.0152
    # Total = 520.6052
    tokens = ['G', 'W', 'M', 'Q']
    mw = calc_peptide_mw(tokens, FREE_RESIDUE_MW, {})
    expected = 57.05 + 186.21 + 131.20 + 128.13 + 18.0152
    assert abs(mw - expected) < 0.01


def test_peptide_mw_adds_water():
    """Single amino acid: residue MW + H2O."""
    mw = calc_peptide_mw(['A'], FREE_RESIDUE_MW, {})
    expected = 71.08 + 18.0152
    assert abs(mw - expected) < 0.01


def test_peptide_mw_uses_residue_info_map():
    """residue_info_map overrides free_residue_mw for known tokens."""
    from spps_assistant.domain.models import ResidueInfo
    residue_info_map = {
        'A': ResidueInfo(token='A', base_code='A', protection='',
                         fmoc_mw=311.3, free_mw=99.99)  # custom MW
    }
    mw = calc_peptide_mw(['A'], FREE_RESIDUE_MW, residue_info_map)
    expected = 99.99 + 18.0152
    assert abs(mw - expected) < 0.01


def test_peptide_mw_unknown_residue():
    """Unknown residue X gets average MW 111.10."""
    mw = calc_peptide_mw(['X'], FREE_RESIDUE_MW, {})
    expected = 111.10 + 18.0152
    assert abs(mw - expected) < 0.01


def test_peptide_mw_empty_sequence():
    """Empty sequence returns just H2O."""
    mw = calc_peptide_mw([], FREE_RESIDUE_MW, {})
    assert abs(mw - 18.0152) < 0.01


def test_theoretical_yield():
    """Yield formula: resin_mass * sub * (0.98^length) * peptide_mw."""
    # resin 0.1g, sub 0.3 mmol/g, length 8, mw 1000 g/mol
    # resin_mmol = 0.03
    # yield = 0.03 * (0.98^8) * 1000 = 25.52...mg
    y = calc_theoretical_yield(0.1, 0.3, 8, 1000.0)
    expected = 0.1 * 0.3 * (0.98 ** 8) * 1000.0
    assert abs(y - expected) < 0.01


def test_theoretical_yield_zero_length():
    """Length 0 gives 100% efficiency (0.98^0 = 1.0)."""
    y = calc_theoretical_yield(0.1, 0.3, 0, 1000.0)
    expected = 0.1 * 0.3 * 1.0 * 1000.0
    assert abs(y - expected) < 0.01


def test_theoretical_yield_longer_sequence_less_yield():
    """Longer sequence gives lower yield (0.98^n decreases)."""
    y5 = calc_theoretical_yield(0.1, 0.3, 5, 1000.0)
    y20 = calc_theoretical_yield(0.1, 0.3, 20, 1000.0)
    assert y5 > y20


def test_back_calc_resin_mass():
    """back_calc inverts calc_theoretical_yield."""
    target = 10.0  # mg
    sub = 0.3
    length = 10
    mw = 1200.0

    resin_mass = back_calc_resin_mass(target, sub, length, mw)
    # Verify round-trip
    recovered_yield = calc_theoretical_yield(resin_mass, sub, length, mw)
    assert abs(recovered_yield - target) < 0.01


def test_back_calc_raises_on_zero_denominator():
    """back_calc raises ValueError if denominator is zero."""
    with pytest.raises(ValueError):
        back_calc_resin_mass(10.0, 0.0, 10, 1200.0)


def test_build_yield_formula_string():
    """build_yield_formula returns a non-empty string with expected values."""
    formula = build_yield_formula(0.1, 0.3, 8, 1000.0, 25.52)
    assert '0.1' in formula or '0.1000' in formula
    assert '0.3' in formula
    assert '1000' in formula
    assert len(formula) > 10
