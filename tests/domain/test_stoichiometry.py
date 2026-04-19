"""Tests for domain.stoichiometry module."""

import pytest

from spps_assistant.domain.stoichiometry import (
    calc_volume_stoichiometry,
    calc_volume_legacy,
    calc_activator_volume,
    calc_base_volume,
    calc_mass_mg,
    format_volume_formula,
)


def test_legacy_volume_matches_spys():
    """Legacy mode: 2 mL per vessel, matches original Spys.pl."""
    assert calc_volume_legacy(2) == 4.0   # '4 ml TRP: 2,3' in Spys.pl
    assert calc_volume_legacy(1) == 2.0
    assert calc_volume_legacy(0) == 0.0


def test_legacy_volume_large():
    assert calc_volume_legacy(10) == 20.0


def test_stoichiometry_volume():
    """V = (n_vessels * equivalents * resin_mmol) / stock_conc_M."""
    # 1 vessel, 3 eq, 0.1g * 0.3mmol/g = 0.03mmol, 0.5M stock
    # V = (1 * 3 * 0.03) / 0.5 = 0.18 mL
    result = calc_volume_stoichiometry(1, 3.0, 0.03, 0.5)
    assert abs(result - 0.18) < 1e-9


def test_stoichiometry_volume_multi_vessel():
    """Multiple vessels scale linearly."""
    v1 = calc_volume_stoichiometry(1, 3.0, 0.03, 0.5)
    v3 = calc_volume_stoichiometry(3, 3.0, 0.03, 0.5)
    assert abs(v3 - 3 * v1) < 1e-9


def test_stoichiometry_volume_zero_conc_raises():
    """Zero stock concentration raises ValueError."""
    with pytest.raises(ValueError):
        calc_volume_stoichiometry(1, 3.0, 0.03, 0.0)


def test_stoichiometry_volume_higher_equivalents():
    """Higher equivalents gives proportionally larger volume."""
    v3 = calc_volume_stoichiometry(1, 3.0, 0.03, 0.5)
    v6 = calc_volume_stoichiometry(1, 6.0, 0.03, 0.5)
    assert abs(v6 - 2 * v3) < 1e-9


def test_activator_volume():
    """Activator volume uses same formula as stoichiometry."""
    v = calc_activator_volume(2, 3.0, 0.03, 0.5)
    expected = calc_volume_stoichiometry(2, 3.0, 0.03, 0.5)
    assert abs(v - expected) < 1e-9


def test_base_volume():
    """Base volume uses same formula as stoichiometry."""
    v = calc_base_volume(1, 6.0, 0.03, 2.0)
    expected = calc_volume_stoichiometry(1, 6.0, 0.03, 2.0)
    assert abs(v - expected) < 1e-9


def test_mass_mg():
    """mass_mg = mmol * fmoc_mw."""
    # 0.03 mmol * 311.3 g/mol = 9.339 mg
    result = calc_mass_mg(0.03, 311.3)
    assert abs(result - 9.339) < 0.001


def test_mass_mg_zero():
    """Zero mmol gives zero mass."""
    assert calc_mass_mg(0.0, 311.3) == 0.0


def test_format_volume_formula():
    """Formula string contains key values."""
    formula = format_volume_formula(2, 3.0, 0.0300, 0.5, 0.36)
    assert '2' in formula
    assert '3.0' in formula
    assert '0.5' in formula
    assert '0.360' in formula
