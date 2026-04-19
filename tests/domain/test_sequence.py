"""Tests for domain.sequence module."""

import pytest

from spps_assistant.domain.sequence import (
    tokenize, reverse_sequence, parse_token, validate_tokens, get_unique_tokens
)
from spps_assistant.domain.constants import VALID_BASE_CODES


def test_tokenize_simple():
    """Simple single-letter sequence tokenizes to individual letters."""
    # Using valid amino acid codes
    assert tokenize('ACGT') == ['A', 'C', 'G', 'T']


def test_tokenize_bracket_notation():
    """Bracket notation C(Trt) is treated as a single token."""
    assert tokenize('AC(Trt)GK') == ['A', 'C(Trt)', 'G', 'K']


def test_tokenize_multiple_brackets():
    """Multiple bracket groups are each a single token."""
    assert tokenize('C(Trt)AC(Acm)') == ['C(Trt)', 'A', 'C(Acm)']


def test_tokenize_empty():
    """Empty or whitespace-only sequence returns empty list."""
    assert tokenize('') == []
    assert tokenize('   ') == []


def test_tokenize_with_spaces():
    """Tokenizer ignores spaces between tokens."""
    result = tokenize('A G K')
    # Spaces are stripped by the regex — only letters/brackets are matched
    assert set(result) == {'A', 'G', 'K'}


def test_reverse_simple():
    """Simple sequence reversal."""
    assert reverse_sequence('ACGK') == ['K', 'G', 'C', 'A']


def test_reverse_bracket_preserves_token():
    """Bracket notation must be treated as atomic during reversal."""
    assert reverse_sequence('AC(Trt)G') == ['G', 'C(Trt)', 'A']
    # Must NOT be: ['G', 'A', 'C', ')', 't', 'r', 'T', '(']


def test_reverse_example_from_srs():
    """AC(Trt)G reversed is G C(Trt) A (C→N SPPS order)."""
    result = reverse_sequence('AC(Trt)G')
    assert result == ['G', 'C(Trt)', 'A']


def test_reverse_single_token():
    """Single-token sequence reversed is itself."""
    assert reverse_sequence('A') == ['A']


def test_reverse_two_tokens():
    """Two-token sequence."""
    assert reverse_sequence('AG') == ['G', 'A']


def test_parse_token_simple():
    """Single-letter token returns (base_code, '')."""
    assert parse_token('A') == ('A', '')


def test_parse_token_protected():
    """Protected token returns (base_code, protection_group)."""
    assert parse_token('C(Trt)') == ('C', 'Trt')


def test_parse_token_lowercase_base():
    """Lowercase base letter is uppercased."""
    assert parse_token('a') == ('A', '')


def test_parse_token_nested_protection():
    """Multi-character protection group is preserved."""
    assert parse_token('K(Boc)') == ('K', 'Boc')
    assert parse_token('R(Pbf)') == ('R', 'Pbf')
    assert parse_token('D(OtBu)') == ('D', 'OtBu')


def test_parse_token_invalid():
    """Invalid token raises ValueError."""
    with pytest.raises(ValueError):
        parse_token('123')
    with pytest.raises(ValueError):
        parse_token('')


def test_validate_tokens_valid():
    """All valid tokens produce no errors."""
    assert validate_tokens(['A', 'C(Trt)', 'G'], VALID_BASE_CODES) == []


def test_validate_tokens_invalid():
    """Invalid base code produces an error message containing the code."""
    errors = validate_tokens(['Z', 'A'], VALID_BASE_CODES)
    assert len(errors) == 1
    assert 'Z' in errors[0]


def test_validate_tokens_multiple_invalid():
    """Multiple invalid codes each produce one error."""
    errors = validate_tokens(['Z', 'J', 'A'], VALID_BASE_CODES)
    assert len(errors) == 2


def test_validate_tokens_all_standard():
    """All 20 standard amino acids pass validation."""
    standard = list('ACDEFGHIKLMNPQRSTVWY')
    errors = validate_tokens(standard, VALID_BASE_CODES)
    assert errors == []


def test_get_unique_tokens_order_preserved():
    """get_unique_tokens preserves first-seen order."""
    from spps_assistant.domain.models import Vessel
    vessels = [
        Vessel(1, 'A', ['A', 'G', 'K'], ['K', 'G', 'A']),
        Vessel(2, 'B', ['G', 'L', 'A'], ['A', 'L', 'G']),
    ]
    result = get_unique_tokens(vessels)
    # A seen first, then G, then K, then L
    assert result == ['A', 'G', 'K', 'L']


def test_get_unique_tokens_no_duplicates():
    """No duplicates in result."""
    from spps_assistant.domain.models import Vessel
    vessels = [
        Vessel(1, 'A', ['A', 'A', 'G'], ['G', 'A', 'A']),
    ]
    result = get_unique_tokens(vessels)
    assert result == ['A', 'G']
    assert len(result) == len(set(result))
