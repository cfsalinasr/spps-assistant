"""Main synthesis guide use case — orchestrates the full generate workflow."""

from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from spps_assistant.application.ports import DatabaseRepository, ConfigRepository
from spps_assistant.domain.models import (
    CouplingCycle, CycleGuideViewData, CyclePageData, DispatchRow, GmpStep,
    MaterialsViewData, SecondaryCouplingRow, SynthesisConfig, Vessel, VesselAssignment, YieldResult
)
from spps_assistant.domain.constants import FREE_RESIDUE_MW
from spps_assistant.domain.yield_calc import (
    calc_peptide_mw, calc_theoretical_yield, back_calc_resin_mass, build_yield_formula
)
from spps_assistant.domain.solubility import analyze_peptide
from spps_assistant.domain.sequence import parse_token, token_to_3letter, build_coupling_label

WASH_DURATION = '2 × 1 min'
COUPLING_DURATION = '30 min'


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


def _build_dispatch_rows(
    cycle: CouplingCycle, config: SynthesisConfig, residue_info_map: Dict
) -> List[DispatchRow]:
    """Build dispatch rows (one per residue token active in this cycle)."""
    from spps_assistant.domain.constants import FMOC_MW_DEFAULTS
    # parse_token is already imported at module level in this file.
    from spps_assistant.domain.stoichiometry import (
        calc_volume_stoichiometry, calc_volume_legacy, format_volume_formula
    )

    n_vessels = len(cycle.all_vessels)
    total_resin_mmol = sum(v.resin_mass_g * v.substitution_mmol_g for v in cycle.all_vessels)
    avg_resin_mmol = total_resin_mmol / n_vessels if n_vessels else 0.03

    rows = []
    for token, vessel_nums in cycle.residues_at_position.items():
        three = token_to_3letter(token)
        n_v = len(vessel_nums)

        if token in residue_info_map:
            res = residue_info_map[token]
            fmoc_mw = res.fmoc_mw
            stock_conc = res.stock_conc
        else:
            try:
                base, _ = parse_token(token)
            except ValueError:
                base = 'X'
            fmoc_mw = FMOC_MW_DEFAULTS.get(token, FMOC_MW_DEFAULTS.get(base, 353.4))
            stock_conc = 0.5

        if config.volume_mode == 'legacy':
            volume_ml = calc_volume_legacy(n_v)
            formula_str = f"V = {n_v} × 2 mL"
        else:
            volume_ml = calc_volume_stoichiometry(n_v, config.aa_equivalents, avg_resin_mmol, stock_conc)
            formula_str = format_volume_formula(
                n_v, config.aa_equivalents, avg_resin_mmol, stock_conc, volume_ml
            )

        mmol = n_v * config.aa_equivalents * avg_resin_mmol

        rows.append(DispatchRow(
            residue_3letter=three,
            fmoc_mw=fmoc_mw,
            mmol=mmol,
            volume_ml=volume_ml,
            formula_shown=formula_str,
            vessel_numbers=sorted(vessel_nums),
        ))
    return rows


def _build_deprotection_steps(config: SynthesisConfig) -> List[GmpStep]:
    """Build the deprotection GMP steps for a cycle, matching the configured protocol."""
    dep_name = config.deprotection_reagent
    steps = [
        GmpStep(label='1. Deprotection', detail=f'{dep_name} in DMF', n_checkboxes=2, duration='2 × 10 min'),
        GmpStep(label='2. DMF wash', detail='DMF (3×)', n_checkboxes=3, duration='3 × 1 min'),
    ]
    if config.include_bb_test:
        steps.append(GmpStep(
            label='3. Bromophenol Blue test', detail='Bromophenol Blue in DMF (1×)',
            n_checkboxes=1, duration='1 × 2 min',
        ))
        steps.append(GmpStep(label='4. DMF wash', detail='DMF (2×)', n_checkboxes=2, duration=WASH_DURATION))
        steps.append(GmpStep(label='5. DCM wash', detail='DCM (2×)', n_checkboxes=2, duration=WASH_DURATION))
    else:
        steps.append(GmpStep(label='3. DMF wash', detail='DMF (2×)', n_checkboxes=2, duration=WASH_DURATION))
        steps.append(GmpStep(label='4. DCM wash', detail='DCM (2×)', n_checkboxes=2, duration=WASH_DURATION))
    if config.include_kaiser_test:
        steps.append(GmpStep(
            label='Kaiser test', detail='Coupling completeness check',
            n_checkboxes=1, duration='As needed',
        ))
    return steps


