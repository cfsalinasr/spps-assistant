"""Reusable interactive prompt helpers for the SPPS CLI."""

from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel

from spps_assistant.domain.stoichiometry import derive_equivalents
from spps_assistant.domain.models import (
    ResidueInfo, SynthesisConfig, Vessel, YieldResult, SolubilityResult
)
from spps_assistant.domain.constants import (
    ACTIVATORS, BASES, DEPROTECTION_REAGENTS, VESSEL_LABELS, VESSEL_METHODS,
    VOLUME_MODES, RESIN_MASS_STRATEGIES, FMOC_MW_DEFAULTS, FREE_RESIDUE_MW,
    THREE_LETTER_CODE,
)
from spps_assistant.domain.sequence import parse_token

console = Console()


def prompt_residue_mws(
    tokens: List[str],
    db,
    residue_info_map: Dict[str, ResidueInfo],
) -> Dict[str, ResidueInfo]:
    """Prompt user to confirm or enter Fmoc-MW for each unique token.

    Checks DB first, then FMOC_MW_DEFAULTS, then prompts for missing values.
    Pre-populates DB with the entered value.

    Args:
        tokens: List of unique residue tokens
        db: DatabaseRepository instance
        residue_info_map: Existing map to update (modified in-place and returned)

    Returns:
        Updated residue_info_map
    """
    console.print("\n[bold cyan]Residue MW Lookup[/bold cyan]")

    for token in tokens:
        if token in residue_info_map:
            console.print(f"  [green]{token}[/green]: {residue_info_map[token].fmoc_mw:.1f} g/mol (already loaded)")
            continue

        # Check DB
        existing = db.get_residue(token)
        if existing:
            residue_info_map[token] = existing
            console.print(f"  [green]{token}[/green]: {existing.fmoc_mw:.1f} g/mol (from database)")
            continue

        # Check defaults
        try:
            base, prot = parse_token(token)
        except ValueError:
            base, prot = token, ''

        default_fmoc = FMOC_MW_DEFAULTS.get(token, FMOC_MW_DEFAULTS.get(base, 0.0))
        default_free = FREE_RESIDUE_MW.get(base, 111.10)

        if default_fmoc > 0:
            console.print(f"\n  Token [yellow]{token}[/yellow] not in database.")
            fmoc_mw = click.prompt(
                f"    Fmoc-MW for {token}",
                default=default_fmoc,
                type=float,
            )
        else:
            console.print(f"\n  [red]Token {token} not found in DB or defaults.[/red]")
            fmoc_mw = click.prompt(
                f"    Enter Fmoc-MW (g/mol) for {token}",
                type=float,
            )

        free_mw = click.prompt(
            f"    Free AA residue MW for {token}",
            default=default_free,
            type=float,
        )
        stock_conc = click.prompt(
            f"    Stock concentration (M) for {token}",
            default=0.5,
            type=float,
        )

        info = ResidueInfo(
            token=token,
            base_code=base,
            protection=prot,
            fmoc_mw=fmoc_mw,
            free_mw=free_mw,
            stock_conc=stock_conc,
        )
        residue_info_map[token] = info

        # Pre-populate DB
        try:
            db.save_residue(
                token=token,
                base_code=base,
                protection=prot,
                fmoc_mw=fmoc_mw,
                free_mw=free_mw,
                stock_conc=stock_conc,
            )
        except Exception as e:
            console.print(f"  [yellow]Warning: could not save to DB: {e}[/yellow]")

    return residue_info_map


def prompt_synthesis_config(config_defaults: Optional[Dict] = None) -> SynthesisConfig:
    """Interactive prompt to build a SynthesisConfig.

    Args:
        config_defaults: Dict of default values (from YAML config)

    Returns:
        Fully populated SynthesisConfig
    """
    d = config_defaults or {}
    console.print("\n[bold cyan]Synthesis Parameters[/bold cyan]")

    name = click.prompt(
        "  Synthesis name",
        default=d.get('name', 'MySynthesis'),
        type=str,
    )

    vessel_label = click.prompt(
        "  Vessel label",
        default=d.get('vessel_label', 'Vessel'),
        type=click.Choice(VESSEL_LABELS, case_sensitive=False),
        show_choices=True,
    )

    vessel_method = click.prompt(
        "  Vessel method",
        default=d.get('vessel_method', 'Teabag'),
        type=click.Choice(VESSEL_METHODS, case_sensitive=False),
        show_choices=True,
    )

    volume_mode = click.prompt(
        "  Volume calculation mode",
        default=d.get('volume_mode', 'stoichiometry'),
        type=click.Choice(VOLUME_MODES, case_sensitive=False),
        show_choices=True,
    )

    activator = click.prompt(
        "  Activator",
        default=d.get('activator', 'HBTU'),
        type=click.Choice(ACTIVATORS, case_sensitive=False),
        show_choices=True,
    )

    use_oxyma = click.confirm(
        "  Use Oxyma as additive?",
        default=d.get('use_oxyma', True),
    )

    base = click.prompt(
        "  Base",
        default=d.get('base', 'DIEA'),
        type=click.Choice(BASES, case_sensitive=False),
        show_choices=True,
    )

    deprotection_reagent = click.prompt(
        "  Deprotection reagent",
        default=d.get('deprotection_reagent', 'Piperidine 20%'),
        type=click.Choice(DEPROTECTION_REAGENTS, case_sensitive=False),
        show_choices=True,
    )

    aa_eq = click.prompt(
        "  Reactant excess (applied to all reagents; DIEA and Pyridine scale via\n"
        "  the Equivalents column in your materials file — DIEA x2, Pyridine x20)",
        default=float(d.get('aa_equivalents', 10.0)),
        type=float,
    )
    if aa_eq <= 0:
        click.echo("  Error: Reactant excess must be > 0.", err=True)
        raise SystemExit(1)
    act_eq, base_eq = derive_equivalents(aa_eq)

    include_bb = click.confirm(
        "  Include Bromophenol Blue test?",
        default=d.get('include_bb_test', True),
    )

    include_kaiser = click.confirm(
        "  Include Kaiser test?",
        default=d.get('include_kaiser_test', False),
    )

    starting_num = click.prompt(
        "  Starting vessel number",
        default=int(d.get('starting_vessel_number', 1)),
        type=int,
    )

    resin_strategy = click.prompt(
        "  Resin mass strategy",
        default=d.get('resin_mass_strategy', 'fixed'),
        type=click.Choice(RESIN_MASS_STRATEGIES, case_sensitive=False),
        show_choices=True,
    )

    fixed_mass = click.prompt(
        "  Fixed resin mass per vessel (g)",
        default=float(d.get('fixed_resin_mass_g', 0.1)),
        type=float,
    )

    target_yield = None
    if resin_strategy in ('target_highest', 'target_average'):
        target_yield = click.prompt(
            "  Target yield per vessel (mg)",
            default=float(d.get('target_yield_mg') or 10.0),
            type=float,
        )

    return SynthesisConfig(
        name=name,
        vessel_label=vessel_label,
        vessel_method=vessel_method,
        volume_mode=volume_mode,
        activator=activator,
        use_oxyma=use_oxyma,
        base=base,
        deprotection_reagent=deprotection_reagent,
        aa_equivalents=aa_eq,
        activator_equivalents=act_eq,
        base_equivalents=base_eq,
        include_bb_test=include_bb,
        include_kaiser_test=include_kaiser,
        starting_vessel_number=starting_num,
        resin_mass_strategy=resin_strategy,
        fixed_resin_mass_g=fixed_mass,
        target_yield_mg=target_yield,
    )


