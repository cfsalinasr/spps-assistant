"""spps-assistant generate — full synthesis guide generation workflow."""

import sys
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


def _parse_and_validate_sequences(input_path: str):
    """Parse FASTA file and validate all sequences. Returns parsed_sequences or exits."""
    from spps_assistant.infrastructure.fasta_parser import parse_fasta
    from spps_assistant.domain.sequence import tokenize, validate_tokens
    from spps_assistant.domain.constants import VALID_BASE_CODES

    console.print(f"\n[bold]Parsing sequences from:[/bold] {input_path}")
    try:
        sequences = parse_fasta(Path(input_path))
    except Exception as e:
        console.print(f"[red]Error parsing sequence file: {e}[/red]")
        sys.exit(1)

    console.print(f"  Found [bold]{len(sequences)}[/bold] sequence(s).")

    errors_found = False
    parsed_sequences = []
    for name, raw_seq in sequences:
        tokens = tokenize(raw_seq)
        errs = validate_tokens(tokens, VALID_BASE_CODES)
        if errs:
            console.print(f"  [red]Errors in sequence '{name}':[/red]")
            for err in errs:
                console.print(f"    - {err}")
            errors_found = True
        else:
            parsed_sequences.append((name, raw_seq, tokens))

    if errors_found:
        console.print("[red]Fix sequence errors before proceeding.[/red]")
        sys.exit(1)

    return parsed_sequences


def _build_vessels(parsed_sequences, starting_num: int):
    """Build Vessel objects from parsed sequences."""
    from spps_assistant.domain.models import Vessel

    vessels = []
    for i, (name, _raw_seq, tokens) in enumerate(parsed_sequences):
        rev_tokens = list(reversed(tokens))
        vessels.append(Vessel(
            number=starting_num + i,
            name=name,
            original_tokens=tokens,
            reversed_tokens=rev_tokens,
        ))
    return vessels


def _load_materials_file(materials_path: str):
    """Load residue info from a materials file. Returns residue_info_map dict."""
    from spps_assistant.infrastructure.materials_parser import load_materials_file
    from spps_assistant.domain.models import ResidueInfo

    residue_info_map: Dict = {}
    console.print(f"\n[bold]Loading Fmoc-MW from materials file:[/bold] {materials_path}")
    try:
        mat_records = load_materials_file(Path(materials_path))
        for rec in mat_records:
            tok = rec['token']
            residue_info_map[tok] = ResidueInfo(
                token=tok,
                base_code=rec['base_code'],
                protection=rec['protection'],
                fmoc_mw=rec['fmoc_mw'],
                free_mw=rec['free_mw'],
                stock_conc=rec.get('stock_conc', 0.5),
                density_g_ml=rec.get('density_g_ml'),
                equivalents_multiplier=rec.get('equivalents_multiplier', 1.0),
            )
        console.print(f"  Loaded {len(residue_info_map)} residues from materials file.")
    except Exception as e:
        console.print(f"[red]Could not load materials file: {e}[/red]")
        sys.exit(1)
    return residue_info_map




def _build_non_interactive_config(config_defaults: Dict, volume_mode: Optional[str],
                                  output_dir: Optional[str], starting_num: int):
    """Build a SynthesisConfig from config defaults without user prompts."""
    from spps_assistant.domain.models import SynthesisConfig
    from spps_assistant.domain.stoichiometry import derive_equivalents

    aa_eq = float(config_defaults.get('aa_equivalents', 3.0))
    if aa_eq <= 0:
        console.print("[red]Reactant excess (aa_equivalents) must be > 0.[/red]")
        sys.exit(1)
    act_eq, base_eq = derive_equivalents(aa_eq)

    return SynthesisConfig(
        name=config_defaults.get('name', 'MySynthesis'),
        vessel_label=config_defaults.get('vessel_label', 'Vessel'),
        vessel_method=config_defaults.get('vessel_method', 'Teabag'),
        volume_mode=volume_mode or config_defaults.get('volume_mode', 'stoichiometry'),
        activator=config_defaults.get('activator', 'HBTU'),
        use_oxyma=config_defaults.get('use_oxyma', True),
        base=config_defaults.get('base', 'DIEA'),
        deprotection_reagent=config_defaults.get('deprotection_reagent', 'Piperidine 20%'),
        aa_equivalents=aa_eq,
        activator_equivalents=act_eq,
        base_equivalents=base_eq,
        include_bb_test=config_defaults.get('include_bb_test', True),
        include_kaiser_test=config_defaults.get('include_kaiser_test', False),
        starting_vessel_number=starting_num,
        output_directory=output_dir or config_defaults.get('output_directory', 'spps_output'),
        resin_mass_strategy=config_defaults.get('resin_mass_strategy', 'fixed'),
        fixed_resin_mass_g=float(config_defaults.get('fixed_resin_mass_g', 0.1)),
        target_yield_mg=config_defaults.get('target_yield_mg'),
    )


