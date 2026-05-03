"""Hydrophobicity analysis, solubility classification, and physicochemical properties."""

import math
from typing import List, Optional, Dict

from spps_assistant.domain.models import SolubilityResult
from spps_assistant.domain.sequence import parse_token


def calc_hydrophobicity(tokens: List[str], scale_dict: Dict[str, float]) -> float:
    """Calculate mean hydrophobicity score for a peptide sequence.

    Non-standard residues not in scale_dict are skipped (not counted).

    Args:
        tokens: List of residue tokens (base code extracted internally)
        scale_dict: Hydrophobicity scale mapping single-letter code -> float

    Returns:
        Mean hydrophobicity value, or 0.0 for empty sequences
    """
    values = []
    for tok in tokens:
        try:
            base, _ = parse_token(tok)
        except ValueError:
            continue
        if base in scale_dict:
            values.append(scale_dict[base])
    if not values:
        return 0.0
    return sum(values) / len(values)


def classify_hydrophobicity(kd: float, eisenberg: float, bm: float) -> bool:
    """Classify peptide as hydrophobic using majority rule across three scales.

    Thresholds:
      - Kyte-Doolittle: kd > 0
      - Eisenberg: eisenberg > 0
      - Black & Mould: bm > 0.5

    Majority rule: hydrophobic if 2 or more of 3 scales classify as hydrophobic.

    Args:
        kd: Mean Kyte-Doolittle hydrophobicity
        eisenberg: Mean Eisenberg hydrophobicity
        bm: Mean Black & Mould hydrophobicity (0-1 normalized)

    Returns:
        True if peptide is classified as hydrophobic
    """
    votes = sum([
        kd > 0,
        eisenberg > 0,
        bm > 0.5,
    ])
    return votes >= 2


def check_orthogonal_protection(tokens: List[str]) -> List[str]:
    """Return tokens that carry orthogonal protecting groups (e.g. Acm).

    These groups survive standard TFA cleavage and require a dedicated
    post-synthesis deprotection step.

    Args:
        tokens: List of residue tokens

    Returns:
        List of tokens whose protection group is in ORTHOGONAL_PROTECTING_GROUPS
    """
    from spps_assistant.domain.constants import ORTHOGONAL_PROTECTING_GROUPS
    found = []
    for tok in tokens:
        try:
            _, prot = parse_token(tok)
        except ValueError:
            continue
        if prot in ORTHOGONAL_PROTECTING_GROUPS:
            found.append(tok)
    return found


def check_light_sensitivity(tokens: List[str]) -> bool:
    """Check if peptide contains light-sensitive residues (F, Y, or W).

    Args:
        tokens: List of residue tokens

    Returns:
        True if any token contains F, Y, or W
    """
    sensitive = {'F', 'Y', 'W'}
    for tok in tokens:
        try:
            base, _ = parse_token(tok)
        except ValueError:
            continue
        if base in sensitive:
            return True
    return False


def calc_net_charge_ph7(tokens: List[str], pka_values: Dict[str, float]) -> float:
    """Calculate approximate net charge at pH 7.0 using Henderson-Hasselbalch.

    Args:
        tokens: List of residue tokens
        pka_values: Dict with keys like 'D', 'E', 'H', 'C', 'Y', 'K', 'R',
                    'N_term', 'C_term'

    Returns:
        Approximate net charge at pH 7.0
    """
    ph = 7.0
    charge = 0.0

    # N-terminus (positive at pH < pKa)
    pka_n = pka_values.get('N_term', 8.0)
    charge += 1.0 / (1.0 + 10 ** (ph - pka_n))

    # C-terminus (negative at pH > pKa)
    pka_c = pka_values.get('C_term', 3.1)
    charge -= 1.0 / (1.0 + 10 ** (pka_c - ph))

    for tok in tokens:
        try:
            base, _ = parse_token(tok)
        except ValueError:
            continue
        if base in pka_values:
            pka = pka_values[base]
            if base in ('D', 'E', 'C', 'Y'):
                # Acidic side chains (negative at pH > pKa)
                charge -= 1.0 / (1.0 + 10 ** (pka - ph))
            elif base in ('H', 'K', 'R'):
                # Basic side chains (positive at pH < pKa)
                charge += 1.0 / (1.0 + 10 ** (ph - pka))

    return round(charge, 3)


def _charge_at_ph(ph: float, tokens: List[str], pka_values: Dict[str, float]) -> float:
    """Return the net charge of the peptide at the given pH."""
    ch = 0.0
    pka_n = pka_values.get('N_term', 8.0)
    ch += 1.0 / (1.0 + 10 ** (ph - pka_n))
    pka_c = pka_values.get('C_term', 3.1)
    ch -= 1.0 / (1.0 + 10 ** (pka_c - ph))
    for tok in tokens:
        try:
            base, _ = parse_token(tok)
        except ValueError:
            continue
        if base in pka_values:
            pka = pka_values[base]
            if base in ('D', 'E', 'C', 'Y'):
                ch -= 1.0 / (1.0 + 10 ** (pka - ph))
            elif base in ('H', 'K', 'R'):
                ch += 1.0 / (1.0 + 10 ** (ph - pka))
    return ch


def _bisect_pi(tokens: List[str], pka_values: Dict[str, float]) -> float:
    """Find the pI by bisection over [0, 14]."""
    lo, hi = 0.0, 14.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        c = _charge_at_ph(mid, tokens, pka_values)
        if abs(c) < 1e-6:
            break
        if c > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def calc_pi(tokens: List[str], pka_values: Dict[str, float]) -> float:
    """Calculate isoelectric point (pI) by bisection search.

    Args:
        tokens: List of residue tokens
        pka_values: pKa dict (see calc_net_charge_ph7)

    Returns:
        Estimated pI
    """
    return round(_bisect_pi(tokens, pka_values), 2)


