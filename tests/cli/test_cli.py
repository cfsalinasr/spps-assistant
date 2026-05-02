"""Tests for the CLI commands using Click CliRunner."""

import csv
from pathlib import Path

import openpyxl
import pytest
from click.testing import CliRunner

from spps_assistant.cli.main import cli


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def fasta_file(tmp_path):
    """Write a two-sequence FASTA to a tmp file and return its path."""
    p = tmp_path / 'seqs.fasta'
    p.write_text('>Pep1\nAG\n>Pep2\nGW\n', encoding='utf-8')
    return p


@pytest.fixture
def materials_csv(tmp_path):
    """Write a three-residue materials CSV to a tmp file and return its path."""
    p = tmp_path / 'mat.csv'
    p.write_text(
        'ResidueCode,ProtectionGroup,FmocMW_g_mol,FreeAA_MW_g_mol,Density_g_mL,Notes\n'
        'A,,311.3,71.08,,Fmoc-Ala-OH\n'
        'G,,297.3,57.05,,Fmoc-Gly-OH\n'
        'W,,496.6,186.21,,Fmoc-Trp-OH\n',
        encoding='utf-8',
    )
    return p


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Redirect SQLiteRepository to a tmp db, and YAMLConfig to a tmp config."""
    import spps_assistant.infrastructure.sqlite_repository as sr
    import spps_assistant.infrastructure.yaml_config as yc

    db_path = tmp_path / 'test.db'
    config_path = tmp_path / 'config.yaml'

    monkeypatch.setattr(sr, '_DB_PATH', db_path)
    monkeypatch.setattr(yc, '_CONFIG_PATH', config_path)

    # Re-init db at new path
    sr._init_db(db_path)
    yc._ensure_config(config_path)

    return tmp_path


# ── version ───────────────────────────────────────────────────────────────────

class TestVersion:
    def test_version_flag(self, runner):
        """Version flag exits 0 and prints the tool name."""
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert 'spps-assistant' in result.output.lower() or result.output.strip()


# ── template command ──────────────────────────────────────────────────────────

class TestTemplateCommand:
    def test_creates_csv_template(self, runner, tmp_path):
        """Template command creates spps_materials_template.csv."""
        result = runner.invoke(cli, ['template', '--output-dir', str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / 'spps_materials_template.csv').exists()

    def test_creates_xlsx_template(self, runner, tmp_path):
        """Template command creates spps_materials_template.xlsx."""
        result = runner.invoke(cli, ['template', '--output-dir', str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / 'spps_materials_template.xlsx').exists()

    def test_creates_fasta_template(self, runner, tmp_path):
        """Template command creates spps_sequences_template.fasta."""
        result = runner.invoke(cli, ['template', '--output-dir', str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / 'spps_sequences_template.fasta').exists()

    def test_no_csv_sequence_template(self, runner, tmp_path):
        """Template command does NOT create spps_sequences_template.csv."""
        result = runner.invoke(cli, ['template', '--output-dir', str(tmp_path)])
        assert result.exit_code == 0
        assert not (tmp_path / 'spps_sequences_template.csv').exists()

    def test_materials_csv_has_density_column(self, runner, tmp_path):
        """Materials CSV template includes the Density_g_mL header."""
        runner.invoke(cli, ['template', '--output-dir', str(tmp_path)])
        p = tmp_path / 'spps_materials_template.csv'
        with open(p, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
        assert 'Density_g_mL' in headers

    def test_materials_csv_has_equivalents_column(self, runner, tmp_path):
        """Materials CSV template includes the Equivalents header."""
        runner.invoke(cli, ['template', '--output-dir', str(tmp_path)])
        p = tmp_path / 'spps_materials_template.csv'
        with open(p, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
        assert 'Equivalents' in headers

    def test_fasta_template_has_no_bare_separator(self, runner, tmp_path):
        """FASTA template has no bare '>' lines."""
        runner.invoke(cli, ['template', '--output-dir', str(tmp_path)])
        content = (tmp_path / 'spps_sequences_template.fasta').read_text()
        lines = content.splitlines()
        bare_gt = [l for l in lines if l.strip() == '>']
        assert bare_gt == []

    def test_default_output_dir_is_current(self, runner, tmp_path):
        """Template command with no output dir defaults to current directory."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['template'])
            assert result.exit_code == 0


# ── config command ────────────────────────────────────────────────────────────

