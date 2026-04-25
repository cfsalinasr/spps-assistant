"""Tests for infrastructure/sqlite_repository.py."""

import csv
from pathlib import Path

import openpyxl
import pytest

from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / 'test.db'
    r = SQLiteRepository(db_path=db_path)
    return r


# ── save_residue / get_residue ────────────────────────────────────────────────

class TestSaveAndGetResidue:
    def test_save_then_get(self, repo):
        repo.save_residue('A', 'A', '', 311.3, 71.08)
        result = repo.get_residue('A')
        assert result is not None
        assert result.token == 'A'
        assert result.fmoc_mw == pytest.approx(311.3)
        assert result.free_mw == pytest.approx(71.08)

    def test_get_missing_returns_none(self, repo):
        assert repo.get_residue('NOTEXIST') is None

    def test_upsert_updates_existing(self, repo):
        repo.save_residue('A', 'A', '', 311.3, 71.08)
        repo.save_residue('A', 'A', '', 999.9, 71.08)
        result = repo.get_residue('A')
        assert result.fmoc_mw == pytest.approx(999.9)

    def test_save_with_protection(self, repo):
        repo.save_residue('C(Trt)', 'C', 'Trt', 585.7, 103.14)
        result = repo.get_residue('C(Trt)')
        assert result.token == 'C(Trt)'
        assert result.base_code == 'C'
        assert result.protection == 'Trt'

    def test_save_with_density(self, repo):
        repo.save_residue('DIEA', 'DIEA', '', 129.24, 129.24,
                          stock_conc=0.5, notes='Base', density_g_ml=0.742)
        records = repo.list_residues()
        assert len(records) == 1
        assert records[0]['density_g_ml'] == pytest.approx(0.742)

    def test_save_density_none_for_solid(self, repo):
        repo.save_residue('HBTU', 'HBTU', '', 379.3, 379.3, density_g_ml=None)
        records = repo.list_residues()
        assert records[0]['density_g_ml'] is None

    def test_stock_conc_default(self, repo):
        repo.save_residue('G', 'G', '', 297.3, 57.05)
        result = repo.get_residue('G')
        assert result.stock_conc == pytest.approx(0.5)

    def test_multiple_residues(self, repo):
        repo.save_residue('A', 'A', '', 311.3, 71.08)
        repo.save_residue('G', 'G', '', 297.3, 57.05)
        repo.save_residue('C(Trt)', 'C', 'Trt', 585.7, 103.14)
        records = repo.list_residues()
        assert len(records) == 3


# ── list_residues ─────────────────────────────────────────────────────────────

class TestListResidues:
    def test_empty_returns_empty_list(self, repo):
        assert repo.list_residues() == []

    def test_returns_dicts(self, repo):
        repo.save_residue('A', 'A', '', 311.3, 71.08)
        records = repo.list_residues()
        assert isinstance(records[0], dict)
        assert 'token' in records[0]

    def test_ordered_by_token(self, repo):
        repo.save_residue('G', 'G', '', 297.3, 57.05)
        repo.save_residue('A', 'A', '', 311.3, 71.08)
        tokens = [r['token'] for r in repo.list_residues()]
        assert tokens == sorted(tokens)


# ── save_default / get_default ────────────────────────────────────────────────

class TestDefaults:
    def test_save_and_get(self, repo):
        repo.save_default('activator', 'HBTU')
        assert repo.get_default('activator') == 'HBTU'

    def test_missing_default_returns_none(self, repo):
        assert repo.get_default('nonexistent') is None

    def test_overwrite_default(self, repo):
        repo.save_default('activator', 'HBTU')
        repo.save_default('activator', 'DIC')
        assert repo.get_default('activator') == 'DIC'

    def test_multiple_defaults(self, repo):
        repo.save_default('activator', 'HBTU')
        repo.save_default('base', 'DIEA')
        assert repo.get_default('base') == 'DIEA'


# ── log_synthesis ─────────────────────────────────────────────────────────────