def _apply_target_resin_mass(vessels, config, residue_info_map: Dict):
    """Back-calculate resin mass for target-yield strategy."""
    from spps_assistant.domain.yield_calc import back_calc_resin_mass as _bcr
    from spps_assistant.domain.yield_calc import calc_peptide_mw
    from spps_assistant.domain.constants import FREE_RESIDUE_MW

    for vessel in vessels:
        pep_mw = calc_peptide_mw(vessel.original_tokens, FREE_RESIDUE_MW, residue_info_map)
        try:
            vessel.resin_mass_g = _bcr(
                config.target_yield_mg,
                vessel.substitution_mmol_g,
                vessel.length,
                pep_mw,
            )
        except Exception as e:
            raise ValueError(
                f"Could not back-calculate resin mass for vessel "
                f"{vessel.number} ({vessel.name}): {e}"
            ) from e


def _calc_yields_and_solubility(vessels, residue_info_map: Dict):
    """Compute yield results and solubility results for all vessels."""
    from spps_assistant.domain.yield_calc import (
        calc_peptide_mw, calc_theoretical_yield, build_yield_formula
    )
    from spps_assistant.domain.models import YieldResult
    from spps_assistant.domain.solubility import analyze_peptide
    from spps_assistant.domain.constants import FREE_RESIDUE_MW

    yield_results = []
    for vessel in vessels:
        pep_mw = calc_peptide_mw(vessel.original_tokens, FREE_RESIDUE_MW, residue_info_map)
        yield_mg = calc_theoretical_yield(
            vessel.resin_mass_g, vessel.substitution_mmol_g, vessel.length, pep_mw
        )
        formula = build_yield_formula(
            vessel.resin_mass_g, vessel.substitution_mmol_g, vessel.length, pep_mw, yield_mg
        )
        yield_results.append(YieldResult(
            vessel_number=vessel.number,
            vessel_name=vessel.name,
            peptide_mw=round(pep_mw, 2),
            sequence_length=vessel.length,
            resin_mass_g=vessel.resin_mass_g,
            substitution_mmol_g=vessel.substitution_mmol_g,
            theoretical_yield_mg=round(yield_mg, 2),
            formula_shown=formula,
        ))

    solubility_results = {}
    for vessel in vessels:
        sol = analyze_peptide(vessel.original_tokens)
        solubility_results[vessel.number] = sol

    return yield_results, solubility_results


def _confirm_reversal_or_abort(vessels, non_interactive: bool) -> None:
    """Show the reversal confirmation table and abort if the user declines."""
    if non_interactive:
        return
    from spps_assistant.cli.prompts import display_reversal_table
    if not display_reversal_table(vessels):
        console.print("[yellow]Aborted by user.[/yellow]")
        sys.exit(0)


def _confirm_run_or_abort(vessels, config, yield_results, solubility_results,
                          non_interactive: bool) -> None:
    """Show the run summary and abort if the user declines."""
    if non_interactive:
        return
    from spps_assistant.cli.prompts import display_run_summary
    if not display_run_summary(vessels, config, yield_results, solubility_results):
        console.print("[yellow]Aborted by user.[/yellow]")
        sys.exit(0)


@click.command('generate')
@click.option('--input', '-i', 'input_path', required=True, type=click.Path(exists=True),
              help='FASTA file with peptide sequences.')
@click.option('--materials', '-m', 'materials_path', default=None, type=click.Path(exists=True),
              help='Optional materials CSV/XLSX with pre-defined Fmoc-MW values.')
@click.option('--output', '-o', 'output_dir', default=None, type=click.Path(),
              help='Output directory for generated files (default: spps_output).')
@click.option('--volume-mode', default=None,
              type=click.Choice(['stoichiometry', 'legacy'], case_sensitive=False),
              help='Volume calculation mode (overrides config).')
@click.option('--dry-run', is_flag=True, default=False,
              help='Validate and preview without writing output files.')
@click.option('--non-interactive', is_flag=True, default=False,
              help='Skip interactive prompts and use config/defaults for everything.')
