"""Shared application-layer helpers for sequence loading, vessel building, and materials loading.

These functions are used by CLI commands to avoid duplicating FASTA parsing,
vessel construction, and materials file loading logic.
"""

from pathlib import Path
from typing import Dict, List, Tuple

from spps_assistant.domain.models import ResidueInfo, Vessel


def parse_and_validate_sequences(fasta_path: Path) -> List[Tuple[str, str, List[str]]]:
    """Parse a FASTA file and validate all residue tokens.

    Args:
        fasta_path: Path to the FASTA (or plain-text) sequence file.

    Returns:
        List of ``(name, raw_seq, tokens)`` tuples for every valid sequence.

    Raises:
        ValueError: If the file cannot be parsed or any token is invalid.
    """
    from spps_assistant.infrastructure.fasta_parser import parse_fasta
    from spps_assistant.domain.sequence import tokenize, validate_tokens
    from spps_assistant.domain.constants import VALID_BASE_CODES

    try:
        sequences = parse_fasta(Path(fasta_path))
    except Exception as exc:
        raise ValueError(f"Could not parse FASTA file: {exc}") from exc

    all_errors: List[str] = []
    parsed: List[Tuple[str, str, List[str]]] = []

    for name, raw_seq in sequences:
        tokens = tokenize(raw_seq)
        errors = validate_tokens(tokens, VALID_BASE_CODES)
        if errors:
            all_errors.extend(
                f"Sequence '{name}': {err}" for err in errors
            )
        else:
            parsed.append((name, raw_seq, tokens))

    if all_errors:
        raise ValueError("Sequence validation errors:\n" + "\n".join(all_errors))

    return parsed


def build_vessels(
    parsed_sequences: List[Tuple[str, str, List[str]]],
    starting_num: int,
    resin_mass_g: float = 0.1,
    substitution_mmol_g: float = 0.3,
) -> List[Vessel]:
    """Build a list of :class:`~spps_assistant.domain.models.Vessel` objects.

    Args:
        parsed_sequences: Output of :func:`parse_and_validate_sequences`.
        starting_num: First vessel number; subsequent vessels are numbered
            ``starting_num + 1``, ``starting_num + 2``, etc.
        resin_mass_g: Resin mass in grams applied to every vessel.
        substitution_mmol_g: Resin substitution loading (mmol/g).

    Returns:
        List of :class:`~spps_assistant.domain.models.Vessel` objects in the
        same order as *parsed_sequences*.
    """
    vessels: List[Vessel] = []
    for i, (name, _raw_seq, tokens) in enumerate(parsed_sequences):
        reversed_tokens = list(reversed(tokens))
        vessels.append(Vessel(
            number=starting_num + i,
            name=name,
            original_tokens=tokens,
            reversed_tokens=reversed_tokens,
            resin_mass_g=resin_mass_g,
            substitution_mmol_g=substitution_mmol_g,
        ))
    return vessels


def load_materials_map(materials_path: Path) -> Dict[str, ResidueInfo]:
    """Load a materials CSV/XLSX file and return a token-keyed residue map.

    Args:
        materials_path: Path to a CSV or XLSX materials file.

    Returns:
        Dictionary mapping token strings (e.g. ``"A"`` or ``"C(Trt)"``) to
        :class:`~spps_assistant.domain.models.ResidueInfo` instances.

    Raises:
        ValueError: If the file cannot be loaded for any reason.
    """
    from spps_assistant.infrastructure.materials_parser import load_materials_file

    try:
        records = load_materials_file(Path(materials_path))
    except Exception as exc:
        raise ValueError(
            f"Could not load materials file '{materials_path}': {exc}"
        ) from exc

    residue_info_map: Dict[str, ResidueInfo] = {}
    for rec in records:
        token = rec["token"]
        residue_info_map[token] = ResidueInfo(
            token=token,
            base_code=rec["base_code"],
            protection=rec["protection"],
            fmoc_mw=rec["fmoc_mw"],
            free_mw=rec["free_mw"],
            stock_conc=rec.get("stock_conc", 0.5),
            density_g_ml=rec.get("density_g_ml"),
            equivalents_multiplier=rec.get("equivalents_multiplier", 1.0),
        )
    return residue_info_map
