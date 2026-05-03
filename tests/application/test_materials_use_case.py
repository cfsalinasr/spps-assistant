"""Tests for application/materials.py."""

import pytest

from spps_assistant.domain.models import (
    MaterialsRow, ResidueInfo, SynthesisConfig, Vessel
)
from spps_assistant.domain.sequence import tokenize
from spps_assistant.application.materials import build_materials_rows


def _vessel(number, name, seq, resin_mass_g=0.1, sub=0.3):
    """Build a minimal Vessel from a single-letter sequence string."""
    tokens = tokenize(seq)
    return Vessel(
        number=number, name=name,
        original_tokens=tokens,
        reversed_tokens=list(reversed(tokens)),
        resin_mass_g=resin_mass_g,
        substitution_mmol_g=sub,
    )


def _info(token, base, prot='', fmoc_mw=311.3, free_mw=71.08, stock_conc=0.5):
    """Build a minimal ResidueInfo for testing."""
    return ResidueInfo(
        token=token, base_code=base, protection=prot,
        fmoc_mw=fmoc_mw, free_mw=free_mw, stock_conc=stock_conc,
    )


def _config(**kwargs):
    """Build a SynthesisConfig with sensible test defaults."""
    defaults = dict(
        name='Test', volume_mode='stoichiometry',
        activator='HBTU', base='DIEA',
        aa_equivalents=3.0, activator_equivalents=3.0, base_equivalents=6.0,
    )
    defaults.update(kwargs)
    return SynthesisConfig(**defaults)


# ── build_materials_rows ──────────────────────────────────────────────────────

