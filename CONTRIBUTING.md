# Contributing to SPPS Synthesis Assistant

Thank you for your interest in contributing! This document outlines the process for
contributing code, bug reports, and documentation improvements.

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/spps-assistant.git
   cd spps-assistant
   ```
3. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```
4. Run the test suite to verify your setup:
   ```bash
   pytest
   ```

## Development Workflow

- Create a feature branch from `main`: `git checkout -b feature/my-feature`
- Write tests for any new functionality (tests live in `tests/`)
- Ensure all tests pass: `pytest --cov=spps_assistant`
- Submit a pull request with a clear description of the change

## Architecture

The project follows clean architecture principles:

```
spps_assistant/
├── domain/        # Pure business logic — no I/O, no framework dependencies
├── application/   # Use cases and port interfaces (ABCs)
├── infrastructure/# I/O adapters: SQLite, YAML, PDF, DOCX, XLSX, FASTA parsers
└── cli/           # Click CLI commands and prompts
```

**Rules:**
- `domain/` must not import from `application/`, `infrastructure/`, or `cli/`
- `application/` may import from `domain/` only
- `infrastructure/` may import from `domain/` and `application/`
- `cli/` may import from all layers

## Adding a New Amino Acid

To add a new non-standard amino acid:
1. Add its single-letter code to `VALID_BASE_CODES` in `domain/constants.py`
2. Add `FREE_RESIDUE_MW` entry
3. Add `FMOC_MW_DEFAULTS` entry(s) for common protection groups
4. Add to `community_mw_library.csv`
5. Optionally add to `THREE_LETTER_CODE` map

## Code Style

- Python 3.11+
- Follow PEP 8
- Use type hints for all public functions
- Docstrings on all public functions and classes (Google style)

## Reporting Bugs

Open an issue on GitHub with:
- SPPS Assistant version (`spps-assistant --version`)
- Python version
- Operating system
- Minimal reproducible example (sequence, config, error message)

## Community MW Library

To propose additions to `community_mw_library.csv`, open a PR with:
- The CSV row(s) to add
- A reference to the supplier catalog or literature MW value
- Confirmation that the value has been experimentally validated
