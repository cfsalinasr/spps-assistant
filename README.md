# SPPS Synthesis Assistant v1.0

A Python CLI tool for parallel Solid Phase Peptide Synthesis (SPPS) workflow management.
Replaces the legacy Perl-based Spys.exe with a modern, GMP-compliant, cross-platform CLI.

## Features

- **Parallel synthesis support** — manage any number of vessels (bags, syringes, columns) simultaneously
- **GMP-compliant cycle guides** — one-page-per-cycle PDF and DOCX with checkbox tables for deprotection and coupling
- **Stoichiometric or legacy volume modes** — matches original Spys.pl legacy calculations or uses modern mmol-based stoichiometry
- **Peptide physicochemical analysis** — GRAVY, pI, net charge, hydrophobicity (Kyte-Doolittle, Eisenberg, Black & Mould), solubilization recommendations
- **Theoretical yield calculation** — with 98% per-step coupling efficiency model and back-calculation from target yield
- **Materials explosion** — XLSX and PDF materials lists for weekly reagent planning
- **SQLite residue library** — persistent Fmoc-AA MW database with community-validated defaults
- **YAML configuration** — persistent synthesis defaults
- **FASTA input** — standard FASTA with bracket notation support (e.g. `C(Trt)`, `K(Boc)`)

## Installation

```bash
pip install -e ".[dev]"
```

**Requirements:** Python 3.11+, and the following packages are installed automatically:
`click`, `reportlab`, `python-docx`, `openpyxl`, `PyYAML`, `rich`

## Quick Start

### 1. First-time setup

```bash
spps-assistant setup
```

This wizard configures your defaults and imports the community Fmoc-AA MW library.

### 2. Generate a cycle guide

```bash
spps-assistant generate --input sequences.fasta
```

Example FASTA file:
```fasta
>PvAMP66
WKKIKKFF
>p5_Mut1
AC(Trt)GK(Boc)LV
```

The generate command will:
- Parse and validate sequences
- Show reversal preview (N→C becomes C→N for SPPS)
- Look up or prompt for Fmoc-MW values
- Prompt synthesis parameters
- Calculate theoretical yields and solubility properties
- Generate PDF + DOCX cycle guides and peptide info documents

### 3. Generate materials list

```bash
spps-assistant materials --input sequences.fasta --week 1
```

### 4. Generate blank materials template

```bash
spps-assistant template --output-dir .
```

### 5. Manage the residue library

```bash
spps-assistant db --list
spps-assistant db --import my_library.csv
spps-assistant db --export backup.csv
spps-assistant db --add "C(Trt)"
```

### 6. View or update configuration

```bash
spps-assistant config --show
spps-assistant config --set activator DIC
spps-assistant config --set aa_equivalents 4.0
spps-assistant config --set volume_mode legacy
```

## CLI Reference

### `spps-assistant generate`

```
spps-assistant generate [OPTIONS]

Options:
  -i, --input PATH          FASTA input file (required)
  -m, --materials PATH      Fmoc-MW library CSV/XLSX
  -o, --output PATH         Output directory (default: spps_output)
  --volume-mode [stoichiometry|legacy]
  --dry-run                 Validate without writing files
  --non-interactive         Use config defaults, skip prompts
  --help
```

### `spps-assistant materials`

```
spps-assistant materials [OPTIONS]

Options:
  -i, --input PATH          FASTA input file (required)
  -w, --week INTEGER        Week number for file labeling
  -o, --output PATH         Output directory
  -m, --materials PATH      Fmoc-MW library file
  --non-interactive
  --help
```

### `spps-assistant db`

```
spps-assistant db [OPTIONS]

Options:
  --list                    List all residue records
  --export PATH             Export to CSV
  --import PATH             Import from CSV
  --reset                   Drop and recreate database (destructive)
  --add TOKEN               Add single residue interactively
  --help
```

### `spps-assistant config`

```
spps-assistant config [OPTIONS]

Options:
  --show                    Display all configuration values
  --set FIELD VALUE         Set a single field
  --help
```

## Sequence Format

Sequences are read from FASTA files. Standard single-letter codes are supported,
as well as bracket notation for protection groups:

| Token      | Meaning                     |
|------------|-----------------------------|
| `A`        | Alanine (Fmoc-Ala-OH)       |
| `C(Trt)`   | Cys with Trt protection     |
| `K(Boc)`   | Lys with Boc protection     |
| `R(Pbf)`   | Arg with Pbf protection     |
| `H(Trt)`   | His with Trt protection     |
| `W(Boc)`   | Trp with Boc protection     |
| `D(OtBu)`  | Asp with OtBu protection    |
| `E(OtBu)`  | Glu with OtBu protection    |
| `N(Trt)`   | Asn with Trt protection     |
| `Q(Trt)`   | Gln with Trt protection     |
| `S(tBu)`   | Ser with tBu protection     |
| `T(tBu)`   | Thr with tBu protection     |
| `Y(tBu)`   | Tyr with tBu protection     |

All standard 20 amino acids plus Aib (`B`), Sec (`U`), Pyl (`O`), and unknown (`X`) are supported.