def _build_coupling_steps(config: SynthesisConfig, cycle: CouplingCycle) -> List[GmpStep]:
    """Build the coupling GMP steps for a cycle (4 repeats + post-coupling wash)."""
    first_token = next(iter(cycle.residues_at_position), 'AA')
    coupling_label = build_coupling_label(config, first_token)

    return [
        GmpStep(label='1st coupling', detail=coupling_label, n_checkboxes=1, duration=COUPLING_DURATION),
        GmpStep(label='2nd coupling', detail=f'Repeat: {coupling_label}', n_checkboxes=1, duration=COUPLING_DURATION),
        GmpStep(label='3rd coupling', detail=f'Repeat: {coupling_label}', n_checkboxes=1, duration=COUPLING_DURATION),
        GmpStep(label='4th coupling', detail=f'Repeat: {coupling_label}', n_checkboxes=1, duration=COUPLING_DURATION),
        GmpStep(label='Post-coupling wash', detail='DMF (2×1 min), DCM (3×1 min)', n_checkboxes=0, duration='5 min'),
    ]


def _build_vessel_assignments(cycle: CouplingCycle) -> List[VesselAssignment]:
    """Build the per-vessel residue-or-OUT assignment list for a cycle."""
    idx = cycle.cycle_number - 1
    assignments = []
    for vessel in cycle.all_vessels:
        if idx < len(vessel.reversed_tokens):
            three = token_to_3letter(vessel.reversed_tokens[idx])
        else:
            three = None
        assignments.append(VesselAssignment(
            vessel_number=vessel.number, vessel_name=vessel.name, residue_3letter=three,
        ))
    return assignments


def _build_secondary_coupling_rows(
    cycle: CouplingCycle, config: SynthesisConfig
) -> Optional[List[SecondaryCouplingRow]]:
    """Build the Teabag-only secondary coupling verification rows, or None."""
    if config.vessel_method != 'Teabag':
        return None

    idx = cycle.cycle_number - 1
    rows = []
    for vessel in cycle.all_vessels:
        if idx < len(vessel.reversed_tokens):
            three = token_to_3letter(vessel.reversed_tokens[idx])
        else:
            three = 'OUT'
        rows.append(SecondaryCouplingRow(
            vessel_number=vessel.number, vessel_name=vessel.name, residue_3letter=three,
        ))
    return rows


def build_cycle_guide_view_data(
    coupling_cycles: List[CouplingCycle],
    config: SynthesisConfig,
    residue_info_map: Dict,
    date_str: str,
) -> CycleGuideViewData:
    """Build the structured, display-ready data for every coupling cycle.

    This is the single source of truth for per-cycle GMP record content —
    both the PDF/DOCX generators and the GUI's Cycle Guide view render
    from this, so the on-screen preview and the exported documents can
    never drift apart.
    """
    cycles = [
        CyclePageData(
            cycle_number=cycle.cycle_number,
            total_cycles=cycle.total_cycles,
            dispatch_rows=_build_dispatch_rows(cycle, config, residue_info_map),
            deprotection_steps=_build_deprotection_steps(config),
            coupling_steps=_build_coupling_steps(config, cycle),
            vessel_assignments=_build_vessel_assignments(cycle),
            secondary_coupling_rows=_build_secondary_coupling_rows(cycle, config),
        )
        for cycle in coupling_cycles
    ]

    return CycleGuideViewData(synthesis_name=config.name, date_str=date_str, cycles=cycles)


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


