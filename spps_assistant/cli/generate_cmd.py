"""spps-assistant generate — full synthesis guide generation workflow."""

import sys
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command('generate')
@click.option('--input', '-i', 'input_path', required=True, type=click.Path(exists=True),
              help='FASTA file (or plain text/CSV) with peptide sequences.')
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
    from spps_assistant.infrastructure.fasta_parser import parse_fasta
    from spps_assistant.infrastructure.materials_parser import load_materials_file
    from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
    from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
    from spps_assistant.application.synthesis_guide import SynthesisGuideUseCase
    from spps_assistant.domain.sequence import (
        tokenize, reverse_sequence, validate_tokens, get_unique_tokens
    )
    from spps_assistant.domain.constants import VALID_BASE_CODES
    from spps_assistant.domain.models import Vessel, ResidueInfo
    from spps_assistant.domain.yield_calc import (
        calc_peptide_mw, calc_theoretical_yield, back_calc_resin_mass
    )
    from spps_assistant.domain.constants import FREE_RESIDUE_MW
    from spps_assistant.domain.solubility import analyze_peptide
    from spps_assistant.cli.prompts import (
        prompt_residue_mws, prompt_synthesis_config, prompt_resin_params,
        display_reversal_table, display_run_summary
    )

    db = SQLiteRepository()
    config_repo = YAMLConfigRepository()

    # ------------------------------------------------------------------ #
    # Step a: Parse FASTA                                                  #
    # ------------------------------------------------------------------ #
    console.print(f"\n[bold]Parsing sequences from:[/bold] {input_path}")
    try:
        sequences = parse_fasta(Path(input_path))
    except Exception as e:
        console.print(f"[red]Error parsing sequence file: {e}[/red]")
        sys.exit(1)

    console.print(f"  Found [bold]{len(sequences)}[/bold] sequence(s).")

    # ------------------------------------------------------------------ #
    # Step b: Tokenize and validate                                        #
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # Step c: Reverse sequences (C->N for SPPS)                           #
    # ------------------------------------------------------------------ #
    config_defaults = config_repo.load()
    starting_num = int(config_defaults.get('starting_vessel_number', 1))

    vessels: List[Vessel] = []
    for i, (name, raw_seq, tokens) in enumerate(parsed_sequences):
        rev_tokens = list(reversed(tokens))
        vessels.append(Vessel(
            number=starting_num + i,
            name=name,
            original_tokens=tokens,
            reversed_tokens=rev_tokens,
        ))

    # ------------------------------------------------------------------ #
    # Step d-e: Show reversal confirmation table                          #
    # ------------------------------------------------------------------ #
    if not non_interactive:
        confirmed = display_reversal_table(vessels)
        if not confirmed:
            console.print("[yellow]Aborted by user.[/yellow]")
            sys.exit(0)

    # ------------------------------------------------------------------ #
    # Step f: Load residue MW from materials file or DB                   #
    # ------------------------------------------------------------------ #
    residue_info_map: Dict[str, ResidueInfo] = {}

    if materials_path:
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
                )
            console.print(f"  Loaded {len(residue_info_map)} residues from materials file.")
        except Exception as e:
            console.print(f"[yellow]Warning: could not load materials file: {e}[/yellow]")

    # ------------------------------------------------------------------ #
    # Step g: Prompt for missing residue MWs                              #
    # ------------------------------------------------------------------ #
    unique_tokens = get_unique_tokens(vessels)

    if not non_interactive:
        residue_info_map = prompt_residue_mws(unique_tokens, db, residue_info_map)
    else:
        # Auto-resolve from DB then defaults
        for tok in unique_tokens:
            if tok in residue_info_map:
                continue
            existing = db.get_residue(tok)
            if existing:
                residue_info_map[tok] = existing
                continue
            # Fall back to defaults
            from spps_assistant.domain.sequence import parse_token as _pt
            from spps_assistant.domain.constants import FMOC_MW_DEFAULTS, FREE_RESIDUE_MW
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

    # ------------------------------------------------------------------ #
    # Step h: Prompt synthesis parameters                                  #
    # ------------------------------------------------------------------ #
    if non_interactive:
        from spps_assistant.domain.models import SynthesisConfig
        config = SynthesisConfig(
            name=config_defaults.get('name', 'MySynthesis'),
            vessel_label=config_defaults.get('vessel_label', 'Vessel'),
            vessel_method=config_defaults.get('vessel_method', 'Teabag'),
            volume_mode=volume_mode or config_defaults.get('volume_mode', 'stoichiometry'),
            activator=config_defaults.get('activator', 'HBTU'),
            use_oxyma=config_defaults.get('use_oxyma', True),
            base=config_defaults.get('base', 'DIEA'),
            deprotection_reagent=config_defaults.get('deprotection_reagent', 'Piperidine 20%'),
            aa_equivalents=float(config_defaults.get('aa_equivalents', 3.0)),
            activator_equivalents=float(config_defaults.get('activator_equivalents', 3.0)),
            base_equivalents=float(config_defaults.get('base_equivalents', 6.0)),
            include_bb_test=config_defaults.get('include_bb_test', True),
            include_kaiser_test=config_defaults.get('include_kaiser_test', False),
            starting_vessel_number=starting_num,
            output_directory=output_dir or config_defaults.get('output_directory', 'spps_output'),
            resin_mass_strategy=config_defaults.get('resin_mass_strategy', 'fixed'),
            fixed_resin_mass_g=float(config_defaults.get('fixed_resin_mass_g', 0.1)),
            target_yield_mg=config_defaults.get('target_yield_mg'),
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
        for vessel in vessels:
            from spps_assistant.domain.yield_calc import back_calc_resin_mass as _bcr
            pep_mw = calc_peptide_mw(vessel.original_tokens, FREE_RESIDUE_MW, residue_info_map)
            try:
                vessel.resin_mass_g = _bcr(
                    config.target_yield_mg,
                    vessel.substitution_mmol_g,
                    vessel.length,
                    pep_mw,
                )
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Step j-k: Calculate yields and solubility                           #
    # ------------------------------------------------------------------ #
    from spps_assistant.domain.yield_calc import build_yield_formula
    from spps_assistant.domain.models import YieldResult
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
        sol = analyze_peptide(vessel.original_tokens, residue_info_map)
        solubility_results[vessel.number] = sol

    # ------------------------------------------------------------------ #
    # Step l: Run summary confirmation                                     #
    # ------------------------------------------------------------------ #
    if not non_interactive:
        if not display_run_summary(vessels, config, yield_results, solubility_results):
            console.print("[yellow]Aborted by user.[/yellow]")
            sys.exit(0)

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
