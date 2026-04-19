"""spps-assistant config — view and modify configuration."""

import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel

console = Console()


@click.command('config')
@click.option('--show', is_flag=True, default=False,
              help='Display current configuration values.')
@click.option('--set', 'set_args', nargs=2, type=str, default=None,
              metavar='FIELD VALUE',
              help='Set a configuration field. Example: --set activator DIC')
def config(show: bool, set_args: Optional[tuple]) -> None:
    """View or modify SPPS Synthesis Assistant configuration.

    \b
    Configuration file: ~/.spps_assistant/spps_config.yaml

    \b
    Examples:
        spps-assistant config --show
        spps-assistant config --set activator DIC
        spps-assistant config --set aa_equivalents 4.0
        spps-assistant config --set volume_mode legacy
    """
    from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository, _CONFIG_PATH

    config_repo = YAMLConfigRepository()
    console.print(f"[dim]Config file: {_CONFIG_PATH}[/dim]")

    if set_args:
        field, raw_value = set_args
        # Type-coerce value
        value = _coerce_value(raw_value)
        config_repo.set_field(field, value)
        console.print(f"[green]Set [bold]{field}[/bold] = {value!r}[/green]")

    if show or (not show and not set_args):
        data = config_repo.load()
        table = RichTable(title="SPPS Configuration")
        table.add_column("Field", style="bold cyan")
        table.add_column("Value")
        table.add_column("Type", style="dim")

        for k, v in sorted(data.items()):
            table.add_row(k, str(v) if v is not None else '[dim]None[/dim]', type(v).__name__)

        console.print(table)


def _coerce_value(raw: str):
    """Try to coerce a string value to bool, int, float, or keep as str."""
    if raw.lower() in ('true', 'yes'):
        return True
    if raw.lower() in ('false', 'no'):
        return False
    if raw.lower() in ('none', 'null', ''):
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw
