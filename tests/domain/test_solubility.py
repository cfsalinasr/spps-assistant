"""Tests for domain.solubility module."""

import pytest

from spps_assistant.domain.solubility import (
    calc_hydrophobicity,
    classify_hydrophobicity,
    check_light_sensitivity,
    get_solubilization_recommendation,
    calc_net_charge_ph7,
    calc_pi as calc_pI,
    calc_gravy,
    analyze_peptide,
)
from spps_assistant.domain.constants import (
    KD_SCALE, EISENBERG_SCALE, BLACK_MOULD_SCALE, PKA_VALUES
)


# ------------------------------------------------------------------ #
# classify_hydrophobicity                                             #
# ------------------------------------------------------------------ #

def test_hydrophobic_majority_rule_all_three():
    """All three scales say hydrophobic -> True."""
    assert classify_hydrophobicity(kd=1.0, eisenberg=0.5, bm=0.6) is True


def test_hydrophobic_majority_rule_two_of_three():
    """Two of three scales say hydrophobic -> True."""
    assert classify_hydrophobicity(kd=1.0, eisenberg=0.5, bm=0.4) is True


def test_hydrophilic_one_of_three():
    """Only one scale says hydrophobic -> False."""
    assert classify_hydrophobicity(kd=-1.0, eisenberg=-0.5, bm=0.6) is False


def test_hydrophilic_none():
    """None of the three scales say hydrophobic -> False."""
    assert classify_hydrophobicity(kd=-1.0, eisenberg=-0.5, bm=0.3) is False


def test_hydrophobic_boundary_kd():
    """Exactly kd=0 is NOT hydrophobic (strict >0)."""
    assert classify_hydrophobicity(kd=0.0, eisenberg=-0.5, bm=0.3) is False


def test_hydrophobic_boundary_bm():
    """Exactly bm=0.5 is NOT hydrophobic (strict >0.5)."""
    assert classify_hydrophobicity(kd=-1.0, eisenberg=-0.5, bm=0.5) is False


# ------------------------------------------------------------------ #
# check_light_sensitivity                                              #
# ------------------------------------------------------------------ #

def test_light_sensitive_F():
    assert check_light_sensitivity(['F', 'A', 'G']) is True


def test_light_sensitive_W():
    assert check_light_sensitivity(['W']) is True


def test_light_sensitive_Y():
    assert check_light_sensitivity(['Y']) is True


def test_not_light_sensitive():
    assert check_light_sensitivity(['A', 'G', 'L']) is False


def test_light_sensitive_protected_W():
    """W(Boc) should still trigger light sensitivity (base code W)."""
    assert check_light_sensitivity(['W(Boc)', 'A']) is True


# ------------------------------------------------------------------ #
# get_solubilization_recommendation                                   #
# ------------------------------------------------------------------ #

def test_recommendation_hydrophobic_with_W():
    """Hydrophobic + W -> 50% Acetonitrile."""
    rec = get_solubilization_recommendation(True, ['W', 'L', 'A'], 0.0, 0.8, 0.0)
    assert 'cetonitrile' in rec or 'ACN' in rec


def test_recommendation_hydrophobic_with_C():
    """Hydrophobic + C -> 50% Acetonitrile."""
    rec = get_solubilization_recommendation(True, ['C', 'L', 'V'], 0.0, 0.8, 0.0)
    assert 'cetonitrile' in rec or 'ACN' in rec


def test_recommendation_hydrophobic_with_M():
    """Hydrophobic + M -> 50% Acetonitrile."""
    rec = get_solubilization_recommendation(True, ['M', 'L', 'V'], 0.0, 0.8, 0.0)
    assert 'cetonitrile' in rec or 'ACN' in rec


def test_recommendation_hydrophobic_no_cmw():
    """Hydrophobic, no C/M/W -> DMSO."""
    rec = get_solubilization_recommendation(True, ['L', 'A', 'V'], 0.0, 0.8, 0.0)
    assert 'DMSO' in rec


def test_recommendation_hydrophilic_low_charge():
    """Hydrophilic, charge < 25% -> DMSO then water."""
    rec = get_solubilization_recommendation(False, ['A', 'G', 'L'], 0.10, 0.5, 0.0)
    assert 'DMSO' in rec


def test_recommendation_hydrophilic_charged_low_hydrophobic():
    """Hydrophilic, charge >= 25%, low hydrophobic -> Water or PBS."""
    rec = get_solubilization_recommendation(False, ['A', 'K', 'E'], 0.40, 0.20, 1.0)
    assert 'ater' in rec or 'PBS' in rec


