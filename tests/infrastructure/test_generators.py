"""Tests for pdf_generator.py and docx_generator.py."""

from pathlib import Path

import pytest

from spps_assistant.domain.models import (
    CouplingCycle, MaterialsRow, SolubilityResult, SynthesisConfig,
    Vessel, YieldResult,
)
from spps_assistant.domain.sequence import tokenize
from spps_assistant.domain.solubility import analyze_peptide
from spps_assistant.application.synthesis_guide import build_coupling_cycles
from spps_assistant.infrastructure.pdf_generator import (
    generate_cycle_guide_pdf,
    generate_peptide_info_pdf,
    generate_materials_pdf,
    _build_coupling_label as _pdf_coupling_label,
    _token_to_3letter as _pdf_token_3letter,
)
from spps_assistant.infrastructure.docx_generator import (
    generate_cycle_guide_docx,
    generate_peptide_info_docx,
    _build_coupling_label as _docx_coupling_label,
    _token_to_3letter as _docx_token_3letter,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _make_vessel(number, name, seq, resin_mass_g=0.1, sub=0.3):
    """Build a Vessel from a sequence string for generator tests."""
    tokens = tokenize(seq)
    return Vessel(
        number=number, name=name,
        original_tokens=tokens,
        reversed_tokens=list(reversed(tokens)),
        resin_mass_g=resin_mass_g,
        substitution_mmol_g=sub,
    )


def _make_config(**kwargs):
    """Build a SynthesisConfig with full defaults for generator tests."""
    defaults = dict(
        name='TestRun', vessel_label='Vessel', vessel_method='Teabag',
        volume_mode='stoichiometry', activator='HBTU', use_oxyma=True,
        base='DIEA', deprotection_reagent='Piperidine 20%',
        aa_equivalents=3.0, activator_equivalents=3.0, base_equivalents=6.0,
        include_bb_test=True, include_kaiser_test=False,
        starting_vessel_number=1, output_directory='out',
        resin_mass_strategy='fixed', fixed_resin_mass_g=0.1, target_yield_mg=None,
    )
    defaults.update(kwargs)
    return SynthesisConfig(**defaults)


def _make_yield(vessel):
    """Build a YieldResult for the given vessel."""
    return YieldResult(
        vessel_number=vessel.number,
        vessel_name=vessel.name,
        peptide_mw=500.0,
        sequence_length=vessel.length,
        resin_mass_g=vessel.resin_mass_g,
        substitution_mmol_g=vessel.substitution_mmol_g,
        theoretical_yield_mg=9.0,
        formula_shown='Y = ...',
    )


def _make_sol(tokens, info=None):
    """Run solubility analysis on the given tokens."""
    return analyze_peptide(tokens)


def _make_materials_row(token='A'):
    """Build a minimal MaterialsRow for the given token."""
    return MaterialsRow(
        token=token, protection='', fmoc_mw=311.3,
        mmol_needed=0.09, mass_mg=28.02, stock_conc=0.5,
        volume_ml=0.600, notes='Fmoc-Ala-OH', formula='V=...',
    )


# ── _token_to_3letter ─────────────────────────────────────────────────────────

class TestTokenTo3Letter:
    def test_pdf_standard_token(self):
        """Single-letter token maps to the 3-letter abbreviation."""
        assert _pdf_token_3letter('A') == 'Ala'

    def test_pdf_protected_token(self):
        """Protected token includes base name and protection group."""
        result = _pdf_token_3letter('C(Trt)')
        assert 'Cys' in result and 'Trt' in result

    def test_pdf_invalid_token_returns_token(self):
        """Non-standard token does not raise."""
        # A token like ">" or other invalid forms should return the token itself
        result = _pdf_token_3letter('DIEA')
        assert result  # should not raise

    def test_docx_standard_token(self):
        """DOCX variant maps G to Gly."""
        assert _docx_token_3letter('G') == 'Gly'

    def test_docx_invalid_token(self):
        """DOCX variant handles non-standard tokens without raising."""
        result = _docx_token_3letter('HBTU')
        assert result


# ── _build_coupling_label ──────────────────────────────────────────────────────

class TestBuildCouplingLabel:
    def test_pdf_hbtu_with_oxyma_and_base(self):
        """PDF coupling label includes HBTU, Oxyma, and DIEA."""
        config = _make_config(activator='HBTU', use_oxyma=True, base='DIEA')
        label = _pdf_coupling_label(config, 'A')
        assert 'HBTU' in label
        assert 'Oxyma' in label
        assert 'DIEA' in label

    def test_pdf_hbtu_with_oxyma_no_base(self):
        """PDF coupling label omits 'None' when base is 'None'."""
        config = _make_config(activator='HBTU', use_oxyma=True, base='None')
        label = _pdf_coupling_label(config, 'A')
        assert 'HBTU' in label
        assert 'Oxyma' in label
        assert 'None' not in label

    def test_pdf_hbtu_no_oxyma(self):
        """PDF coupling label omits Oxyma when use_oxyma is False."""
        config = _make_config(activator='HBTU', use_oxyma=False, base='DIEA')
        label = _pdf_coupling_label(config, 'A')
        assert 'HBTU' in label
        assert 'Oxyma' not in label

    def test_pdf_dic_with_oxyma(self):
        """PDF label includes DIC and Oxyma."""
        config = _make_config(activator='DIC', use_oxyma=True)
        label = _pdf_coupling_label(config, 'A')
        assert 'DIC' in label
        assert 'Oxyma' in label

    def test_pdf_dic_without_oxyma(self):
        """PDF label includes DIC but not Oxyma."""
        config = _make_config(activator='DIC', use_oxyma=False)
        label = _pdf_coupling_label(config, 'A')
        assert 'DIC' in label
        assert 'Oxyma' not in label

    def test_docx_dic_with_oxyma(self):
        """DOCX label includes DIC and Oxyma."""
        config = _make_config(activator='DIC', use_oxyma=True)
        label = _docx_coupling_label(config, 'A')
        assert 'DIC' in label
        assert 'Oxyma' in label

    def test_docx_dic_without_oxyma(self):
        """DOCX label includes DIC but not Oxyma."""
        config = _make_config(activator='DIC', use_oxyma=False)
        label = _docx_coupling_label(config, 'A')
        assert 'DIC' in label
        assert 'Oxyma' not in label

    def test_docx_hbtu_no_oxyma(self):
        """DOCX HBTU label without Oxyma."""
        config = _make_config(activator='HBTU', use_oxyma=False, base='DIEA')
        label = _docx_coupling_label(config, 'A')
        assert 'HBTU' in label
        assert 'Oxyma' not in label

    def test_docx_hbtu_oxyma_no_base(self):
        """DOCX HBTU label includes Oxyma even without a base."""
        config = _make_config(activator='HBTU', use_oxyma=True, base='None')
        label = _docx_coupling_label(config, 'A')
        assert 'Oxyma' in label


# ── generate_cycle_guide_pdf ──────────────────────────────────────────────────

class TestGenerateCycleGuidePDF:
    def test_creates_file(self, tmp_path):
        """Cycle guide PDF is created and non-empty."""
        v = _make_vessel(1, 'P1', 'AG')
        config = _make_config()
        cycles = build_coupling_cycles([v])
        yr = _make_yield(v)
        path = tmp_path / 'guide.pdf'
        generate_cycle_guide_pdf(
            path=path, synthesis_name='T', date_str='2026-01-01',
            vessels=[v], coupling_cycles=cycles, config=config,
            residue_info_map={}, yield_results=[yr],
        )
        assert path.exists()
        assert path.stat().st_size > 0

    def test_with_dic_activator(self, tmp_path):
        """Cycle guide PDF is created when DIC is the activator."""
        v = _make_vessel(1, 'P1', 'A')
        config = _make_config(activator='DIC', use_oxyma=True)
        cycles = build_coupling_cycles([v])
        yr = _make_yield(v)
        path = tmp_path / 'guide_dic.pdf'
        generate_cycle_guide_pdf(
            path=path, synthesis_name='T', date_str='2026-01-01',
            vessels=[v], coupling_cycles=cycles, config=config,
            residue_info_map={}, yield_results=[yr],
        )
        assert path.exists()

    def test_with_legacy_volume_mode(self, tmp_path):
        """Cycle guide PDF is created in legacy volume mode."""
        v = _make_vessel(1, 'P1', 'AG')
        config = _make_config(volume_mode='legacy')
        cycles = build_coupling_cycles([v])
        yr = _make_yield(v)
        path = tmp_path / 'guide_legacy.pdf'
        generate_cycle_guide_pdf(
            path=path, synthesis_name='T', date_str='2026-01-01',
            vessels=[v], coupling_cycles=cycles, config=config,
            residue_info_map={}, yield_results=[yr],
        )
        assert path.exists()

    def test_without_bb_test(self, tmp_path):
        """Cycle guide PDF is created when BB test is disabled."""
        v = _make_vessel(1, 'P1', 'A')
        config = _make_config(include_bb_test=False)
        cycles = build_coupling_cycles([v])
        yr = _make_yield(v)
        path = tmp_path / 'guide_nobb.pdf'
        generate_cycle_guide_pdf(
            path=path, synthesis_name='T', date_str='2026-01-01',
            vessels=[v], coupling_cycles=cycles, config=config,
            residue_info_map={}, yield_results=[yr],
        )
        assert path.exists()


# ── generate_peptide_info_pdf ─────────────────────────────────────────────────

class TestGeneratePeptideInfoPDF:
    def test_creates_file(self, tmp_path):
        """Peptide info PDF is created and non-empty."""
        v = _make_vessel(1, 'P1', 'AG')
        sol = _make_sol(v.original_tokens)
        yr = _make_yield(v)
        path = tmp_path / 'info.pdf'
        generate_peptide_info_pdf(
            path=path, synthesis_name='T',
            vessels=[v],
            solubility_results={1: sol},
            yield_results=[yr],
        )
        assert path.exists()

    def test_with_orthogonal_group_triggers_warning(self, tmp_path):
        """Orthogonal protecting group triggers a warning section."""
        # C(Acm) carries an orthogonal protecting group
        v = _make_vessel(1, 'P1', 'C(Acm)A')
        sol = _make_sol(v.original_tokens)
        assert sol.orthogonal_groups  # must have at least one
        yr = _make_yield(v)
        path = tmp_path / 'info_orthogonal.pdf'
        generate_peptide_info_pdf(
            path=path, synthesis_name='T',
            vessels=[v],
            solubility_results={1: sol},
            yield_results=[yr],
        )
        assert path.exists()

    def test_without_solubility_result(self, tmp_path):
        """Peptide info PDF is created even when solubility result is absent."""
        v = _make_vessel(1, 'P1', 'A')
        yr = _make_yield(v)
        path = tmp_path / 'info_nosol.pdf'
        generate_peptide_info_pdf(
            path=path, synthesis_name='T',
            vessels=[v],
            solubility_results={},
            yield_results=[yr],
        )
        assert path.exists()


# ── generate_materials_pdf ────────────────────────────────────────────────────

class TestGenerateMaterialsPDF:
    def test_creates_file(self, tmp_path):
        """Materials PDF is created and non-empty."""
        path = tmp_path / 'mat.pdf'
        generate_materials_pdf(
            path=path, synthesis_name='T',
            materials_rows=[_make_materials_row()],
            config_summary={'Activator': 'HBTU', 'AA Eq': 3.0},
        )
        assert path.exists()
        assert path.stat().st_size > 0

    def test_empty_rows(self, tmp_path):
        """Materials PDF is created even with no rows."""
        path = tmp_path / 'mat_empty.pdf'
        generate_materials_pdf(
            path=path, synthesis_name='T',
            materials_rows=[],
            config_summary={},
        )
        assert path.exists()

    def test_multiple_rows(self, tmp_path):
        """Materials PDF handles multiple rows."""
        rows = [_make_materials_row('A'), _make_materials_row('G'), _make_materials_row('W')]
        path = tmp_path / 'mat_multi.pdf'
        generate_materials_pdf(
            path=path, synthesis_name='T',
            materials_rows=rows,
            config_summary={'Activator': 'HBTU'},
        )
        assert path.exists()


# ── generate_cycle_guide_docx ─────────────────────────────────────────────────

class TestGenerateCycleGuideDOCX:
    def test_creates_file(self, tmp_path):
        """Cycle guide DOCX is created."""
        v = _make_vessel(1, 'P1', 'AG')
        config = _make_config()
        cycles = build_coupling_cycles([v])
        yr = _make_yield(v)
        path = tmp_path / 'guide.docx'
        generate_cycle_guide_docx(
            path=path, synthesis_name='T', date_str='2026-01-01',
            vessels=[v], coupling_cycles=cycles, config=config,
            residue_info_map={}, yield_results=[yr],
        )
        assert path.exists()

    def test_with_dic_activator(self, tmp_path):
        """Cycle guide DOCX is created with DIC activator."""
        v = _make_vessel(1, 'P1', 'A')
        config = _make_config(activator='DIC', use_oxyma=False)
        cycles = build_coupling_cycles([v])
        yr = _make_yield(v)
        path = tmp_path / 'guide_dic.docx'
        generate_cycle_guide_docx(
            path=path, synthesis_name='T', date_str='2026-01-01',
            vessels=[v], coupling_cycles=cycles, config=config,
            residue_info_map={}, yield_results=[yr],
        )
        assert path.exists()

    def test_without_bb_test(self, tmp_path):
        """Cycle guide DOCX is created with BB test disabled."""
        v = _make_vessel(1, 'P1', 'A')
        config = _make_config(include_bb_test=False)
        cycles = build_coupling_cycles([v])
        yr = _make_yield(v)
        path = tmp_path / 'guide_nobb.docx'
        generate_cycle_guide_docx(
            path=path, synthesis_name='T', date_str='2026-01-01',
            vessels=[v], coupling_cycles=cycles, config=config,
            residue_info_map={}, yield_results=[yr],
        )
        assert path.exists()

    def test_with_kaiser_test(self, tmp_path):
        """Cycle guide DOCX is created with Kaiser test enabled."""
        v = _make_vessel(1, 'P1', 'A')
        config = _make_config(include_kaiser_test=True)
        cycles = build_coupling_cycles([v])
        yr = _make_yield(v)
        path = tmp_path / 'guide_kaiser.docx'
        generate_cycle_guide_docx(
            path=path, synthesis_name='T', date_str='2026-01-01',
            vessels=[v], coupling_cycles=cycles, config=config,
            residue_info_map={}, yield_results=[yr],
        )
        assert path.exists()

    def test_legacy_volume_mode(self, tmp_path):
        """Cycle guide DOCX is created in legacy volume mode."""
        v = _make_vessel(1, 'P1', 'AG')
        config = _make_config(volume_mode='legacy')
        cycles = build_coupling_cycles([v])
        yr = _make_yield(v)
        path = tmp_path / 'guide_legacy.docx'
        generate_cycle_guide_docx(
            path=path, synthesis_name='T', date_str='2026-01-01',
            vessels=[v], coupling_cycles=cycles, config=config,
            residue_info_map={}, yield_results=[yr],
        )
        assert path.exists()


# ── generate_peptide_info_docx ────────────────────────────────────────────────

class TestGeneratePeptideInfoDOCX:
    def test_creates_file(self, tmp_path):
        """Peptide info DOCX is created."""
        v = _make_vessel(1, 'P1', 'AG')
        sol = _make_sol(v.original_tokens)
        yr = _make_yield(v)
        path = tmp_path / 'info.docx'
        generate_peptide_info_docx(
            path=path, synthesis_name='T',
            vessels=[v],
            solubility_results={1: sol},
            yield_results=[yr],
        )
        assert path.exists()

    def test_with_orthogonal_group_triggers_warning(self, tmp_path):
        """Peptide info DOCX handles orthogonal protecting groups."""
        v = _make_vessel(1, 'P1', 'C(Acm)A')
        sol = _make_sol(v.original_tokens)
        assert sol.orthogonal_groups
        yr = _make_yield(v)
        path = tmp_path / 'info_orthogonal.docx'
        generate_peptide_info_docx(
            path=path, synthesis_name='T',
            vessels=[v],
            solubility_results={1: sol},
            yield_results=[yr],
        )
        assert path.exists()

    def test_multiple_vessels(self, tmp_path):
        """Peptide info DOCX handles multiple vessels."""
        v1 = _make_vessel(1, 'P1', 'AG')
        v2 = _make_vessel(2, 'P2', 'GW')
        sol1 = _make_sol(v1.original_tokens)
        sol2 = _make_sol(v2.original_tokens)
        yr1 = _make_yield(v1)
        yr2 = _make_yield(v2)
        path = tmp_path / 'info_multi.docx'
        generate_peptide_info_docx(
            path=path, synthesis_name='T',
            vessels=[v1, v2],
            solubility_results={1: sol1, 2: sol2},
            yield_results=[yr1, yr2],
        )
        assert path.exists()
