"""spps-assistant materials — weekly materials explosion use case."""

import sys
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


def _parse_sequences_to_vessels(input_path: str, starting_num: int,
                                 config_defaults: Dict) -> List:
    """Parse FASTA and build Vessel objects, exiting on error."""
    from spps_assistant.infrastructure.fasta_parser import parse_fasta
    from spps_assistant.domain.sequence import tokenize, validate_tokens
    from spps_assistant.domain.constants import VALID_BASE_CODES
    from spps_assistant.domain.models import Vessel

    console.print(f"\n[bold]Parsing sequences from:[/bold] {input_path}")
    try:
        sequences = parse_fasta(Path(input_path))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    console.print(f"  Found [bold]{len(sequences)}[/bold] sequence(s).")

    vessels = []
    for i, (name, raw_seq) in enumerate(sequences):
        tokens = tokenize(raw_seq)
        errs = validate_tokens(tokens, VALID_BASE_CODES)
        if errs:
            for e in errs:
                console.print(f"  [red]{e}[/red]")
            sys.exit(1)
        rev = list(reversed(tokens))
        vessels.append(Vessel(
            number=starting_num + i,
            name=name,
            original_tokens=tokens,
            reversed_tokens=rev,
            resin_mass_g=float(config_defaults.get('fixed_resin_mass_g', 0.1)),
            substitution_mmol_g=0.3,
        ))
    return vessels


def _load_materials_map(materials_path: str) -> Dict:
    """Load residue info from a materials file into a dict."""
    from spps_assistant.infrastructure.materials_parser import load_materials_file
    from spps_assistant.domain.models import ResidueInfo

    residue_info_map: Dict = {}
    try:
        for rec in load_materials_file(Path(materials_path)):
            tok = rec['token']
            residue_info_map[tok] = ResidueInfo(
                token=tok, base_code=rec['base_code'],
                protection=rec['protection'], fmoc_mw=rec['fmoc_mw'],
                free_mw=rec['free_mw'], stock_conc=rec.get('stock_conc', 0.5),
                density_g_ml=rec.get('density_g_ml'),
                equivalents_multiplier=rec.get('equivalents_multiplier', 1.0),
            )
    except Exception as e:
        console.print(f"[yellow]Warning: {e}[/yellow]")
    return residue_info_map


def _auto_resolve_mw(unique_tokens, db, residue_info_map: Dict) -> Dict:
    """Fill missing tokens from DB or built-in defaults."""
    from spps_assistant.domain.models import ResidueInfo
    from spps_assistant.domain.sequence import parse_token as _pt
    from spps_assistant.domain.constants import FMOC_MW_DEFAULTS, FREE_RESIDUE_MW

    for tok in unique_tokens:
        if tok in residue_info_map:
            continue
        existing = db.get_residue(tok)
        if existing:
            residue_info_map[tok] = existing
            continue
        try:
            base, prot = _pt(tok)
        except ValueError:
            base, prot = tok, ''
        fmoc_mw = FMOC_MW_DEFAULTS.get(tok, FMOC_MW_DEFAULTS.get(base, 353.4))
        free_mw = FREE_RESIDUE_MW.get(base, 111.10)
        residue_info_map[tok] = ResidueInfo(
            token=tok, base_code=base, protection=prot,
            fmoc_mw=fmoc_mw, free_mw=free_mw, stock_conc=0.5,
        )
    return residue_info_map


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
    from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
    from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
    from spps_assistant.application.materials import MaterialsUseCase
    from spps_assistant.domain.sequence import get_unique_tokens
    from spps_assistant.domain.models import SynthesisConfig
    from spps_assistant.cli.prompts import prompt_residue_mws

    db = SQLiteRepository()
    config_repo = YAMLConfigRepository()
    config_defaults = config_repo.load()

    # Parse sequences
    starting_num = int(config_defaults.get('starting_vessel_number', 1))
    vessels = _parse_sequences_to_vessels(input_path, starting_num, config_defaults)

    # Load MW data
    residue_info_map: Dict = {}
    if materials_path:
        residue_info_map = _load_materials_map(materials_path)

    unique_tokens = get_unique_tokens(vessels)

    if not non_interactive:
        residue_info_map = prompt_residue_mws(unique_tokens, db, residue_info_map)
    else:
        residue_info_map = _auto_resolve_mw(unique_tokens, db, residue_info_map)

    config = SynthesisConfig(
        name=config_defaults.get('name', 'MySynthesis'),
        volume_mode=config_defaults.get('volume_mode', 'stoichiometry'),
        activator=config_defaults.get('activator', 'HBTU'),
        base=config_defaults.get('base', 'DIEA'),
        aa_equivalents=float(config_defaults.get('aa_equivalents', 3.0)),
        activator_equivalents=float(config_defaults.get('activator_equivalents', 3.0)),
        base_equivalents=float(config_defaults.get('base_equivalents', 6.0)),
    )

    eff_output = output_dir or config_defaults.get('output_directory', 'spps_output')
    use_case = MaterialsUseCase(db=db)

    try:
        paths = use_case.run(
            vessels=vessels,
            residue_info_map=residue_info_map,
            config=config,
            output_dir=eff_output,
            week=week,
        )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    console.print(Panel(
        "\n".join(f"  [green]{k}:[/green] {v}" for k, v in paths.items()),
        title="[bold green]Materials Files Generated[/bold green]",
        border_style="green",
    ))
