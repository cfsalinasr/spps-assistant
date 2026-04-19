"""Shared test fixtures."""

import pytest


@pytest.fixture
def simple_vessels():
    """Return two simple Vessel objects for testing."""
    from spps_assistant.domain.models import Vessel
    from spps_assistant.domain.sequence import tokenize, reverse_sequence

    seq1 = 'ACGK'
    seq2 = 'WLFM'

    return [
        Vessel(
            number=1,
            name='PepA',
            original_tokens=tokenize(seq1),
            reversed_tokens=list(reversed(tokenize(seq1))),
            resin_mass_g=0.1,
            substitution_mmol_g=0.3,
        ),
        Vessel(
            number=2,
            name='PepB',
            original_tokens=tokenize(seq2),
            reversed_tokens=list(reversed(tokenize(seq2))),
            resin_mass_g=0.1,
            substitution_mmol_g=0.3,
        ),
    ]
