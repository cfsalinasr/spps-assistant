"""spps-assistant generate — full synthesis guide generation workflow."""

import sys
import traceback
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


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
    from pathlib import Path
    from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
    from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
    from spps_assistant.application.synthesis_guide import (
        SynthesisGuideUseCase, build_config_from_defaults,
        calc_yields_and_solubility, apply_target_resin_mass,
    )
    from spps_assistant.application.sequence_loader import (
        parse_and_validate_sequences, build_vessels, load_materials_map,
    )
    from spps_assistant.domain.sequence import get_unique_tokens
    from spps_assistant.cli.prompts import (
        prompt_residue_mws, prompt_synthesis_config, prompt_resin_params,
        auto_resolve_residues,
    )

    db = SQLiteRepository()
    config_repo = YAMLConfigRepository()
    config_defaults = config_repo.load()
    starting_num = int(config_defaults.get('starting_vessel_number', 1))

    # ------------------------------------------------------------------ #
    # Step a-b: Parse and validate sequences                               #
    # ------------------------------------------------------------------ #
    console.print(f"\n[bold]Parsing sequences from:[/bold] {input_path}")
    try:
        parsed_sequences = parse_and_validate_sequences(Path(input_path))
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)
    console.print(f"  Found [bold]{len(parsed_sequences)}[/bold] sequence(s).")

    # ------------------------------------------------------------------ #
    # Step c: Build vessels                                                #
    # ------------------------------------------------------------------ #
    substitution_mmol_g = float(config_defaults.get('substitution_mmol_g', 0.3))
    vessels = build_vessels(parsed_sequences, starting_num, substitution_mmol_g=substitution_mmol_g)

    # ------------------------------------------------------------------ #
    # Step d-e: Show reversal confirmation table                           #
    # ------------------------------------------------------------------ #
    _confirm_reversal_or_abort(vessels, non_interactive)

    # ------------------------------------------------------------------ #
    # Step f: Load residue MW from materials file                          #
    # ------------------------------------------------------------------ #
    residue_info_map = {}
    if materials_path:
        console.print(f"\n[bold]Loading Fmoc-MW from materials file:[/bold] {materials_path}")
        try:
            residue_info_map = load_materials_map(Path(materials_path))
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)
        console.print(f"  Loaded {len(residue_info_map)} residues from materials file.")

    # ------------------------------------------------------------------ #
    # Step g: Resolve missing residue MWs                                  #
    # ------------------------------------------------------------------ #
    unique_tokens = get_unique_tokens(vessels)
    if not non_interactive:
        residue_info_map = prompt_residue_mws(unique_tokens, db, residue_info_map)
    else:
        residue_info_map = auto_resolve_residues(unique_tokens, db, residue_info_map)

    # ------------------------------------------------------------------ #
    # Step h: Build synthesis config                                        #
    # ------------------------------------------------------------------ #
    if non_interactive:
        try:
            config = build_config_from_defaults(config_defaults, volume_mode, output_dir,
                                                starting_num)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)
    else:
        config = prompt_synthesis_config(config_defaults)
        if volume_mode:
            config.volume_mode = volume_mode

    if output_dir:
        config.output_directory = output_dir

    # ------------------------------------------------------------------ #
    # Step i: Set resin params on vessels                                   #
    # ------------------------------------------------------------------ #
    for vessel in vessels:
        vessel.resin_mass_g = config.fixed_resin_mass_g

    if not non_interactive:
        vessels = prompt_resin_params(vessels, config)

    # If target strategy, back-calculate resin mass
    if config.resin_mass_strategy != 'fixed' and config.target_yield_mg:
        try:
            apply_target_resin_mass(vessels, config, residue_info_map)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)

    # ------------------------------------------------------------------ #
    # Step j-k: Calculate yields and solubility                            #
    # ------------------------------------------------------------------ #
    yield_results, solubility_results = calc_yields_and_solubility(vessels, residue_info_map)

    # ------------------------------------------------------------------ #
    # Step l: Run summary confirmation                                      #
    # ------------------------------------------------------------------ #
    _confirm_run_or_abort(vessels, config, yield_results, solubility_results, non_interactive)

    # ------------------------------------------------------------------ #
    # Step m: Generate output files                                         #
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
        traceback.print_exc()
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Step n: Report                                                        #
    # ------------------------------------------------------------------ #
    console.print(Panel(
        "\n".join(f"  [green]{label}:[/green] {path}"
                  for label, path in output_paths.items()),
        title="[bold green]Generated Files[/bold green]",
        border_style="green",
    ))