def calc_gravy(tokens: List[str], kd_scale: Dict[str, float]) -> float:
    """Calculate GRAVY (Grand Average of Hydropathicity) score.

    GRAVY = mean Kyte-Doolittle value across all residues.
    Positive = hydrophobic, negative = hydrophilic.

    Args:
        tokens: List of residue tokens
        kd_scale: Kyte-Doolittle hydrophobicity scale dict

    Returns:
        GRAVY score
    """
    return calc_hydrophobicity(tokens, kd_scale)


def _hydrophobic_recommendation(base_codes: set) -> str:
    """Return solubilization recommendation for a hydrophobic peptide."""
    if base_codes & {'C', 'M', 'W'}:
        return "50% Acetonitrile in water (contains C/M/W residues)"
    return "50% DMSO in water"


def _hydrophilic_recommendation(charge_fraction: float,
                                 hydrophobic_fraction: float,
                                 net_charge: float) -> str:
    """Return solubilization recommendation for a hydrophilic peptide."""
    if charge_fraction < 0.25:
        return "DMSO 10-20 μL, then dilute with water"
    if hydrophobic_fraction <= 0.50:
        return "Water or PBS (pH 7.4)"
    if net_charge < 0:
        return "0.1 M ammonium bicarbonate"
    return "Acetic acid (dilute, ~10%)"


def get_solubilization_recommendation(
    is_hydrophobic: bool,
    tokens: List[str],
    charge_fraction: float,
    hydrophobic_fraction: float,
    net_charge: float,
) -> str:
    """Recommend a solubilization strategy for the peptide.

    Args:
        is_hydrophobic: Overall hydrophobicity classification
        tokens: List of residue tokens
        charge_fraction: Fraction of charged residues (D,E,K,R,H)
        hydrophobic_fraction: Fraction of hydrophobic residues (A,V,I,L,M,F,W,P)
        net_charge: Net charge at pH 7 (positive or negative)

    Returns:
        Solubilization recommendation string
    """
    base_codes = set()
    for tok in tokens:
        try:
            base, _ = parse_token(tok)
            base_codes.add(base)
        except ValueError:
            pass

    if is_hydrophobic:
        return _hydrophobic_recommendation(base_codes)
    return _hydrophilic_recommendation(charge_fraction, hydrophobic_fraction, net_charge)


def analyze_peptide(
    tokens: List[str],
    kd_scale: Optional[Dict] = None,
    eisenberg_scale: Optional[Dict] = None,
    bm_scale: Optional[Dict] = None,
    pka_values: Optional[Dict] = None,
) -> SolubilityResult:
    """Run full hydrophobicity and solubility analysis on a peptide.

    Args:
        tokens: List of residue tokens
        kd_scale: Kyte-Doolittle scale (uses domain.constants default if None)
        eisenberg_scale: Eisenberg scale (uses domain.constants default if None)
        bm_scale: Black & Mould scale (uses domain.constants default if None)
        pka_values: pKa values (uses domain.constants default if None)

    Returns:
        SolubilityResult with all computed properties
    """
    from spps_assistant.domain.constants import (
        KD_SCALE, EISENBERG_SCALE, BLACK_MOULD_SCALE, PKA_VALUES
    )

    kd_scale = kd_scale or KD_SCALE
    eisenberg_scale = eisenberg_scale or EISENBERG_SCALE
    bm_scale = bm_scale or BLACK_MOULD_SCALE
    pka_values = pka_values or PKA_VALUES

    kd_avg = calc_hydrophobicity(tokens, kd_scale)
    eis_avg = calc_hydrophobicity(tokens, eisenberg_scale)
    bm_avg = calc_hydrophobicity(tokens, bm_scale)
    is_hydrophobic = classify_hydrophobicity(kd_avg, eis_avg, bm_avg)
    light_sensitive = check_light_sensitivity(tokens)
    orthogonal_groups = check_orthogonal_protection(tokens)
    net_charge = calc_net_charge_ph7(tokens, pka_values)
    pi_val = calc_pi(tokens, pka_values)
    gravy_val = calc_gravy(tokens, kd_scale)

    # Compute fractions for recommendation
    charged_residues = {'D', 'E', 'K', 'R', 'H'}
    hydrophobic_residues = {'A', 'V', 'I', 'L', 'M', 'F', 'W', 'P'}
    base_codes = []
    for tok in tokens:
        try:
            base, _ = parse_token(tok)
            base_codes.append(base)
        except ValueError:
            pass

    n = len(base_codes) if base_codes else 1
    charge_fraction = sum(1 for b in base_codes if b in charged_residues) / n
    hydrophobic_fraction = sum(1 for b in base_codes if b in hydrophobic_residues) / n

    recommendation = get_solubilization_recommendation(
        is_hydrophobic, tokens, charge_fraction, hydrophobic_fraction, net_charge
    )

    return SolubilityResult(
        kd_avg=round(kd_avg, 3),
        eisenberg_avg=round(eis_avg, 3),
        black_mould_avg=round(bm_avg, 3),
        is_hydrophobic=is_hydrophobic,
        recommendation=recommendation,
        light_sensitive=light_sensitive,
        net_charge_ph7=round(net_charge, 3),
        p_i=round(pi_val, 2),
        gravy=round(gravy_val, 3),
        orthogonal_groups=orthogonal_groups,
    )
