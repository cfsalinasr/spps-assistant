"""Sequence tokenization, reversal, and validation for SPPS."""

import re
from typing import List, Tuple

from spps_assistant.domain.constants import THREE_LETTER_CODE

# Matches a single letter optionally followed by a parenthesized group, e.g. C(Trt)
TOKEN_RE = re.compile(r'[A-Za-z](?:\([^)]+\))?')


def tokenize(sequence: str) -> List[str]:
    """Parse sequence string into list of residue tokens.

    Bracket notation like C(Trt) is treated as a single atomic token.

    Args:
        sequence: Raw sequence string, e.g. "AC(Trt)GK(Boc)"

    Returns:
        List of token strings, e.g. ['A', 'C(Trt)', 'G', 'K(Boc)']
    """
    return TOKEN_RE.findall(sequence.strip())


def reverse_sequence(sequence: str) -> List[str]:
    """Reverse N->C sequence to C->N for SPPS.

    In SPPS, synthesis proceeds from C-terminus to N-terminus, so the
    input N->C sequence must be reversed. Bracket notation is treated as
    an atomic unit so 'C(Trt)' is never split.

    Args:
        sequence: Raw N->C sequence string

    Returns:
        List of tokens in C->N order (reversed)
    """
    return list(reversed(tokenize(sequence)))


def parse_token(token: str) -> Tuple[str, str]:
    """Return (base_code, protection_group) from a residue token.

    Args:
        token: Residue token, e.g. 'C(Trt)' or 'A'

    Returns:
        Tuple of (base_code_uppercase, protection_group_str)

    Raises:
        ValueError: if token format is invalid
    """
    m = re.match(r'^([A-Za-z])(?:\(([^)]+)\))?$', token)
    if not m:
        raise ValueError(f"Invalid token: {token!r}")
    return m.group(1).upper(), (m.group(2) or '')


def validate_tokens(tokens: List[str], valid_base_codes: set) -> List[str]:
    """Return list of error messages for invalid tokens.

    Args:
        tokens: List of residue tokens to validate
        valid_base_codes: Set of accepted single-letter codes

    Returns:
        List of error message strings (empty if all valid)
    """
    errors = []
    for tok in tokens:
        try:
            base, _ = parse_token(tok)
            if base not in valid_base_codes:
                errors.append(f"Unrecognized residue code '{base}' in token '{tok}'")
        except ValueError as e:
            errors.append(str(e))
    return errors


def token_to_3letter(token: str) -> str:
    """Convert a bracket-notation token (e.g. 'C(Trt)') to its 3-letter display form."""
    try:
        base, prot = parse_token(token)
    except ValueError:
        return token
    three = THREE_LETTER_CODE.get(base, base)
    return f"{three}({prot})" if prot else three


def get_unique_tokens(vessels) -> List[str]:
    """Get sorted unique residue tokens across all vessels (order-preserving).

    Args:
        vessels: Iterable of Vessel objects with .original_tokens attribute

    Returns:
        List of unique tokens preserving first-seen order
    """
    seen = set()
    result = []
    for v in vessels:
        for tok in v.original_tokens:
            if tok not in seen:
                seen.add(tok)
                result.append(tok)
    return result
