"""spps-assistant db — manage the residue MW database."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel

console = Console()


@click.command('db')
@click.option('--list', 'list_residues', is_flag=True, default=False,
              help='List all residue records in the database.')
@click.option('--export', 'export_path', default=None, type=click.Path(),
              help='Export residue library to a CSV file.')
@click.option('--import', 'import_path', default=None, type=click.Path(exists=True),
              help='Import materials library from a CSV or XLSX file.')
@click.option('--reset', is_flag=True, default=False,
              help='Reset (drop and recreate) the database. DESTRUCTIVE.')
@click.option('--add', 'add_token', default=None, type=str,
              help='Add a single residue by token (e.g. C(Trt)).')
def db(
    list_residues: bool,
    export_path: Optional[str],
    import_path: Optional[str],
    reset: bool,
    add_token: Optional[str],
) -> None:
    """Manage the SPPS residue MW database.

    The database stores Fmoc-AA molecular weights, synthesis defaults, and
    run history. Located at ~/.spps_assistant/spps_database.db.
    """
    from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository, _DB_PATH

    repository = SQLiteRepository()
    console.print(f"[dim]Database: {_DB_PATH}[/dim]")

    if reset:
        if not click.confirm(
            "[red]This will delete all residue MW data and synthesis history.[/red] Continue?",
            default=False,
        ):
            console.print("[yellow]Aborted.[/yellow]")
            return
        repository.reset()
        console.print("[green]Database reset complete.[/green]")
        return

    if import_path:
        console.print(f"[bold]Importing from:[/bold] {import_path}")
        try:
            n = repository.import_csv(Path(import_path))
            console.print(f"[green]Imported {n} residue record(s).[/green]")
        except Exception as e:
            console.print(f"[red]Import failed: {e}[/red]")
            sys.exit(1)

    if export_path:
        console.print(f"[bold]Exporting to:[/bold] {export_path}")
        try:
            repository.export_csv(Path(export_path))
            console.print(f"[green]Exported to {export_path}[/green]")
        except Exception as e:
            console.print(f"[red]Export failed: {e}[/red]")
            sys.exit(1)

    if add_token:
        _add_single_residue(repository, add_token)

    if list_residues:
        records = repository.list_residues()
        if not records:
            console.print("[yellow]No residue records in database.[/yellow]")
            console.print(
                "Run [bold]spps-assistant setup[/bold] to import the community library,\n"
                "or [bold]spps-assistant db --import community_mw_library.csv[/bold]"
            )
            return

        table = RichTable(title=f"Materials Library ({len(records)} records)")
        table.add_column("Token", style="bold cyan")
        table.add_column("Base")
        table.add_column("Protection")
        table.add_column("MW (g/mol)")
        table.add_column("Free MW (g/mol)")
        table.add_column("Density (g/mL)")
        table.add_column("Notes")

        for rec in records:
            density = rec.get('density_g_ml')
            density_str = f"{density:.3f}" if density is not None else '—'
            table.add_row(
                rec['token'],
                rec['base_code'],
                rec['protection'] or '—',
                f"{rec['fmoc_mw']:.1f}",
                f"{rec['free_mw']:.2f}",
                density_str,
                rec.get('notes', ''),
            )

        console.print(table)

    if not any([list_residues, export_path, import_path, reset, add_token]):
        # Default: show a brief status
        records = repository.list_residues()
        console.print(Panel(
            f"[bold]Residue records:[/bold] {len(records)}\n"
            f"[bold]Location:[/bold] {_DB_PATH}\n\n"
            "Options: --list  --export <path>  --import <path>  --reset  --add <token>",
            title="Database Status",
            border_style="blue",
        ))


def _add_single_residue(repository, token: str) -> None:
    """Interactively add a single residue to the database."""
    from spps_assistant.domain.sequence import parse_token
    from spps_assistant.domain.constants import FMOC_MW_DEFAULTS, FREE_RESIDUE_MW

    try:
        base, prot = parse_token(token)
    except ValueError as e:
        console.print(f"[red]Invalid token: {e}[/red]")
        return

    default_fmoc = FMOC_MW_DEFAULTS.get(token, FMOC_MW_DEFAULTS.get(base, 0.0))
    default_free = FREE_RESIDUE_MW.get(base, 111.10)

    console.print(f"\n[bold]Adding residue:[/bold] {token}")
    fmoc_mw = click.prompt("  Fmoc-MW (g/mol)", default=default_fmoc, type=float)
    free_mw = click.prompt("  Free AA residue MW (g/mol)", default=default_free, type=float)
    stock_conc = click.prompt("  Stock concentration (M)", default=0.5, type=float)
    notes = click.prompt("  Notes (optional)", default='', type=str)

    repository.save_residue(
        token=token,
        base_code=base,
        protection=prot,
        fmoc_mw=fmoc_mw,
        free_mw=free_mw,
        stock_conc=stock_conc,
        notes=notes,
    )
    console.print(f"[green]Saved {token} to database.[/green]")