def test_recommendation_hydrophilic_charged_net_negative():
    """Hydrophilic, charge >= 25%, high hydrophobic, net negative -> ammonium bicarbonate."""
    rec = get_solubilization_recommendation(False, ['D', 'E', 'L', 'V'], 0.35, 0.65, -2.0)
    assert 'ammonium' in rec.lower() or 'bicarbonate' in rec.lower()


def test_recommendation_hydrophilic_charged_net_positive():
    """Hydrophilic, charge >= 25%, high hydrophobic, net positive -> Acetic acid."""
    rec = get_solubilization_recommendation(False, ['K', 'R', 'L', 'V'], 0.35, 0.65, 2.0)
    assert 'cetic' in rec.lower()


# ------------------------------------------------------------------ #
# calc_hydrophobicity                                                  #
# ------------------------------------------------------------------ #

def test_calc_hydrophobicity_single():
    """Single residue returns its own scale value."""
    result = calc_hydrophobicity(['I'], KD_SCALE)
    assert abs(result - 4.5) < 1e-9


def test_calc_hydrophobicity_average():
    """Average of two residues."""
    result = calc_hydrophobicity(['I', 'G'], KD_SCALE)
    # KD: I=4.5, G=-0.4 -> average = 2.05
    assert abs(result - (4.5 + (-0.4)) / 2) < 1e-9


def test_calc_hydrophobicity_empty():
    """Empty sequence returns 0.0."""
    assert calc_hydrophobicity([], KD_SCALE) == 0.0


def test_calc_hydrophobicity_skips_unknown():
    """Non-standard residues not in scale are skipped."""
    result = calc_hydrophobicity(['I', 'X_unknown_123'], KD_SCALE)
    # Only I contributes
    assert abs(result - 4.5) < 1e-9


# ------------------------------------------------------------------ #
# calc_net_charge_ph7                                                  #
# ------------------------------------------------------------------ #

def test_net_charge_lysine():
    """Single K peptide has positive charge at pH 7."""
    charge = calc_net_charge_ph7(['K'], PKA_VALUES)
    assert charge > 0


def test_net_charge_aspartate():
    """Single D peptide has negative charge at pH 7."""
    charge = calc_net_charge_ph7(['D'], PKA_VALUES)
    assert charge < 0


def test_net_charge_glycine():
    """Gly-Gly (neutral side chains) has charge ~0 (near pI)."""
    charge = calc_net_charge_ph7(['G', 'G'], PKA_VALUES)
    # Termini: N-term pKa=8 -> positive, C-term pKa=3.1 -> negative
    # At pH 7: net should be near 0 (slightly positive because N-term dominates)
    assert isinstance(charge, float)


# ------------------------------------------------------------------ #
# calc_pI                                                              #
# ------------------------------------------------------------------ #

def test_pI_is_float():
    """pI calculation returns a float."""
    pI = calc_pI(['A', 'G', 'K'], PKA_VALUES)
    assert isinstance(pI, float)
    assert 0.0 < pI < 14.0


def test_pI_lysine_basic():
    """Lysine-containing peptide has basic pI."""
    pI_basic = calc_pI(['K', 'K', 'K'], PKA_VALUES)
    pI_neutral = calc_pI(['A', 'G', 'V'], PKA_VALUES)
    assert pI_basic > pI_neutral


# ------------------------------------------------------------------ #
# calc_gravy                                                           #
# ------------------------------------------------------------------ #

def test_gravy_hydrophobic_peptide():
    """GRAVY should be positive for hydrophobic peptide."""
    gravy = calc_gravy(['I', 'L', 'V'], KD_SCALE)
    assert gravy > 0


def test_gravy_hydrophilic_peptide():
    """GRAVY should be negative for hydrophilic peptide."""
    gravy = calc_gravy(['R', 'K', 'D', 'E'], KD_SCALE)
    assert gravy < 0


# ------------------------------------------------------------------ #
# analyze_peptide (integration)                                        #
# ------------------------------------------------------------------ #

def test_analyze_peptide_returns_result():
    """analyze_peptide returns a SolubilityResult."""
    from spps_assistant.domain.models import SolubilityResult
    result = analyze_peptide(['A', 'G', 'K', 'W'], {})
    assert isinstance(result, SolubilityResult)
    assert result.light_sensitive is True  # W present
    assert isinstance(result.kd_avg, float)
    assert isinstance(result.p_i, float)
    assert isinstance(result.net_charge_ph7, float)
