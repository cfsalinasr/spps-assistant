"""Entry point for the SPPS Synthesis Assistant CLI."""

import click

from spps_assistant import __version__


@click.group()
@click.version_option(version=__version__, prog_name='spps-assistant')
def cli() -> None:
    """SPPS Synthesis Assistant — parallel SPPS workflow management.

    A GMP-compliant CLI tool replacing the legacy Spys.exe for planning,
    documenting, and executing parallel solid phase peptide syntheses.

    Common usage:

    \b
        spps-assistant setup          # first-time configuration wizard
        spps-assistant generate \\
            --input sequences.fasta   # generate cycle guide + peptide info
        spps-assistant materials \\
            --input sequences.fasta   # weekly materials explosion
        spps-assistant template       # generate blank materials templates
        spps-assistant db --list      # view residue MW library
        spps-assistant config --show  # view current configuration
    """


# Register subcommands lazily to avoid circular imports
def _register_commands() -> None:
    from spps_assistant.cli.setup_cmd import setup
    from spps_assistant.cli.generate_cmd import generate
    from spps_assistant.cli.materials_cmd import materials
    from spps_assistant.cli.template_cmd import template
    from spps_assistant.cli.db_cmd import db
    from spps_assistant.cli.config_cmd import config

    cli.add_command(setup)
    cli.add_command(generate)
    cli.add_command(materials)
    cli.add_command(template)
    cli.add_command(db)
    cli.add_command(config)


_register_commands()