def build_config_from_defaults(
    config_defaults: Dict,
    volume_mode: Optional[str] = None,
    output_dir: Optional[str] = None,
    starting_num: Optional[int] = None,
) -> SynthesisConfig:
    """Build a SynthesisConfig from a defaults dict with optional overrides.

    Args:
        config_defaults: Dict of default values (e.g. from a config file)
        volume_mode: Overrides config_defaults volume_mode when provided
        output_dir: Overrides config_defaults output_directory when provided
        starting_num: Overrides config_defaults starting_vessel_number when provided

    Returns:
        A fully-populated SynthesisConfig instance

    Raises:
        ValueError: If aa_equivalents <= 0
    """
    from spps_assistant.domain.stoichiometry import derive_equivalents

    aa_eq = config_defaults.get('aa_equivalents', 3.0)
    if aa_eq <= 0:
        raise ValueError(f"aa_equivalents must be > 0, got {aa_eq}")

    activator_eq, base_eq = derive_equivalents(aa_eq)

    resolved_volume_mode = volume_mode if volume_mode is not None else config_defaults.get('volume_mode', 'stoichiometry')
    resolved_output_dir = output_dir if output_dir is not None else config_defaults.get('output_directory', 'spps_output')
    resolved_starting_num = starting_num if starting_num is not None else config_defaults.get('starting_vessel_number', 1)

    return SynthesisConfig(
        name=config_defaults.get('name', 'MySynthesis'),
        vessel_label=config_defaults.get('vessel_label', 'Vessel'),
        vessel_method=config_defaults.get('vessel_method', 'Teabag'),
        volume_mode=resolved_volume_mode,
        activator=config_defaults.get('activator', 'HBTU'),
        use_oxyma=config_defaults.get('use_oxyma', True),
        base=config_defaults.get('base', 'DIEA'),
        deprotection_reagent=config_defaults.get('deprotection_reagent', 'Piperidine 20%'),
        aa_equivalents=aa_eq,
        activator_equivalents=activator_eq,
        base_equivalents=base_eq,
        include_bb_test=config_defaults.get('include_bb_test', True),
        include_kaiser_test=config_defaults.get('include_kaiser_test', False),
        starting_vessel_number=resolved_starting_num,
        output_directory=resolved_output_dir,
        resin_mass_strategy=config_defaults.get('resin_mass_strategy', 'fixed'),
        fixed_resin_mass_g=config_defaults.get('fixed_resin_mass_g', 0.1),
        target_yield_mg=config_defaults.get('target_yield_mg', None),
    )


def calc_yields_and_solubility(
    vessels: List[Vessel],
    residue_info_map: Dict,
) -> Tuple[List[YieldResult], Dict]:
    """Calculate yields and run solubility analysis for each vessel.

    Args:
        vessels: List of Vessel objects with resin_mass_g and substitution_mmol_g set
        residue_info_map: Token -> ResidueInfo map

    Returns:
        Tuple of (yield_results, solubility_results) where solubility_results
        is keyed by vessel.number
    """
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

    solubility_results: Dict = {}
    for vessel in vessels:
        result = analyze_peptide(vessel.original_tokens)
        solubility_results[vessel.number] = result

    return yield_results, solubility_results