## Volume Calculation Modes

**Stoichiometry mode (default):**
```
V = (n_vessels × equivalents × resin_mmol) / stock_conc_M
```

**Legacy mode** (matches original Spys.pl):
```
V = n_vessels × 2 mL
```

## Output Files

For a synthesis named `MySynthesis`, the generate command produces:

| File | Description |
|------|-------------|
| `MySynthesis_cycle_guide.pdf` | GMP cycle guide, one page per coupling step |
| `MySynthesis_cycle_guide.docx` | Word version of the cycle guide |
| `MySynthesis_peptide_info.pdf` | Peptide physicochemical properties per vessel |
| `MySynthesis_peptide_info.docx` | Word version of peptide info |

Each cycle guide page contains:
- Header: synthesis name, date (blank for printing), operator (blank), cycle N of total
- AA Dispatch Table: residue, MW, mmol, volume, GMP formula, status checkbox, vessel numbers
- Deprotection Table: step-by-step with checkboxes (Bromophenol Blue test optional)
- Coupling Table: 1st–4th coupling steps with checkboxes
- Vessel Assignment: which residue goes in which vessel
- Secondary Coupling Verification Table (Teabag method)

## Configuration

Default configuration file: `~/.spps_assistant/spps_config.yaml`

| Field | Default | Description |
|-------|---------|-------------|
| `name` | `MySynthesis` | Synthesis run name |
| `vessel_label` | `Vessel` | Label for synthesis vessels |
| `vessel_method` | `Teabag` | Method: Teabag or Syringe/Reactor |
| `volume_mode` | `stoichiometry` | Volume calculation mode |
| `activator` | `HBTU` | Coupling activator |
| `use_oxyma` | `true` | Use Oxyma as additive |
| `base` | `DIEA` | Base for coupling |
| `deprotection_reagent` | `Piperidine 20%` | Fmoc deprotection reagent |
| `aa_equivalents` | `3.0` | AA molar equivalents |
| `activator_equivalents` | `3.0` | Activator equivalents |
| `base_equivalents` | `6.0` | Base equivalents |
| `include_bb_test` | `true` | Include Bromophenol Blue test |
| `include_kaiser_test` | `false` | Include Kaiser test |
| `starting_vessel_number` | `1` | Starting vessel number |
| `output_directory` | `spps_output` | Output file directory |
| `resin_mass_strategy` | `fixed` | fixed / target_highest / target_average |
| `fixed_resin_mass_g` | `0.1` | Resin mass per vessel (g) |
| `target_yield_mg` | `null` | Target yield for back-calculation (mg) |

## Database

Residue MW database: `~/.spps_assistant/spps_database.db` (SQLite)

Tables:
- `residue_mw` — Fmoc-AA molecular weights and stock concentrations
- `synthesis_defaults` — key-value synthesis defaults
- `synthesis_log` — history of synthesis runs

Import the community library (included with the package):
```bash
spps-assistant db --import community_mw_library.csv
```

## Running Tests

```bash
pytest
pytest --cov=spps_assistant --cov-report=term-missing
```

## Project Structure

```
spps-assistant/
├── pyproject.toml
├── LICENSE
├── CONTRIBUTING.md
├── CITATION.cff
├── community_mw_library.csv
├── spps_assistant/
│   ├── __init__.py             # version = "1.0.0"
│   ├── domain/                 # Pure business logic
│   │   ├── constants.py        # MW tables, hydrophobicity scales
│   │   ├── models.py           # Dataclasses
│   │   ├── sequence.py         # Tokenizer, reversal, validation
│   │   ├── stoichiometry.py    # Volume calculations
│   │   ├── solubility.py       # Hydrophobicity analysis
│   │   └── yield_calc.py       # Theoretical yield calculations
│   ├── application/            # Use cases and port interfaces
│   │   ├── ports.py            # ABCs for DB and Config
│   │   ├── synthesis_guide.py  # Generate workflow orchestration
│   │   └── materials.py        # Materials explosion use case
│   ├── infrastructure/         # I/O adapters
│   │   ├── fasta_parser.py
│   │   ├── materials_parser.py
│   │   ├── sqlite_repository.py
│   │   ├── yaml_config.py
│   │   ├── pdf_generator.py
│   │   ├── docx_generator.py
│   │   └── xlsx_generator.py
│   └── cli/                    # Click CLI
│       ├── main.py
│       ├── prompts.py
│       ├── setup_cmd.py
│       ├── generate_cmd.py
│       ├── materials_cmd.py
│       ├── template_cmd.py
│       ├── db_cmd.py
│       └── config_cmd.py
└── tests/
    ├── domain/
    │   ├── test_sequence.py
    │   ├── test_stoichiometry.py
    │   ├── test_solubility.py
    │   └── test_yield_calc.py
    └── infrastructure/
        └── test_fasta_parser.py
```

## License

MIT — see [LICENSE](LICENSE) for details.

## Citation

If you use SPPS Synthesis Assistant in your research, please cite it using the
information in [CITATION.cff](CITATION.cff).