class TestLogSynthesis:
    def test_log_does_not_raise(self, repo):
        repo.log_synthesis('TestRun', {'n_vessels': 2})

    def test_multiple_logs_allowed(self, repo):
        repo.log_synthesis('Run1', {})
        repo.log_synthesis('Run1', {})  # same name is OK


# ── export_csv ────────────────────────────────────────────────────────────────

class TestExportCSV:
    def test_export_creates_file(self, repo, tmp_path):
        repo.save_residue('A', 'A', '', 311.3, 71.08)
        out = tmp_path / 'export.csv'
        repo.export_csv(out)
        assert out.exists()

    def test_export_has_header_and_row(self, repo, tmp_path):
        repo.save_residue('A', 'A', '', 311.3, 71.08, notes='test')
        out = tmp_path / 'export.csv'
        repo.export_csv(out)
        with open(out, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]['token'] == 'A'

    def test_export_empty_library(self, repo, tmp_path):
        out = tmp_path / 'empty.csv'
        repo.export_csv(out)
        assert out.exists()
        with open(out, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert rows == []

    def test_export_creates_parent_dirs(self, repo, tmp_path):
        out = tmp_path / 'subdir' / 'nested' / 'export.csv'
        repo.save_residue('G', 'G', '', 297.3, 57.05)
        repo.export_csv(out)
        assert out.exists()


# ── import_csv ────────────────────────────────────────────────────────────────

class TestImportCSV:
    def _write_csv(self, path, rows):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['ResidueCode', 'ProtectionGroup', 'FmocMW_g_mol',
                            'FreeAA_MW_g_mol', 'Density_g_mL', 'Notes'],
            )
            writer.writeheader()
            writer.writerows(rows)

    def test_import_csv_returns_count(self, repo, tmp_path):
        p = tmp_path / 'lib.csv'
        self._write_csv(p, [
            {'ResidueCode': 'A', 'ProtectionGroup': '', 'FmocMW_g_mol': '311.3',
             'FreeAA_MW_g_mol': '71.08', 'Density_g_mL': '', 'Notes': ''},
            {'ResidueCode': 'G', 'ProtectionGroup': '', 'FmocMW_g_mol': '297.3',
             'FreeAA_MW_g_mol': '57.05', 'Density_g_mL': '', 'Notes': ''},
        ])
        count = repo.import_csv(p)
        assert count == 2

    def test_import_csv_persists_records(self, repo, tmp_path):
        p = tmp_path / 'lib.csv'
        self._write_csv(p, [
            {'ResidueCode': 'A', 'ProtectionGroup': '', 'FmocMW_g_mol': '311.3',
             'FreeAA_MW_g_mol': '71.08', 'Density_g_mL': '', 'Notes': ''},
        ])
        repo.import_csv(p)
        assert repo.get_residue('A') is not None

    def test_import_xlsx(self, repo, tmp_path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['ResidueCode', 'ProtectionGroup', 'FmocMW_g_mol',
                   'FreeAA_MW_g_mol', 'Density_g_mL', 'Notes'])
        ws.append(['A', '', 311.3, 71.08, None, ''])
        p = tmp_path / 'lib.xlsx'
        wb.save(str(p))
        count = repo.import_csv(p)
        assert count == 1
        assert repo.get_residue('A') is not None

    def test_import_nonexistent_raises(self, repo):
        with pytest.raises((FileNotFoundError, Exception)):
            repo.import_csv(Path('/nonexistent/file.csv'))


# ── reset ─────────────────────────────────────────────────────────────────────

class TestReset:
    def test_reset_clears_residues(self, repo):
        repo.save_residue('A', 'A', '', 311.3, 71.08)
        repo.reset()
        assert repo.list_residues() == []

    def test_reset_clears_defaults(self, repo):
        repo.save_default('activator', 'HBTU')
        repo.reset()
        assert repo.get_default('activator') is None

    def test_reset_allows_reinsertion(self, repo):
        repo.save_residue('A', 'A', '', 311.3, 71.08)
        repo.reset()
        repo.save_residue('G', 'G', '', 297.3, 57.05)
        assert repo.get_residue('G') is not None
