"""Materials explosion use case — weekly reagent planning."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from spps_assistant.application.ports import DatabaseRepository
from spps_assistant.domain.models import MaterialsRow, SynthesisConfig, Vessel
from spps_assistant.domain.stoichiometry import (
    calc_volume_stoichiometry, calc_volume_legacy, calc_mass_mg
)
from spps_assistant.domain.sequence import get_unique_tokens, parse_token
from spps_assistant.domain.constants import THREE_LETTER_CODE


def _count_token_per_vessel(tok: str, vessels: List[Vessel]) -> Dict:
    """Return a dict mapping vessel number to (Vessel, occurrences) for a token."""
    count_per_vessel = {}
    for vessel in vessels:
        occurrences = vessel.original_tokens.count(tok)
        if occurrences > 0:
            count_per_vessel[vessel.number] = (vessel, occurrences)
    return count_per_vessel


def _calc_total_mmol(count_per_vessel: Dict, eff_eq: float) -> float:
    """Compute total mmol needed across all vessels."""
    total_mmol = 0.0
    for _vessel_num, (v_obj, occurrences) in count_per_vessel.items():
        resin_mmol = v_obj.resin_mass_g * v_obj.substitution_mmol_g
        total_mmol += eff_eq * resin_mmol * occurrences
    return total_mmol


def _calc_volume(count_per_vessel: Dict, config: SynthesisConfig,
                 eff_eq: float, n_uses: int, stock_conc: float) -> Tuple[float, float]:
    """Return (volume_ml, avg_resin_mmol) for the given usage data."""
    if config.volume_mode == 'legacy':
        return calc_volume_legacy(n_uses), 0.0
    avg_resin_mmol = (
        sum(v_obj.resin_mass_g * v_obj.substitution_mmol_g * occ
            for v_obj, occ in count_per_vessel.values())
        / n_uses
    )
    volume_ml = calc_volume_stoichiometry(n_uses, eff_eq, avg_resin_mmol, stock_conc)
    return volume_ml, avg_resin_mmol


def _build_formula(volume_ul: Optional[float], mass_mg: float, density: Optional[float],
                   volume_mode: str, n_uses: int, eff_eq: float,
                   avg_resin_mmol: float, stock_conc: float) -> str:
    """Build the GMP formula string for a materials row."""
    if volume_ul is not None:
        return f"V(µL) = {mass_mg:.2f} mg / {density} g/mL = {volume_ul:.1f} µL"
    if volume_mode != 'legacy':
        return (
            f"V = ({n_uses} × {eff_eq} eq × {avg_resin_mmol:.4f} mmol) "
            f"/ {stock_conc} M"
        )
    return f"V = {n_uses} uses × 2 mL"


def build_materials_rows(
    vessels: List[Vessel],
    residue_info_map: Dict,
    config: SynthesisConfig,
) -> List[MaterialsRow]:
    """Build materials rows for all unique residues needed for a synthesis run.

    Calculates total mmol needed per unique token across all vessels that use it,
    then computes mass and volume.

    Args:
        vessels: List of Vessel objects
        residue_info_map: Token -> ResidueInfo map
        config: SynthesisConfig with equivalents and volume mode

    Returns:
        List of MaterialsRow objects, one per unique residue token
    """
    unique_tokens = get_unique_tokens(vessels)

    rows = []
    for tok in unique_tokens:
        if tok not in residue_info_map:
            continue

        res_info = residue_info_map[tok]
        count_per_vessel = _count_token_per_vessel(tok, vessels)

        if not count_per_vessel:
            continue

        # Effective equivalents: global reactant excess × per-reagent multiplier
        eff_eq = config.aa_equivalents * res_info.equivalents_multiplier
        total_mmol = _calc_total_mmol(count_per_vessel, eff_eq)
        mass_mg = calc_mass_mg(total_mmol, res_info.fmoc_mw)

        # Volume
        n_uses = sum(occ for _, occ in count_per_vessel.values())
        volume_ml, avg_resin_mmol = _calc_volume(
            count_per_vessel, config, eff_eq, n_uses, res_info.stock_conc
        )

        volume_ul = None
        if res_info.density_g_ml is not None:
            if res_info.density_g_ml <= 0:
                raise ValueError(
                    f"Invalid density_g_ml for {tok}: {res_info.density_g_ml}"
                )
            volume_ul = round(mass_mg / res_info.density_g_ml, 1)

        try:
            base, prot = parse_token(tok)
        except ValueError:
            base, prot = tok, ''

        three_letter = THREE_LETTER_CODE.get(base, base)
        if prot:
            display_name = f"{three_letter}({prot})"
        else:
            display_name = three_letter

        formula = _build_formula(
            volume_ul, mass_mg, res_info.density_g_ml,
            config.volume_mode, n_uses, eff_eq, avg_resin_mmol, res_info.stock_conc
        )

        rows.append(MaterialsRow(
            token=tok,
            protection=prot,
            fmoc_mw=res_info.fmoc_mw,
            mmol_needed=round(total_mmol, 4),
            mass_mg=round(mass_mg, 2),
            stock_conc=res_info.stock_conc,
            volume_ml=round(volume_ml, 3),
            notes=f"Fmoc-{display_name}-OH",
            formula=formula,
            volume_ul=volume_ul,
        ))

    return rows


class MaterialsUseCase:
    """Weekly materials explosion use case."""

    def __init__(self, db: DatabaseRepository):
        """Initialise with a database repository for residue lookups."""
        self.db = db

    def run(
        self,
        vessels: List[Vessel],
        residue_info_map: Dict,
        config: SynthesisConfig,
        output_dir: str,
        week: Optional[int] = None,
    ) -> Dict[str, str]:
        """Generate materials list for a set of synthesis vessels.

        Args:
            vessels: List of Vessel objects
            residue_info_map: Token -> ResidueInfo map
            config: SynthesisConfig with equivalents settings
            output_dir: Where to write output files
            week: Optional week number for labeling

        Returns:
            Dict mapping file types to paths
        """
        from spps_assistant.infrastructure.xlsx_generator import generate_materials_xlsx
        from spps_assistant.infrastructure.pdf_generator import generate_materials_pdf

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        rows = build_materials_rows(vessels, residue_info_map, config)

        label = config.name
        if week is not None:
            label = f"{config.name}_week{week}"

        safe_label = label.replace(' ', '_').replace('/', '-')
        xlsx_path = out_path / f"{safe_label}_materials.xlsx"
        pdf_path = out_path / f"{safe_label}_materials.pdf"

        generate_materials_xlsx(
            path=xlsx_path,
            synthesis_name=label,
            materials_rows=rows,
        )

        config_summary = {
            'Activator': config.activator,
            'AA Equivalents': config.aa_equivalents,
            'Volume Mode': config.volume_mode,
            'Base': config.base,
        }
        generate_materials_pdf(
            path=pdf_path,
            synthesis_name=label,
            materials_rows=rows,
            config_summary=config_summary,
        )

        return {
            'materials_xlsx': str(xlsx_path),
            'materials_pdf': str(pdf_path),
        }