class TestBuildMaterialsRows:
    def test_empty_vessels_returns_empty(self):
        """Empty vessel list yields no material rows."""
        rows = build_materials_rows([], {}, _config())
        assert rows == []

    def test_single_vessel_single_residue(self):
        """Single vessel with one residue yields one row."""
        v = _vessel(1, 'P1', 'A')
        info = {'A': _info('A', 'A', fmoc_mw=311.3)}
        config = _config(aa_equivalents=3.0)
        rows = build_materials_rows([v], info, config)
        assert len(rows) == 1
        assert rows[0].token == 'A'

    def test_mmol_calculation(self):
        """Verify mmol = eq * resin_mass * substitution."""
        # resin_mass=0.1g, sub=0.3mmol/g → resin_mmol=0.03
        # eq=3.0, single occurrence → total_mmol = 3.0 * 0.03 * 1 = 0.09
        v = _vessel(1, 'P1', 'A', resin_mass_g=0.1, sub=0.3)
        info = {'A': _info('A', 'A', fmoc_mw=311.3)}
        rows = build_materials_rows([v], info, _config(aa_equivalents=3.0))
        assert rows[0].mmol_needed == pytest.approx(0.09)

    def test_mass_mg_calculation(self):
        """Verify mass_mg = mmol * fmoc_mw."""
        v = _vessel(1, 'P1', 'A', resin_mass_g=0.1, sub=0.3)
        info = {'A': _info('A', 'A', fmoc_mw=311.3)}
        rows = build_materials_rows([v], info, _config(aa_equivalents=3.0))
        # mass = 0.09 mmol * 311.3 g/mol = 0.09 * 311.3 mg = 28.017 mg
        assert rows[0].mass_mg == pytest.approx(28.02, abs=0.01)

    def test_unknown_token_skipped(self):
        """Tokens absent from residue_info_map are silently skipped."""
        v = _vessel(1, 'P1', 'A')
        rows = build_materials_rows([v], {}, _config())
        assert rows == []

    def test_two_vessels_share_residue(self):
        """Two vessels sharing a residue produce one row with summed mmol."""
        v1 = _vessel(1, 'P1', 'A', resin_mass_g=0.1, sub=0.3)
        v2 = _vessel(2, 'P2', 'A', resin_mass_g=0.1, sub=0.3)
        info = {'A': _info('A', 'A', fmoc_mw=311.3)}
        rows = build_materials_rows([v1, v2], info, _config(aa_equivalents=3.0))
        assert len(rows) == 1
        # total_mmol = 2 * (3.0 * 0.03 * 1) = 0.18
        assert rows[0].mmol_needed == pytest.approx(0.18)

    def test_repeated_residue_in_sequence(self):
        """Each occurrence of a residue in a sequence is counted separately."""
        # AA has A twice — each occurrence should count
        v = _vessel(1, 'P1', 'AA', resin_mass_g=0.1, sub=0.3)
        info = {'A': _info('A', 'A', fmoc_mw=311.3)}
        rows = build_materials_rows([v], info, _config(aa_equivalents=3.0))
        # 2 occurrences: total_mmol = 3.0 * 0.03 * 2 = 0.18
        assert rows[0].mmol_needed == pytest.approx(0.18)

    def test_legacy_volume_mode(self):
        """Legacy volume mode still produces a positive volume."""
        v = _vessel(1, 'P1', 'A')
        info = {'A': _info('A', 'A')}
        rows = build_materials_rows([v], info, _config(volume_mode='legacy'))
        assert len(rows) == 1
        assert rows[0].volume_ml > 0

    def test_stoichiometry_volume_mode(self):
        """Stoichiometry volume mode produces a positive volume."""
        v = _vessel(1, 'P1', 'A', resin_mass_g=0.1, sub=0.3)
        info = {'A': _info('A', 'A', stock_conc=0.5)}
        rows = build_materials_rows([v], info, _config(
            volume_mode='stoichiometry', aa_equivalents=3.0
        ))
        assert rows[0].volume_ml > 0

    def test_unique_tokens_across_multiple_vessels(self):
        """Unique tokens from all vessels are each represented by exactly one row."""
        v1 = _vessel(1, 'P1', 'AG')
        v2 = _vessel(2, 'P2', 'GW')
        info = {
            'A': _info('A', 'A'), 'G': _info('G', 'G', fmoc_mw=297.3),
            'W': _info('W', 'W', fmoc_mw=496.6),
        }
        rows = build_materials_rows([v1, v2], info, _config())
        tokens = {r.token for r in rows}
        assert tokens == {'A', 'G', 'W'}

    def test_row_has_expected_fields(self):
        """Every MaterialsRow carries the mandatory fields."""
        v = _vessel(1, 'P1', 'A')
        info = {'A': _info('A', 'A')}
        rows = build_materials_rows([v], info, _config())
        row = rows[0]
        assert hasattr(row, 'token')
        assert hasattr(row, 'fmoc_mw')
        assert hasattr(row, 'mass_mg')
        assert hasattr(row, 'volume_ml')
        assert hasattr(row, 'formula')

    def test_protected_residue_in_row(self):
        """Protection group is preserved in the returned row."""
        v = _vessel(1, 'P1', 'C(Trt)')
        info = {'C(Trt)': _info('C(Trt)', 'C', prot='Trt', fmoc_mw=585.7)}
        rows = build_materials_rows([v], info, _config())
        assert rows[0].protection == 'Trt'

    def test_equivalents_multiplier_applied(self):
        """Per-reagent equivalents multiplier scales mmol correctly."""
        # DIEA has multiplier=2; excess=10 → effective eq = 20
        v = _vessel(1, 'P1', 'A', resin_mass_g=0.1, sub=0.3)
        info = {
            'A': ResidueInfo(
                token='A', base_code='A', protection='',
                fmoc_mw=311.3, free_mw=71.08, stock_conc=0.5,
                equivalents_multiplier=2.0,
            )
        }
        rows = build_materials_rows([v], info, _config(aa_equivalents=10.0))
        # eff_eq=20, resin_mmol=0.03 → mmol = 20 * 0.03 = 0.60
        assert rows[0].mmol_needed == pytest.approx(0.60, abs=1e-9)

    def test_liquid_reagent_sets_volume_ul(self):
        """Reagent with density produces a non-None volume_ul."""
        v = _vessel(1, 'P1', 'A', resin_mass_g=0.1, sub=0.3)
        info = {
            'A': ResidueInfo(
                token='A', base_code='A', protection='',
                fmoc_mw=129.24, free_mw=129.24, stock_conc=0.5,
                density_g_ml=0.742, equivalents_multiplier=1.0,
            )
        }
        rows = build_materials_rows([v], info, _config(aa_equivalents=3.0))
        # mass_mg = 0.09 * 129.24 = 11.6316; volume_ul = 11.6316 / 0.742 ≈ 15.7
        assert rows[0].volume_ul is not None
        assert rows[0].volume_ul == pytest.approx(15.7, abs=0.2)

    def test_solid_reagent_volume_ul_is_none(self):
        """Solid reagent (no density) leaves volume_ul as None."""
        v = _vessel(1, 'P1', 'A')
        info = {'A': _info('A', 'A')}  # no density → solid
        rows = build_materials_rows([v], info, _config())
        assert rows[0].volume_ul is None
