"""spps-assistant setup — first-time configuration wizard."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command('setup')
def setup() -> None:
    """Guided first-time setup wizard for SPPS Synthesis Assistant.

    Walks through all configuration parameters and optionally imports
    the bundled community Fmoc-AA MW library.
    """
    from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
    from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
    from spps_assistant.cli.prompts import prompt_synthesis_config

    console.print(Panel(
        "[bold cyan]Welcome to SPPS Synthesis Assistant v1.0[/bold cyan]\n\n"
        "This wizard will configure your default synthesis parameters and\n"
        "optionally import the community Fmoc-AA MW library.\n\n"
        "Settings are saved to [bold]~/.spps_assistant/spps_config.yaml[/bold]",
        title="Setup Wizard",
        border_style="green",
    ))
    console.print()

    config_repo = YAMLConfigRepository()
    existing = config_repo.load()

    # Prompt all config fields
    synth_config = prompt_synthesis_config(existing)

    # Save
    config_dict = {
        'name': synth_config.name,
        'vessel_label': synth_config.vessel_label,
        'vessel_method': synth_config.vessel_method,
        'volume_mode': synth_config.volume_mode,
        'activator': synth_config.activator,
        'use_oxyma': synth_config.use_oxyma,
        'base': synth_config.base,
        'deprotection_reagent': synth_config.deprotection_reagent,
        'aa_equivalents': synth_config.aa_equivalents,
        'activator_equivalents': synth_config.activator_equivalents,
        'base_equivalents': synth_config.base_equivalents,
        'include_bb_test': synth_config.include_bb_test,
        'include_kaiser_test': synth_config.include_kaiser_test,
        'starting_vessel_number': synth_config.starting_vessel_number,
        'output_directory': synth_config.output_directory,
        'resin_mass_strategy': synth_config.resin_mass_strategy,
        'fixed_resin_mass_g': synth_config.fixed_resin_mass_g,
        'target_yield_mg': synth_config.target_yield_mg,
    }
    config_repo.save(config_dict)
    console.print("[green]Configuration saved.[/green]")

    # Import community library
    if click.confirm(
        "\nImport community Fmoc-AA MW library? "
        "(adds common protected amino acids to your database)",
        default=True,
    ):
        db = SQLiteRepository()
        # Find the CSV in the package directory
        package_dir = Path(__file__).parent.parent.parent
        library_path = package_dir / 'community_mw_library.csv'
        if not library_path.exists():
            # Try sibling of the package directory
            library_path = Path(__file__).parent.parent.parent / 'community_mw_library.csv'

        if library_path.exists():
            try:
                n = db.import_csv(library_path)
                console.print(f"[green]Imported {n} residue records from community library.[/green]")
            except Exception as e:
                console.print(f"[red]Import failed: {e}[/red]")
        else:
            console.print(
                f"[yellow]Community library not found at {library_path}.[/yellow]\n"
                "You can import it later with: [bold]spps-assistant db --import community_mw_library.csv[/bold]"
            )

    console.print(Panel(
        "[bold green]Setup complete![/bold green]\n\n"
        "You can now run:\n"
        "  [bold]spps-assistant generate --input sequences.fasta[/bold]\n"
        "  [bold]spps-assistant materials --input sequences.fasta[/bold]\n\n"
        "Configuration file: [bold]~/.spps_assistant/spps_config.yaml[/bold]\n"
        "Database: [bold]~/.spps_assistant/spps_database.db[/bold]",
        title="Setup Complete",
        border_style="green",
    ))
