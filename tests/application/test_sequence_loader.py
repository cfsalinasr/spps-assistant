"""Tests for application/sequence_loader.py."""

import pytest
from pathlib import Path

from spps_assistant.application.sequence_loader import (
    parse_and_validate_sequences,
    build_vessels,
    load_materials_map,
)
from spps_assistant.domain.models import Vessel, ResidueInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_fasta(tmp_path: Path, content: str) -> Path:
    """Write a FASTA file and return its path."""
    p = tmp_path / "seqs.fasta"
    p.write_text(content, encoding="utf-8")
    return p


def _write_csv(tmp_path: Path, content: str, name: str = "mats.csv") -> Path:
    """Write a materials CSV file and return its path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


SIMPLE_FASTA = ">Peptide1\nAGLK\n>Peptide2\nFW\n"
SIMPLE_CSV = (
    "ResidueCode,ProtectionGroup,FmocMW_g_mol,FreeAA_MW_g_mol,Density_g_mL,Notes\n"
    "A,,311.3,71.08,,Fmoc-Ala-OH\n"
    "G,,297.3,57.05,,Fmoc-Gly-OH\n"
)


# ---------------------------------------------------------------------------
# TestParseAndValidateSequences
# ---------------------------------------------------------------------------

class TestParseAndValidateSequences:

    def test_valid_fasta_returns_parsed_list(self, tmp_path):
        """A well-formed FASTA file returns one entry per sequence."""
        fasta = _write_fasta(tmp_path, SIMPLE_FASTA)
        result = parse_and_validate_sequences(fasta)
        assert len(result) == 2

    def test_parsed_tuple_has_name_rawseq_tokens(self, tmp_path):
        """Each element is a (name, raw_seq, tokens) 3-tuple with correct types."""
        fasta = _write_fasta(tmp_path, ">P1\nAGL\n")
        result = parse_and_validate_sequences(fasta)
        assert len(result) == 1
        name, raw_seq, tokens = result[0]
        assert name == "P1"
        assert raw_seq == "AGL"
        assert tokens == ["A", "G", "L"]

    def test_invalid_token_raises_value_error(self, tmp_path):
        """A sequence with an unrecognised residue code raises ValueError."""
        fasta = _write_fasta(tmp_path, ">Bad\nAZG\n")
        with pytest.raises(ValueError, match="Sequence validation errors"):
            parse_and_validate_sequences(fasta)

    def test_missing_file_raises_value_error(self, tmp_path):
        """A non-existent file path raises ValueError."""
        missing = tmp_path / "nonexistent.fasta"
        with pytest.raises(ValueError, match="Could not parse FASTA file"):
            parse_and_validate_sequences(missing)


# ---------------------------------------------------------------------------
# TestBuildVessels
# ---------------------------------------------------------------------------

class TestBuildVessels:

    def _parsed(self):
        """Return a minimal parsed_sequences list for two peptides."""
        return [
            ("Pep1", "AGLK", ["A", "G", "L", "K"]),
            ("Pep2", "FW",   ["F", "W"]),
        ]

    def test_returns_vessel_objects(self):
        """build_vessels returns a list of Vessel instances."""
        vessels = build_vessels(self._parsed(), starting_num=1)
        assert all(isinstance(v, Vessel) for v in vessels)
        assert len(vessels) == 2

    def test_vessel_numbering_starts_at_starting_num(self):
        """Vessel numbers begin at starting_num and increment by 1."""
        vessels = build_vessels(self._parsed(), starting_num=5)
        assert vessels[0].number == 5
        assert vessels[1].number == 6

    def test_reversed_tokens_are_reverse_of_original(self):
        """Each vessel's reversed_tokens is the reverse of original_tokens."""
        vessels = build_vessels(self._parsed(), starting_num=1)
        for v in vessels:
            assert v.reversed_tokens == list(reversed(v.original_tokens))

    def test_default_resin_params_applied(self):
        """Default resin_mass_g=0.1 and substitution_mmol_g=0.3 are set."""
        vessels = build_vessels(self._parsed(), starting_num=1)
        for v in vessels:
            assert v.resin_mass_g == pytest.approx(0.1)
            assert v.substitution_mmol_g == pytest.approx(0.3)

    def test_custom_resin_params_applied(self):
        """Custom resin_mass_g and substitution_mmol_g are forwarded to vessels."""
        vessels = build_vessels(
            self._parsed(), starting_num=1,
            resin_mass_g=0.25, substitution_mmol_g=0.45,
        )
        for v in vessels:
            assert v.resin_mass_g == pytest.approx(0.25)
            assert v.substitution_mmol_g == pytest.approx(0.45)


# ---------------------------------------------------------------------------
# TestLoadMaterialsMap
# ---------------------------------------------------------------------------

class TestLoadMaterialsMap:

    def test_valid_csv_returns_residue_info_map(self, tmp_path):
        """A valid CSV returns a dict mapping token -> ResidueInfo."""
        csv_path = _write_csv(tmp_path, SIMPLE_CSV)
        result = load_materials_map(csv_path)
        assert isinstance(result, dict)
        assert "A" in result
        assert "G" in result
        assert isinstance(result["A"], ResidueInfo)

    def test_density_parsed_when_present(self, tmp_path):
        """A row with a density value results in a non-None density_g_ml field."""
        csv_content = (
            "ResidueCode,ProtectionGroup,FmocMW_g_mol,FreeAA_MW_g_mol,Density_g_mL,Notes\n"
            "A,,311.3,71.08,1.23,Fmoc-Ala-OH\n"
        )
        csv_path = _write_csv(tmp_path, csv_content)
        result = load_materials_map(csv_path)
        assert result["A"].density_g_ml == pytest.approx(1.23)

    def test_missing_file_raises_value_error(self, tmp_path):
        """A non-existent materials file raises ValueError."""
        missing = tmp_path / "no_such_file.csv"
        with pytest.raises(ValueError, match="Could not load materials file"):
            load_materials_map(missing)