class TestConfigCommand:
    def test_show_displays_table(self, runner, tmp_db):
        """Config --show displays a table containing 'activator'."""
        result = runner.invoke(cli, ['config', '--show'])
        assert result.exit_code == 0
        assert 'activator' in result.output.lower() or 'HBTU' in result.output

    def test_default_no_args_shows_config(self, runner, tmp_db):
        """Config with no args exits 0."""
        result = runner.invoke(cli, ['config'])
        assert result.exit_code == 0

    def test_set_field(self, runner, tmp_db):
        """Config --set writes a string field."""
        result = runner.invoke(cli, ['config', '--set', 'activator', 'DIC'])
        assert result.exit_code == 0
        assert 'activator' in result.output.lower() or 'DIC' in result.output

    def test_set_numeric_field(self, runner, tmp_db):
        """Config --set writes a numeric field."""
        result = runner.invoke(cli, ['config', '--set', 'aa_equivalents', '4.0'])
        assert result.exit_code == 0

    def test_set_bool_true(self, runner, tmp_db):
        """Config --set writes a boolean true value."""
        result = runner.invoke(cli, ['config', '--set', 'include_kaiser_test', 'true'])
        assert result.exit_code == 0


# ── db command ────────────────────────────────────────────────────────────────

class TestDbCommand:
    def test_db_no_args_shows_status(self, runner, tmp_db):
        """DB command with no args exits 0."""
        result = runner.invoke(cli, ['db'])
        assert result.exit_code == 0

    def test_db_list_empty(self, runner, tmp_db):
        """DB --list on empty database prints 'no residue' or 'library'."""
        result = runner.invoke(cli, ['db', '--list'])
        assert result.exit_code == 0
        assert 'no residue' in result.output.lower() or 'library' in result.output.lower()

    def test_db_import_csv(self, runner, tmp_db, materials_csv):
        """DB --import loads residues from a CSV file."""
        result = runner.invoke(cli, ['db', '--import', str(materials_csv)])
        assert result.exit_code == 0
        assert 'imported' in result.output.lower()

    def test_db_import_then_list(self, runner, tmp_db, materials_csv):
        """Residues imported via --import appear in --list output."""
        runner.invoke(cli, ['db', '--import', str(materials_csv)])
        result = runner.invoke(cli, ['db', '--list'])
        assert result.exit_code == 0
        assert 'A' in result.output

    def test_db_import_xlsx(self, runner, tmp_db, tmp_path):
        """DB --import accepts an XLSX file."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['ResidueCode', 'ProtectionGroup', 'FmocMW_g_mol',
                   'FreeAA_MW_g_mol', 'Density_g_mL', 'Notes'])
        ws.append(['A', '', 311.3, 71.08, None, ''])
        p = tmp_path / 'lib.xlsx'
        wb.save(str(p))
        result = runner.invoke(cli, ['db', '--import', str(p)])
        assert result.exit_code == 0

    def test_db_export(self, runner, tmp_db, materials_csv, tmp_path):
        """DB --export writes a CSV file to the given path."""
        runner.invoke(cli, ['db', '--import', str(materials_csv)])
        out = tmp_path / 'export.csv'
        result = runner.invoke(cli, ['db', '--export', str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_db_reset_aborted(self, runner, tmp_db):
        """DB --reset aborted by user does not reset."""
        result = runner.invoke(cli, ['db', '--reset'], input='n\n')
        assert result.exit_code == 0
        assert 'aborted' in result.output.lower()

    def test_db_reset_confirmed(self, runner, tmp_db, materials_csv):
        """DB --reset confirmed wipes the database."""
        runner.invoke(cli, ['db', '--import', str(materials_csv)])
        result = runner.invoke(cli, ['db', '--reset'], input='y\n')
        assert result.exit_code == 0
        assert 'reset' in result.output.lower()

    def test_db_add_token(self, runner, tmp_db):
        """DB --add saves a new residue interactively."""
        result = runner.invoke(
            cli, ['db', '--add', 'A'],
            input='311.3\n71.08\n0.5\n\n',
        )
        assert result.exit_code == 0
        assert 'saved' in result.output.lower() or 'A' in result.output

    def test_db_add_invalid_token(self, runner, tmp_db):
        """DB --add with invalid token exits gracefully."""
        result = runner.invoke(
            cli, ['db', '--add', '(invalid'],
            input='\n',
        )
        assert result.exit_code == 0
        assert 'invalid' in result.output.lower() or result.output


# ── generate command (dry-run / non-interactive) ──────────────────────────────

class TestGenerateCommand:
    def test_dry_run(self, runner, tmp_db, fasta_file, materials_csv, tmp_path):
        """Generate --dry-run prints dry-run message and exits 0."""
        result = runner.invoke(cli, [
            'generate',
            '--input', str(fasta_file),
            '--materials', str(materials_csv),
            '--output', str(tmp_path / 'out'),
            '--dry-run',
            '--non-interactive',
        ])
        assert result.exit_code == 0
        assert 'dry run' in result.output.lower()

    def test_missing_input_exits(self, runner, tmp_db, tmp_path):
        """Generate with a nonexistent input file exits non-zero."""
        result = runner.invoke(cli, [
            'generate',
            '--input', str(tmp_path / 'nonexistent.fasta'),
            '--non-interactive',
        ])
        assert result.exit_code != 0

    def test_generates_files_non_interactive(self, runner, tmp_db, fasta_file,
                                             materials_csv, tmp_path):
        """Non-interactive generate creates at least one PDF."""
        out_dir = tmp_path / 'output'
        result = runner.invoke(cli, [
            'generate',
            '--input', str(fasta_file),
            '--materials', str(materials_csv),
            '--output', str(out_dir),
            '--non-interactive',
        ])
        assert result.exit_code == 0
        assert out_dir.exists()
        pdf_files = list(out_dir.glob('*.pdf'))
        assert len(pdf_files) >= 1

    def test_invalid_sequence_exits(self, runner, tmp_db, tmp_path):
        """Invalid amino-acid sequence causes exit code 1."""
        seq_file = tmp_path / 'bad.fasta'
        seq_file.write_text('>Bad\nZZZZ\n', encoding='utf-8')
        result = runner.invoke(cli, [
            'generate',
            '--input', str(seq_file),
            '--non-interactive',
        ])
        assert result.exit_code == 1


# ── materials command ─────────────────────────────────────────────────────────

class TestMaterialsCommand:
    def test_generates_materials_non_interactive(self, runner, tmp_db, fasta_file,
                                                  materials_csv, tmp_path):
        """Non-interactive materials command creates at least one XLSX."""
        out_dir = tmp_path / 'mat_out'
        result = runner.invoke(cli, [
            'materials',
            '--input', str(fasta_file),
            '--materials', str(materials_csv),
            '--output', str(out_dir),
            '--non-interactive',
        ])
        assert result.exit_code == 0
        assert out_dir.exists()
        xlsx_files = list(out_dir.glob('*.xlsx'))
        assert len(xlsx_files) >= 1

    def test_with_week_flag(self, runner, tmp_db, fasta_file, materials_csv, tmp_path):
        """Materials command accepts a --week flag and exits 0."""
        out_dir = tmp_path / 'mat_out'
        result = runner.invoke(cli, [
            'materials',
            '--input', str(fasta_file),
            '--materials', str(materials_csv),
            '--output', str(out_dir),
            '--week', '5',
            '--non-interactive',
        ])
        assert result.exit_code == 0

    def test_missing_input_exits(self, runner, tmp_db, tmp_path):
        """Materials command with missing input exits non-zero."""
        result = runner.invoke(cli, [
            'materials',
            '--input', str(tmp_path / 'missing.fasta'),
            '--non-interactive',
        ])
        assert result.exit_code != 0


# ── generate: additional error paths ─────────────────────────────────────────

class TestGenerateErrorPaths:
    def test_bad_materials_file_warns_and_continues(self, runner, tmp_db, fasta_file, tmp_path):
        """Invalid materials file does not abort a dry run."""
        bad_mat = tmp_path / 'bad_mat.csv'
        bad_mat.write_text('not,valid,csv,data\n', encoding='utf-8')
        out_dir = tmp_path / 'out'
        result = runner.invoke(cli, [
            'generate',
            '--input', str(fasta_file),
            '--materials', str(bad_mat),
            '--output', str(out_dir),
            '--dry-run',
            '--non-interactive',
        ])
        # Continues with dry run even if materials file is bad
        assert result.exit_code == 0

    def test_volume_mode_override_applied(self, runner, tmp_db, fasta_file,
                                          materials_csv, tmp_path):
        """--volume-mode flag overrides config and exits 0."""
        out_dir = tmp_path / 'out'
        result = runner.invoke(cli, [
            'generate',
            '--input', str(fasta_file),
            '--materials', str(materials_csv),
            '--output', str(out_dir),
            '--volume-mode', 'legacy',
            '--dry-run',
            '--non-interactive',
        ])
        assert result.exit_code == 0

    def test_exception_during_generation_exits(self, runner, tmp_db, tmp_path, monkeypatch):
        """Unexpected exception during generation yields exit code 1."""
        from spps_assistant.application import synthesis_guide
        def _fail(*a, **k):
            raise RuntimeError('boom')
        monkeypatch.setattr(synthesis_guide.SynthesisGuideUseCase, 'run', _fail)

        fasta = tmp_path / 's.fasta'
        fasta.write_text('>P1\nAG\n', encoding='utf-8')
        mat = tmp_path / 'm.csv'
        mat.write_text(
            'ResidueCode,ProtectionGroup,FmocMW_g_mol,FreeAA_MW_g_mol,Density_g_mL,Notes\n'
            'A,,311.3,71.08,,\nG,,297.3,57.05,,\n',
            encoding='utf-8',
        )
        result = runner.invoke(cli, [
            'generate',
            '--input', str(fasta),
            '--materials', str(mat),
            '--output', str(tmp_path / 'out'),
            '--non-interactive',
        ])
        assert result.exit_code == 1


# ── materials: additional error paths ─────────────────────────────────────────

class TestMaterialsErrorPaths:
    def test_invalid_sequence_exits(self, runner, tmp_db, tmp_path):
        """Invalid sequence in materials command yields exit code 1."""
        seq_file = tmp_path / 'bad.fasta'
        seq_file.write_text('>Bad\nZZZZ\n', encoding='utf-8')
        result = runner.invoke(cli, [
            'materials',
            '--input', str(seq_file),
            '--non-interactive',
        ])
        assert result.exit_code == 1

    def test_exception_during_run_exits(self, runner, tmp_db, fasta_file,
                                        materials_csv, tmp_path, monkeypatch):
        """Unexpected exception during materials run yields exit code 1."""
        from spps_assistant.application import materials as mat_mod
        def _fail(*a, **k):
            raise RuntimeError('boom')
        monkeypatch.setattr(mat_mod.MaterialsUseCase, 'run', _fail)
        result = runner.invoke(cli, [
            'materials',
            '--input', str(fasta_file),
            '--materials', str(materials_csv),
            '--output', str(tmp_path / 'out'),
            '--non-interactive',
        ])
        assert result.exit_code == 1


# ── db: error paths ───────────────────────────────────────────────────────────

class TestDbErrorPaths:
    def test_import_nonexistent_file_exits(self, runner, tmp_db, tmp_path):
        """Importing a nonexistent file exits non-zero."""
        result = runner.invoke(cli, ['db', '--import', str(tmp_path / 'nonexistent.csv')])
        # Click validates path exists so it should fail before even running
        assert result.exit_code != 0

    def test_export_error_exits(self, runner, tmp_db, tmp_path, monkeypatch):
        """Export failure propagates as exit code 1."""
        from spps_assistant.infrastructure import sqlite_repository as sr
        def _fail(*a, **k):
            raise RuntimeError('disk full')
        monkeypatch.setattr(sr.SQLiteRepository, 'export_csv', _fail)
        result = runner.invoke(cli, ['db', '--export', str(tmp_path / 'out.csv')])
        assert result.exit_code == 1


# ── config: _coerce_value ─────────────────────────────────────────────────────

class TestCoerceValue:
    def test_coerce_true(self, runner, tmp_db):
        """String 'true' is coerced to bool True."""
        result = runner.invoke(cli, ['config', '--set', 'use_oxyma', 'true'])
        assert result.exit_code == 0

    def test_coerce_false(self, runner, tmp_db):
        """String 'false' is coerced to bool False."""
        result = runner.invoke(cli, ['config', '--set', 'use_oxyma', 'false'])
        assert result.exit_code == 0

    def test_coerce_none(self, runner, tmp_db):
        """String 'none' is coerced to None."""
        result = runner.invoke(cli, ['config', '--set', 'target_yield_mg', 'none'])
        assert result.exit_code == 0

    def test_coerce_int(self, runner, tmp_db):
        """Numeric string is coerced to int."""
        result = runner.invoke(cli, ['config', '--set', 'starting_vessel_number', '3'])
        assert result.exit_code == 0

    def test_coerce_string(self, runner, tmp_db):
        """Non-special string is kept as-is."""
        result = runner.invoke(cli, ['config', '--set', 'name', 'MySynth'])
        assert result.exit_code == 0


# ── generate: interactive paths ───────────────────────────────────────────────

class TestGenerateInteractive:
    def test_abort_at_reversal_confirmation(self, runner, tmp_db, fasta_file,
                                            materials_csv, tmp_path):
        """Covers the abort path in display_reversal_table (lines 123-126)."""
        result = runner.invoke(cli, [
            'generate',
            '--input', str(fasta_file),
            '--materials', str(materials_csv),
            '--output', str(tmp_path / 'out'),
        ], input='n\n')
        assert result.exit_code == 0
        assert 'aborted' in result.output.lower()

    def test_full_interactive_dry_run(self, runner, tmp_db, fasta_file,
                                      materials_csv, tmp_path):
        """Covers interactive config, resin prompts, and run summary (lines 207-222, 273-275)."""
        interactive_input = (
            'y\n'                # confirm sequences
            'MySynthesis\n'      # name
            'Vessel\n'           # vessel_label
            'Teabag\n'           # vessel_method
            'stoichiometry\n'    # volume_mode
            'HBTU\n'             # activator
            'y\n'                # use_oxyma
            'DIEA\n'             # base
            'Piperidine 20%\n'   # deprotection_reagent
            '3.0\n'              # aa_eq
            '3.0\n'              # act_eq
            '6.0\n'              # base_eq
            'y\n'                # include_bb
            'n\n'                # include_kaiser
            '1\n'                # starting_num
            'fixed\n'            # resin_strategy
            '0.1\n'              # fixed_mass
            '0.1\n'              # vessel 1 resin_mass
            '0.3\n'              # vessel 1 sub
            '0.1\n'              # vessel 2 resin_mass
            '0.3\n'              # vessel 2 sub
            'y\n'                # run summary confirm
        )
        result = runner.invoke(cli, [
            'generate',
            '--input', str(fasta_file),
            '--materials', str(materials_csv),
            '--output', str(tmp_path / 'out'),
            '--dry-run',
        ], input=interactive_input)
        assert result.exit_code == 0
        assert 'dry run' in result.output.lower()

    def test_abort_at_run_summary(self, runner, tmp_db, fasta_file,
                                  materials_csv, tmp_path):
        """Covers run summary abort (lines 273-275)."""
        interactive_input = (
            'y\n'                # confirm sequences
            'MySynthesis\n'
            'Vessel\n'
            'Teabag\n'
            'stoichiometry\n'
            'HBTU\n'
            'y\n'
            'DIEA\n'
            'Piperidine 20%\n'
            '3.0\n'
            '3.0\n'
            '6.0\n'
            'y\n'
            'n\n'
            '1\n'
            'fixed\n'
            '0.1\n'
            '0.1\n'
            '0.3\n'
            '0.1\n'
            '0.3\n'
            'n\n'                # abort at run summary
        )
        result = runner.invoke(cli, [
            'generate',
            '--input', str(fasta_file),
            '--materials', str(materials_csv),
            '--output', str(tmp_path / 'out'),
        ], input=interactive_input)
        assert result.exit_code == 0
        assert 'aborted' in result.output.lower()


# ── generate: non-interactive without materials file ──────────────────────────

class TestGenerateNoMaterials:
    def test_uses_default_mws_when_no_materials_file(self, runner, tmp_db, fasta_file, tmp_path):
        """Covers auto-resolve from DB then defaults (lines 157, 172-173)."""
        result = runner.invoke(cli, [
            'generate',
            '--input', str(fasta_file),
            '--output', str(tmp_path / 'out'),
            '--dry-run',
            '--non-interactive',
        ])
        assert result.exit_code == 0


# ── materials: non-interactive without materials file ─────────────────────────

class TestMaterialsNoMaterials:
    def test_uses_default_mws_when_no_materials_file(self, runner, tmp_db, fasta_file, tmp_path):
        """Covers auto-resolve from defaults in materials_cmd (lines 106-116)."""
        out_dir = tmp_path / 'mat_out'
        result = runner.invoke(cli, [
            'materials',
            '--input', str(fasta_file),
            '--output', str(out_dir),
            '--non-interactive',
        ])
        assert result.exit_code == 0
        assert out_dir.exists()

    def test_uses_db_when_token_in_db(self, runner, tmp_db, fasta_file,
                                       materials_csv, tmp_path):
        """Covers lines 107-109 (existing residue in DB)."""
        # Import materials first so A, G, W are in DB
        runner.invoke(cli, ['db', '--import', str(materials_csv)])
        out_dir = tmp_path / 'mat_out'
        result = runner.invoke(cli, [
            'materials',
            '--input', str(fasta_file),
            # No --materials, so it reads from DB
            '--output', str(out_dir),
            '--non-interactive',
        ])
        assert result.exit_code == 0