def apply_target_resin_mass(
    vessels: List[Vessel],
    config: SynthesisConfig,
    residue_info_map: Dict,
) -> None:
    """Apply resin mass to each vessel using determine_resin_mass, modifying in place.

    Args:
        vessels: List of Vessel objects to update
        config: SynthesisConfig with resin_mass_strategy and related fields
        residue_info_map: Token -> ResidueInfo map

    Raises:
        ValueError: If resin mass cannot be determined for any vessel
    """
    for vessel in vessels:
        try:
            vessel.resin_mass_g = determine_resin_mass(vessel, config, residue_info_map)
        except Exception as exc:
            raise ValueError(
                f"Could not back-calculate resin mass for vessel {vessel.number} "
                f"({vessel.name}): {exc}"
            ) from exc


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
        yield_results: Optional[List[YieldResult]] = None,
        solubility_results: Optional[Dict] = None,
    ) -> Tuple[Dict[str, str], CycleGuideViewData, MaterialsViewData]:
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
            yield_results: Optional pre-computed yield results to avoid recomputation
            solubility_results: Optional pre-computed solubility results to avoid recomputation

        Returns:
            Tuple of (output_paths, cycle_guide_data, materials_data).
            output_paths maps output file types to their paths.
            cycle_guide_data is the structured per-cycle GMP record data for
            the GUI's Cycle Guide view. materials_data is the structured
            materials-explosion data for the GUI's Materials view. Both are
            the same data the PDF/DOCX/XLSX generators render from
            internally, so the GUI previews and the exported documents can
            never drift apart.
        """
        from spps_assistant.application.materials import build_materials_view_data
        from spps_assistant.infrastructure.pdf_generator import (
            generate_cycle_guide_pdf, generate_peptide_info_pdf, generate_materials_pdf
        )
        from spps_assistant.infrastructure.docx_generator import (
            generate_cycle_guide_docx, generate_peptide_info_docx
        )
        from spps_assistant.infrastructure.xlsx_generator import generate_materials_xlsx

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()

        # 1. Build coupling cycles
        coupling_cycles = build_coupling_cycles(vessels)

        # 2 & 3. Calculate yields and solubility (use pre-computed if provided)
        if yield_results is None or solubility_results is None:
            yield_results, solubility_results = calc_yields_and_solubility(vessels, residue_info_map)

        # Build the shared cycle-guide view data once, from real domain
        # objects. Both the PDF/DOCX generators below and this method's
        # return value use this same data — the on-screen preview and the
        # exported documents can never drift apart.
        cycle_guide_data = build_cycle_guide_view_data(
            coupling_cycles, config, residue_info_map, today
        )

        # 4 & 5. Generate cycle guide (PDF + DOCX)
        safe_name = config.name.replace(' ', '_').replace('/', '-')
        cycle_guide_pdf = out_path / f"{safe_name}_cycle_guide.pdf"
        cycle_guide_docx = out_path / f"{safe_name}_cycle_guide.docx"
        peptide_info_pdf = out_path / f"{safe_name}_peptide_info.pdf"
        peptide_info_docx = out_path / f"{safe_name}_peptide_info.docx"
        materials_xlsx = out_path / f"{safe_name}_materials.xlsx"
        materials_pdf = out_path / f"{safe_name}_materials.pdf"

        generate_cycle_guide_pdf(
            path=cycle_guide_pdf,
            synthesis_name=config.name,
            date_str=today,
            vessels=vessels,
            cycle_guide_data=cycle_guide_data,
            config=config,
            yield_results=yield_results,
        )

        generate_cycle_guide_docx(
            path=cycle_guide_docx,
            synthesis_name=config.name,
            date_str=today,
            vessels=vessels,
            cycle_guide_data=cycle_guide_data,
            config=config,
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

        # 6.5 Materials explosion (XLSX + PDF), computed once and shared
        # with this method's return value so the GUI preview and the
        # exported files can never drift apart.
        materials_data = build_materials_view_data(vessels, residue_info_map, config)

        generate_materials_xlsx(
            path=materials_xlsx,
            synthesis_name=config.name,
            materials_rows=materials_data.rows,
        )

        generate_materials_pdf(
            path=materials_pdf,
            synthesis_name=config.name,
            materials_rows=materials_data.rows,
            config_summary=materials_data.config_summary,
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
            'materials_xlsx': str(materials_xlsx),
            'materials_pdf': str(materials_pdf),
        }, cycle_guide_data, materials_data
