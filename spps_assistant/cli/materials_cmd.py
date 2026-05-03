"""spps-assistant materials — weekly materials explosion use case."""

import sys
import traceback
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command('materials')
@click.option('--input', '-i', 'input_path', required=True, type=click.Path(exists=True),
              help='FASTA file with peptide sequences.')
@click.option('--week', '-w', default=None, type=int,
              help='Week number for labeling the materials list.')
@click.option('--output', '-o', 'output_dir', default=None, type=click.Path(),
              help='Output directory (default: from config or "spps_output").')
@click.option('--materials', '-m', 'materials_path', default=None, type=click.Path(exists=True),
              help='Optional Fmoc-MW library CSV/XLSX.')
@click.option('--non-interactive', is_flag=True, default=False,
              help='Use defaults without interactive prompts.')
def materials(
    input_path: str,
    week: Optional[int],
    output_dir: Optional[str],
    materials_path: Optional[str],
    non_interactive: bool,
) -> None:
    """Generate a weekly materials (reagent) list for all peptides.

    Produces both an XLSX and PDF materials list showing the Fmoc-AA to
    weigh and volumes to prepare for the synthesis run.
    """
    from pathlib import Path
    from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
    from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
    from spps_assistant.application.materials import MaterialsUseCase
    from spps_assistant.application.synthesis_guide import build_config_from_defaults
    from spps_assistant.application.sequence_loader import (
        parse_and_validate_sequences, build_vessels, load_materials_map,
    )
    from spps_assistant.domain.sequence import get_unique_tokens
    from spps_assistant.cli.prompts import prompt_residue_mws, auto_resolve_residues

    db = SQLiteRepository()
    config_repo = YAMLConfigRepository()
    config_defaults = config_repo.load()
    starting_num = int(config_defaults.get('starting_vessel_number', 1))

    # Parse sequences
    console.print(f"\n[bold]Parsing sequences from:[/bold] {input_path}")
    try:
        parsed_sequences = parse_and_validate_sequences(Path(input_path))
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)
    console.print(f"  Found [bold]{len(parsed_sequences)}[/bold] sequence(s).")

    fixed_resin_mass_g = float(config_defaults.get('fixed_resin_mass_g', 0.1))
    substitution_mmol_g = float(config_defaults.get('substitution_mmol_g', 0.3))
    vessels = build_vessels(parsed_sequences, starting_num,
                            resin_mass_g=fixed_resin_mass_g,
                            substitution_mmol_g=substitution_mmol_g)

    # Load MW data
    residue_info_map = {}
    if materials_path:
        console.print(f"\n[bold]Loading Fmoc-MW from materials file:[/bold] {materials_path}")
        try:
            residue_info_map = load_materials_map(Path(materials_path))
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)
        console.print(f"  Loaded {len(residue_info_map)} residues from materials file.")

    unique_tokens = get_unique_tokens(vessels)
    if not non_interactive:
        residue_info_map = prompt_residue_mws(unique_tokens, db, residue_info_map)
    else:
        residue_info_map = auto_resolve_residues(unique_tokens, db, residue_info_map)

    try:
        config = build_config_from_defaults(config_defaults, output_dir=output_dir,
                                            starting_num=starting_num)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    use_case = MaterialsUseCase(db=db)

    try:
        paths = use_case.run(
            vessels=vessels,
            residue_info_map=residue_info_map,
            config=config,
            output_dir=config.output_directory,
            week=week,
        )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)

    console.print(Panel(
        "\n".join(f"  [green]{k}:[/green] {v}" for k, v in paths.items()),
        title="[bold green]Materials Files Generated[/bold green]",
        border_style="green",
    ))
