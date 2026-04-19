"""Tests for infrastructure.fasta_parser module."""

import pytest
from pathlib import Path

from spps_assistant.infrastructure.fasta_parser import parse_fasta, parse_plain_text


# ------------------------------------------------------------------ #
# parse_fasta tests                                                    #
# ------------------------------------------------------------------ #

def test_parse_simple_fasta(tmp_path):
    """Parse standard two-sequence FASTA."""
    fasta = tmp_path / 'test.fasta'
    fasta.write_text('>PvAMP66\nWKKIKKFF\n>p5_Mut1_W6A\nLVGGVAVIVPGLLK\n')
    result = parse_fasta(fasta)
    assert len(result) == 2
    assert result[0] == ('PvAMP66', 'WKKIKKFF')
    assert result[1] == ('p5_Mut1_W6A', 'LVGGVAVIVPGLLK')


def test_parse_fasta_with_bracket_notation(tmp_path):
    """Bracket notation in sequences is preserved as-is."""
    fasta = tmp_path / 'test.fasta'
    fasta.write_text('>Vessel1\nAC(Trt)GK(Boc)\n')
    result = parse_fasta(fasta)
    assert result[0] == ('Vessel1', 'AC(Trt)GK(Boc)')


def test_parse_fasta_multiline_sequence(tmp_path):
    """Multi-line sequences are concatenated."""
    fasta = tmp_path / 'test.fasta'
    fasta.write_text('>Peptide1\nACDE\nFGHI\n')
    result = parse_fasta(fasta)
    assert result[0][1] == 'ACDEFGHI'


def test_parse_fasta_single_sequence(tmp_path):
    """Single sequence with no trailing newline."""
    fasta = tmp_path / 'test.fasta'
    fasta.write_text('>Pep\nAGLKW')
    result = parse_fasta(fasta)
    assert len(result) == 1
    assert result[0] == ('Pep', 'AGLKW')


def test_parse_fasta_header_with_description(tmp_path):
    """FASTA header with description: only first word used as name."""
    fasta = tmp_path / 'test.fasta'
    fasta.write_text('>Peptide1 A great peptide from study X\nAGLKW\n')
    result = parse_fasta(fasta)
    # Name is first word only (standard FASTA behavior)
    assert result[0][0] == 'Peptide1'
    assert result[0][1] == 'AGLKW'


def test_parse_fasta_skips_blank_lines(tmp_path):
    """Blank lines between entries are ignored."""
    fasta = tmp_path / 'test.fasta'
    fasta.write_text('>Seq1\nAGL\n\n>Seq2\nKWF\n')
    result = parse_fasta(fasta)
    assert len(result) == 2
    assert result[0][1] == 'AGL'
    assert result[1][1] == 'KWF'


def test_parse_fasta_skips_comment_lines(tmp_path):
    """; comment lines are ignored."""
    fasta = tmp_path / 'test.fasta'
    fasta.write_text('; this is a comment\n>Seq1\nAGL\n')
    result = parse_fasta(fasta)
    assert len(result) == 1
    assert result[0][1] == 'AGL'


def test_parse_fasta_file_not_found():
    """Non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parse_fasta(Path('/does/not/exist.fasta'))


def test_parse_fasta_empty_file(tmp_path):
    """Completely empty file raises ValueError."""
    fasta = tmp_path / 'empty.fasta'
    fasta.write_text('')
    with pytest.raises(ValueError):
        parse_fasta(fasta)


def test_parse_fasta_fallback_to_plain_text(tmp_path):
    """File without '>' headers falls back to plain text parsing."""
    plain = tmp_path / 'seqs.txt'
    plain.write_text('AGLKW\nWKKIKK\n')
    result = parse_fasta(plain)
    assert len(result) == 2
    assert result[0][1] == 'AGLKW'
    assert result[1][1] == 'WKKIKK'


def test_parse_fasta_many_sequences(tmp_path):
    """Parse more than 2 sequences."""
    content = '\n'.join(f'>Peptide{i}\nAGL\n' for i in range(1, 11))
    fasta = tmp_path / 'multi.fasta'
    fasta.write_text(content)
    result = parse_fasta(fasta)
    assert len(result) == 10
    for i, (name, seq) in enumerate(result, start=1):
        assert name == f'Peptide{i}'
        assert seq == 'AGL'


# ------------------------------------------------------------------ #
# parse_plain_text tests                                               #
# ------------------------------------------------------------------ #

def test_parse_plain_text_simple(tmp_path):
    """One sequence per line, auto-named."""
    f = tmp_path / 'seqs.txt'
    f.write_text('AGLKW\nWKKIKK\n')
    result = parse_plain_text(f)
    assert len(result) == 2
    assert result[0] == ('Seq1', 'AGLKW')
    assert result[1] == ('Seq2', 'WKKIKK')


def test_parse_plain_text_csv_format(tmp_path):
    """Two-column CSV: name,sequence."""
    f = tmp_path / 'seqs.csv'
    f.write_text('PepA,AGLKW\nPepB,WKKIKK\n')
    result = parse_plain_text(f)
    assert result[0] == ('PepA', 'AGLKW')
    assert result[1] == ('PepB', 'WKKIKK')


def test_parse_plain_text_skips_blank_lines(tmp_path):
    """Blank lines are skipped."""
    f = tmp_path / 'seqs.txt'
    f.write_text('AGLKW\n\nWKKIKK\n')
    result = parse_plain_text(f)
    assert len(result) == 2


def test_parse_plain_text_skips_comments(tmp_path):
    """Lines starting with # are skipped."""
    f = tmp_path / 'seqs.txt'
    f.write_text('# comment\nAGLKW\n')
    result = parse_plain_text(f)
    assert len(result) == 1
    assert result[0][1] == 'AGLKW'


def test_parse_plain_text_file_not_found():
    """Non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parse_plain_text(Path('/does/not/exist.txt'))


def test_parse_plain_text_empty_raises(tmp_path):
    """Empty file raises ValueError."""
    f = tmp_path / 'empty.txt'
    f.write_text('')
    with pytest.raises(ValueError):
        parse_plain_text(f)