def prompt_resin_params(vessels: List[Vessel], config: SynthesisConfig) -> List[Vessel]:
    """Prompt user to confirm/enter resin parameters per vessel.

    Args:
        vessels: List of Vessel objects to update
        config: SynthesisConfig (used for defaults)

    Returns:
        Updated vessels list (modified in-place)
    """
    console.print("\n[bold cyan]Resin Parameters[/bold cyan]")
    for vessel in vessels:
        console.print(f"\n  [bold]Vessel {vessel.number}: {vessel.name}[/bold]")
        vessel.resin_mass_g = click.prompt(
            f"    Resin mass (g)",
            default=config.fixed_resin_mass_g,
            type=float,
        )
        vessel.substitution_mmol_g = click.prompt(
            f"    Substitution (mmol/g)",
            default=0.3,
            type=float,
        )
    return vessels


def display_reversal_table(vessels: List[Vessel]) -> bool:
    """Display a rich table showing N->C and reversed C->N sequences.

    Args:
        vessels: List of Vessel objects

    Returns:
        True if user confirms ('y'), False otherwise
    """
    console.print()
    table = RichTable(title="Sequence Reversal Preview (N→C → C→N for SPPS)")
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Name", style="bold")
    table.add_column("N→C (input)", style="green")
    table.add_column("C→N (SPPS order)", style="yellow")
    table.add_column("Length")

    for v in vessels:
        table.add_row(
            str(v.number),
            v.name,
            ''.join(v.original_tokens),
            ''.join(v.reversed_tokens),
            str(v.length),
        )

    console.print(table)
    return click.confirm("\nAre these sequences correct?", default=True)


def display_run_summary(
    vessels: List[Vessel],
    config: SynthesisConfig,
    yield_results: List[YieldResult],
    solubility_results: Dict[int, SolubilityResult],
) -> bool:
    """Display a full run summary table and ask for confirmation.

    Args:
        vessels: List of Vessel objects
        config: SynthesisConfig
        yield_results: Computed yield results
        solubility_results: Computed solubility results

    Returns:
        True if user confirms, False otherwise
    """
    console.print()

    # Config summary panel
    cfg_text = (
        f"[bold]Synthesis:[/bold] {config.name}  "
        f"[bold]Activator:[/bold] {config.activator}  "
        f"[bold]Base:[/bold] {config.base}  "
        f"[bold]Mode:[/bold] {config.volume_mode}  "
        f"[bold]Oxyma:[/bold] {'Yes' if config.use_oxyma else 'No'}\n"
        f"[bold]Reactant excess:[/bold] {config.aa_equivalents}x  "
        f"(DIEA x2 = {config.aa_equivalents * 2:.0f} eq, "
        f"Pyridine x20 = {config.aa_equivalents * 20:.0f} eq)  "
        f"[bold]Deprotection:[/bold] {config.deprotection_reagent}"
    )
    console.print(Panel(cfg_text, title="Synthesis Configuration", border_style="blue"))

    # Per-vessel summary
    yield_map = {yr.vessel_number: yr for yr in yield_results}
    table = RichTable(title="Vessel Summary")
    table.add_column("#", style="bold cyan")
    table.add_column("Name")
    table.add_column("Sequence")
    table.add_column("Len")
    table.add_column("MW (Da)")
    table.add_column("Yield est. (mg)")
    table.add_column("Hydrophobic?")
    table.add_column("Light sensitive?")

    for v in vessels:
        yr = yield_map.get(v.number)
        sol = solubility_results.get(v.number)
        seq = ''.join(v.original_tokens)
        table.add_row(
            str(v.number),
            v.name,
            seq[:30] + ('...' if len(seq) > 30 else ''),
            str(v.length),
            f"{yr.peptide_mw:.1f}" if yr else '—',
            f"{yr.theoretical_yield_mg:.1f}" if yr else '—',
            '[yellow]Yes[/yellow]' if (sol and sol.is_hydrophobic) else '[green]No[/green]',
            '[red]Yes[/red]' if (sol and sol.light_sensitive) else 'No',
        )

    console.print(table)
    return click.confirm("\nProceed with synthesis guide generation?", default=True)
