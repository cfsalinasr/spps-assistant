"""Materials explosion use case — weekly reagent planning."""

from pathlib import Path
from typing import Dict, List, Optional

from spps_assistant.application.ports import DatabaseRepository
from spps_assistant.domain.models import MaterialsRow, SynthesisConfig, Vessel
from spps_assistant.domain.stoichiometry import (
    calc_volume_stoichiometry, calc_volume_legacy, calc_mass_mg
)
from spps_assistant.domain.sequence import get_unique_tokens, parse_token
from spps_assistant.domain.constants import THREE_LETTER_CODE


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

        # Count how many vessels need this token (and how many times)
        count_per_vessel = {}
        for vessel in vessels:
            occurrences = vessel.original_tokens.count(tok)
            if occurrences > 0:
                count_per_vessel[vessel.number] = (vessel, occurrences)

        if not count_per_vessel:
            continue

        # Effective equivalents: global reactant excess × per-reagent multiplier
        eff_eq = config.aa_equivalents * res_info.equivalents_multiplier

        # Compute total mmol needed
        total_mmol = 0.0
        for vessel, (v_obj, occurrences) in count_per_vessel.items():
            resin_mmol = v_obj.resin_mass_g * v_obj.substitution_mmol_g
            total_mmol += eff_eq * resin_mmol * occurrences

        mass_mg = calc_mass_mg(total_mmol, res_info.fmoc_mw)

        # Volume
        n_uses = sum(occ for _, occ in count_per_vessel.values())
        if config.volume_mode == 'legacy':
            volume_ml = calc_volume_legacy(n_uses)
        else:
            avg_resin_mmol = (
                sum(v_obj.resin_mass_g * v_obj.substitution_mmol_g
                    for v_obj, _ in count_per_vessel.values())
                / len(count_per_vessel)
            )
            volume_ml = calc_volume_stoichiometry(
                n_uses, eff_eq, avg_resin_mmol, res_info.stock_conc
            )

        # For liquid reagents: report volume in µL (pipette, no weighing)
        volume_ul = None
        if res_info.density_g_ml is not None and res_info.density_g_ml > 0:
            # volume_µL = mass_mg / density_g_mL
            volume_ul = round(mass_mg / res_info.density_g_ml, 1)

        try:
            base, prot = parse_token(tok)
        except ValueError:
            base, prot = tok, ''

        three_letter = THREE_LETTER_CODE.get(base, base)
        display_name = three_letter if not prot else f"{three_letter}({prot})"

        if volume_ul is not None:
            formula = (
                f"V(µL) = {mass_mg:.2f} mg / {res_info.density_g_ml} g/mL = {volume_ul:.1f} µL"
            )
        elif config.volume_mode != 'legacy':
            formula = (
                f"V = ({n_uses} × {eff_eq} eq × {avg_resin_mmol:.4f} mmol) "
                f"/ {res_info.stock_conc} M"
            )
        else:
            formula = f"V = {n_uses} uses × 2 mL"

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
