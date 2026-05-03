"""Main synthesis guide use case — orchestrates the full generate workflow."""

from datetime import date
from pathlib import Path
from typing import Dict, List

from spps_assistant.application.ports import DatabaseRepository, ConfigRepository
from spps_assistant.domain.models import (
    CouplingCycle, SynthesisConfig, Vessel, YieldResult
)
from spps_assistant.domain.constants import FREE_RESIDUE_MW
from spps_assistant.domain.yield_calc import (
    calc_peptide_mw, calc_theoretical_yield, back_calc_resin_mass, build_yield_formula
)
from spps_assistant.domain.solubility import analyze_peptide
from spps_assistant.domain.sequence import parse_token


def build_coupling_cycles(vessels: List[Vessel]) -> List[CouplingCycle]:
    """Build a list of CouplingCycle objects from a set of Vessel objects.

    For cycle N (1-indexed), the residue at position N in each vessel's
    reversed_tokens sequence is coupled. Vessels shorter than N are 'OUT'.

    Args:
        vessels: List of Vessel objects with reversed_tokens set

    Returns:
        Ordered list of CouplingCycle objects (one per cycle step)
    """
    if not vessels:
        return []
    total_cycles = max(v.length for v in vessels)
    cycles = []
    for cycle_num in range(1, total_cycles + 1):
        # Map token -> list of vessel numbers for this cycle
        residues_at_position: Dict[str, List[int]] = {}
        for vessel in vessels:
            idx = cycle_num - 1
            if idx < len(vessel.reversed_tokens):
                tok = vessel.reversed_tokens[idx]
                residues_at_position.setdefault(tok, [])
                residues_at_position[tok].append(vessel.number)
        cycles.append(CouplingCycle(
            cycle_number=cycle_num,
            total_cycles=total_cycles,
            residues_at_position=residues_at_position,
            all_vessels=vessels,
        ))
    return cycles


def determine_resin_mass(
    vessel: Vessel,
    config: SynthesisConfig,
    residue_info_map: Dict,
) -> float:
    """Determine resin mass for a vessel based on config strategy.

    Args:
        vessel: Vessel object
        config: SynthesisConfig with resin_mass_strategy field
        residue_info_map: Token -> ResidueInfo map

    Returns:
        Resin mass in grams
    """
    if config.resin_mass_strategy == 'fixed':
        return config.fixed_resin_mass_g

    if config.target_yield_mg is None:
        return config.fixed_resin_mass_g

    # Calculate peptide MW for back-calculation
    peptide_mw = calc_peptide_mw(vessel.original_tokens, FREE_RESIDUE_MW, residue_info_map)
    return back_calc_resin_mass(
        config.target_yield_mg,
        vessel.substitution_mmol_g,
        vessel.length,
        peptide_mw,
    )


class SynthesisGuideUseCase:
    """Orchestrates the full SPPS synthesis guide generation workflow."""

    def __init__(self, db: DatabaseRepository, config_repo: ConfigRepository):
        """Initialise with a database repository and a config repository."""
        self.db = db
        self.config_repo = config_repo

    def run(
        self,
        output_dir: str,
        config: SynthesisConfig,
        residue_info_map: Dict,
        vessels: List[Vessel],
    ) -> Dict[str, str]:
        """Execute the synthesis guide generation workflow.

        Steps:
            1. Build coupling cycles
            2. Calculate yields for each vessel
            3. Run solubility analysis per vessel
            4. Generate PDF cycle guide
            5. Generate DOCX cycle guide
            6. Generate peptide info PDF + DOCX
            7. Log synthesis to DB

        Args:
            output_dir: Output directory path
            config: SynthesisConfig parameters
            residue_info_map: Token -> ResidueInfo map
            vessels: List of Vessel objects

        Returns:
            Dict mapping output file types to their paths
        """
        from spps_assistant.infrastructure.pdf_generator import (
            generate_cycle_guide_pdf, generate_peptide_info_pdf
        )
        from spps_assistant.infrastructure.docx_generator import (
            generate_cycle_guide_docx, generate_peptide_info_docx
        )

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()

        # 1. Build coupling cycles
        coupling_cycles = build_coupling_cycles(vessels)

        # 2. Calculate yields
        yield_results: List[YieldResult] = []
        for vessel in vessels:
            peptide_mw = calc_peptide_mw(
                vessel.original_tokens, FREE_RESIDUE_MW, residue_info_map
            )
            yield_mg = calc_theoretical_yield(
                vessel.resin_mass_g,
                vessel.substitution_mmol_g,
                vessel.length,
                peptide_mw,
            )
            formula = build_yield_formula(
                vessel.resin_mass_g,
                vessel.substitution_mmol_g,
                vessel.length,
                peptide_mw,
                yield_mg,
            )
            yield_results.append(YieldResult(
                vessel_number=vessel.number,
                vessel_name=vessel.name,
                peptide_mw=round(peptide_mw, 2),
                sequence_length=vessel.length,
                resin_mass_g=vessel.resin_mass_g,
                substitution_mmol_g=vessel.substitution_mmol_g,
                theoretical_yield_mg=round(yield_mg, 2),
                formula_shown=formula,
            ))

        # 3. Solubility analysis
        solubility_results = {}
        for vessel in vessels:
            result = analyze_peptide(vessel.original_tokens)
            solubility_results[vessel.number] = result

        # 4 & 5. Generate cycle guide (PDF + DOCX)
        safe_name = config.name.replace(' ', '_').replace('/', '-')
        cycle_guide_pdf = out_path / f"{safe_name}_cycle_guide.pdf"
        cycle_guide_docx = out_path / f"{safe_name}_cycle_guide.docx"
        peptide_info_pdf = out_path / f"{safe_name}_peptide_info.pdf"
        peptide_info_docx = out_path / f"{safe_name}_peptide_info.docx"

        generate_cycle_guide_pdf(
            path=cycle_guide_pdf,
            synthesis_name=config.name,
            date_str=today,
            vessels=vessels,
            coupling_cycles=coupling_cycles,
            config=config,
            residue_info_map=residue_info_map,
            yield_results=yield_results,
        )

        generate_cycle_guide_docx(
            path=cycle_guide_docx,
            synthesis_name=config.name,
            date_str=today,
            vessels=vessels,
            coupling_cycles=coupling_cycles,
            config=config,
            residue_info_map=residue_info_map,
            yield_results=yield_results,
        )

        # 6. Peptide info documents
        generate_peptide_info_pdf(
            path=peptide_info_pdf,
            synthesis_name=config.name,
            vessels=vessels,
            solubility_results=solubility_results,
            yield_results=yield_results,
        )

        generate_peptide_info_docx(
            path=peptide_info_docx,
            synthesis_name=config.name,
            vessels=vessels,
            solubility_results=solubility_results,
            yield_results=yield_results,
        )

        # 7. Log to DB
        try:
            self.db.log_synthesis(
                synthesis_name=config.name,
                metadata={
                    'date': today,
                    'n_vessels': len(vessels),
                    'n_cycles': len(coupling_cycles),
                    'volume_mode': config.volume_mode,
                    'activator': config.activator,
                    'output_dir': str(out_path),
                },
            )
        except Exception:
            pass  # Don't let DB logging failures break the workflow

        return {
            'cycle_guide_pdf': str(cycle_guide_pdf),
            'cycle_guide_docx': str(cycle_guide_docx),
            'peptide_info_pdf': str(peptide_info_pdf),
            'peptide_info_docx': str(peptide_info_docx),
        }