def generate(
    input_path: str,
    materials_path: Optional[str],
    output_dir: Optional[str],
    volume_mode: Optional[str],
    dry_run: bool,
    non_interactive: bool,
) -> None:
    """Generate a complete SPPS cycle guide and peptide information sheets.

    Reads peptide sequences from INPUT, interactively configures synthesis
    parameters, and outputs PDF + DOCX cycle guides and peptide info documents.

    \b
    Output files:
        <name>_cycle_guide.pdf   — GMP cycle guide (one page per coupling cycle)
        <name>_cycle_guide.docx  — DOCX version of the cycle guide
        <name>_peptide_info.pdf  — Peptide physicochemical properties
        <name>_peptide_info.docx — DOCX version of peptide info
    """
    from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
    from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
    from spps_assistant.application.synthesis_guide import SynthesisGuideUseCase
    from spps_assistant.domain.sequence import get_unique_tokens
    from spps_assistant.cli.prompts import (
        prompt_residue_mws, prompt_synthesis_config, prompt_resin_params,
        auto_resolve_residues,
    )

    db = SQLiteRepository()
    config_repo = YAMLConfigRepository()

    # ------------------------------------------------------------------ #
    # Step a-b: Parse FASTA and validate                                   #
    # ------------------------------------------------------------------ #
    parsed_sequences = _parse_and_validate_sequences(input_path)

    # ------------------------------------------------------------------ #
    # Step c: Reverse sequences (C->N for SPPS)                           #
    # ------------------------------------------------------------------ #
    config_defaults = config_repo.load()
    starting_num = int(config_defaults.get('starting_vessel_number', 1))
    vessels: List = _build_vessels(parsed_sequences, starting_num)

    # ------------------------------------------------------------------ #
    # Step d-e: Show reversal confirmation table                          #
    # ------------------------------------------------------------------ #
    _confirm_reversal_or_abort(vessels, non_interactive)

    # ------------------------------------------------------------------ #
    # Step f: Load residue MW from materials file or DB                   #
    # ------------------------------------------------------------------ #
    residue_info_map: Dict = {}
    if materials_path:
        residue_info_map = _load_materials_file(materials_path)

    # ------------------------------------------------------------------ #
    # Step g: Prompt for missing residue MWs                              #
    # ------------------------------------------------------------------ #
    unique_tokens = get_unique_tokens(vessels)

    if not non_interactive:
        residue_info_map = prompt_residue_mws(unique_tokens, db, residue_info_map)
    else:
        residue_info_map = auto_resolve_residues(unique_tokens, db, residue_info_map)

    # ------------------------------------------------------------------ #
    # Step h: Prompt synthesis parameters                                  #
    # ------------------------------------------------------------------ #
    if non_interactive:
        config = _build_non_interactive_config(
            config_defaults, volume_mode, output_dir, starting_num
        )
    else:
        config = prompt_synthesis_config(config_defaults)
        if volume_mode:
            config.volume_mode = volume_mode

    if output_dir:
        config.output_directory = output_dir

    # ------------------------------------------------------------------ #
    # Step i: Set resin params on vessels                                  #
    # ------------------------------------------------------------------ #
    for vessel in vessels:
        vessel.resin_mass_g = config.fixed_resin_mass_g
        vessel.substitution_mmol_g = 0.3  # will be prompted if interactive

    if not non_interactive:
        vessels = prompt_resin_params(vessels, config)

    # If target strategy, back-calculate resin mass
    if config.resin_mass_strategy != 'fixed' and config.target_yield_mg:
        _apply_target_resin_mass(vessels, config, residue_info_map)

    # ------------------------------------------------------------------ #
    # Step j-k: Calculate yields and solubility                           #
    # ------------------------------------------------------------------ #
    yield_results, solubility_results = _calc_yields_and_solubility(
        vessels, residue_info_map
    )

    # ------------------------------------------------------------------ #
    # Step l: Run summary confirmation                                     #
    # ------------------------------------------------------------------ #
    _confirm_run_or_abort(vessels, config, yield_results, solubility_results, non_interactive)

    # ------------------------------------------------------------------ #
    # Step m: Generate output files                                        #
    # ------------------------------------------------------------------ #
    if dry_run:
        console.print(Panel(
            "[bold yellow]Dry run mode — no files written.[/bold yellow]\n\n"
            f"Would generate files in: [bold]{config.output_directory}[/bold]\n"
            f"Vessels: {len(vessels)}\n"
            f"Coupling cycles: {max(v.length for v in vessels) if vessels else 0}",
            title="Dry Run",
            border_style="yellow",
        ))
        return

    console.print(f"\n[bold]Generating output files in:[/bold] {config.output_directory}")

    use_case = SynthesisGuideUseCase(db=db, config_repo=config_repo)
    try:
        output_paths = use_case.run(
            output_dir=config.output_directory,
            config=config,
            residue_info_map=residue_info_map,
            vessels=vessels,
        )
    except Exception as e:
        console.print(f"[red]Error generating files: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Step n: Report                                                       #
    # ------------------------------------------------------------------ #
    console.print(Panel(
        "\n".join(f"  [green]{label}:[/green] {path}"
                  for label, path in output_paths.items()),
        title="[bold green]Generated Files[/bold green]",
        border_style="green",
    ))
