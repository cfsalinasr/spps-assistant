"""Theoretical yield calculations for SPPS."""

from typing import List, Dict


def calc_peptide_mw(
    tokens: List[str],
    free_residue_mw: Dict[str, float],
    residue_info_map: Dict,
) -> float:
    """Calculate peptide molecular weight from residue tokens.

    MW = sum of free residue MWs + H2O (18.0152)

    ResidueInfo objects in residue_info_map take precedence over free_residue_mw
    defaults. For tokens not in either source, average MW (111.10) is used.

    Args:
        tokens: List of residue tokens (e.g. ['G', 'W', 'C(Trt)'])
        free_residue_mw: Default free AA residue MW dict (single-letter keys)
        residue_info_map: Dict mapping token -> ResidueInfo objects

    Returns:
        Peptide MW in g/mol
    """
    from spps_assistant.domain.sequence import parse_token

    total = 18.0152  # Water
    for tok in tokens:
        if tok in residue_info_map:
            total += residue_info_map[tok].free_mw
        else:
            try:
                base, _ = parse_token(tok)
            except ValueError:
                total += 111.10  # unknown average
                continue
            mw = free_residue_mw.get(base, 111.10)
            total += mw
    return total


def calc_theoretical_yield(
    resin_mass_g: float,
    substitution_mmol_g: float,
    sequence_length: int,
    peptide_mw: float,
) -> float:
    """Calculate theoretical peptide yield in milligrams.

    Formula:
        resin_mmol = resin_mass_g * substitution_mmol_g
        theoretical_mmol = resin_mmol * (0.98 ^ sequence_length)
        yield_mg = theoretical_mmol * peptide_mw

    The 0.98 per-step factor assumes ~98% coupling efficiency per cycle.

    Args:
        resin_mass_g: Resin mass in grams
        substitution_mmol_g: Resin loading in mmol/g
        sequence_length: Number of residues in the peptide
        peptide_mw: Peptide molecular weight in g/mol

    Returns:
        Theoretical yield in milligrams
    """
    resin_mmol = resin_mass_g * substitution_mmol_g
    theoretical_mmol = resin_mmol * (0.98 ** sequence_length)
    yield_mg = theoretical_mmol * peptide_mw
    return yield_mg


def back_calc_resin_mass(
    target_yield_mg: float,
    substitution_mmol_g: float,
    sequence_length: int,
    peptide_mw: float,
) -> float:
    """Back-calculate resin mass needed to achieve a target yield.

    Rearrangement of calc_theoretical_yield:
        resin_mass_g = target_yield_mg / (substitution_mmol_g * (0.98^length) * peptide_mw)

    Args:
        target_yield_mg: Desired yield in milligrams
        substitution_mmol_g: Resin loading in mmol/g
        sequence_length: Number of residues
        peptide_mw: Peptide molecular weight in g/mol

    Returns:
        Required resin mass in grams
    """
    denominator = substitution_mmol_g * (0.98 ** sequence_length) * peptide_mw
    if denominator <= 0:
        raise ValueError("Cannot back-calculate: denominator is zero or negative.")
    return target_yield_mg / denominator


def build_yield_formula(
    resin_mass_g: float,
    substitution_mmol_g: float,
    sequence_length: int,
    peptide_mw: float,
    yield_mg: float,
) -> str:
    """Build a human-readable yield formula string.

    Args:
        resin_mass_g: Resin mass in grams
        substitution_mmol_g: Resin loading in mmol/g
        sequence_length: Number of residues
        peptide_mw: Peptide MW in g/mol
        yield_mg: Theoretical yield in mg

    Returns:
        Formula string for display/GMP documentation
    """
    return (
        f"{resin_mass_g:.4f} g × {substitution_mmol_g:.4f} mmol/g × "
        f"0.98^{sequence_length} × {peptide_mw:.2f} g/mol = {yield_mg:.2f} mg"
    )
