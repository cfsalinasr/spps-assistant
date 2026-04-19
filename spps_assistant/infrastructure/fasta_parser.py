"""FASTA and plain-text sequence file parsers."""

from pathlib import Path
from typing import List, Tuple


def parse_fasta(path: Path) -> List[Tuple[str, str]]:
    """Parse a FASTA file into a list of (name, sequence) tuples.

    Supports:
    - Standard FASTA with '>' header lines (multi-line sequences concatenated)
    - Bracket notation in sequences (e.g. 'AC(Trt)GK(Boc)') is preserved as-is
    - Falls back to parse_plain_text if no '>' headers are found

    Args:
        path: Path to the FASTA file

    Returns:
        List of (name, raw_sequence_string) tuples

    Raises:
        FileNotFoundError: if path does not exist
        ValueError: if the file is empty or unparseable
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Sequence file not found: {path}")

    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()

    # Check if this looks like FASTA
    has_header = any(line.startswith('>') for line in lines)
    if not has_header:
        return parse_plain_text(path)

    results = []
    current_name: str = ''
    current_seq_parts: List[str] = []

    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line or line.startswith(';'):
            # Skip blank lines and FASTA comments
            continue
        if line.startswith('>'):
            # Save previous entry
            if current_name:
                seq = ''.join(current_seq_parts)
                if seq:
                    results.append((current_name, seq))
            # Parse header — take everything after '>' as the name, strip whitespace
            header = line[1:].strip()
            # Use only up to first whitespace as name (standard FASTA behavior)
            parts = header.split(None, 1)
            current_name = parts[0] if parts else f"Seq{len(results)+1}"
            current_seq_parts = []
        else:
            # Sequence line — accumulate (preserves bracket notation)
            current_seq_parts.append(line)

    # Save last entry
    if current_name:
        seq = ''.join(current_seq_parts)
        if seq:
            results.append((current_name, seq))

    if not results:
        raise ValueError(f"No valid sequences found in FASTA file: {path}")

    return results


def parse_plain_text(path: Path) -> List[Tuple[str, str]]:
    """Parse a plain-text or CSV file with one sequence per line.

    Each non-empty line is treated as a sequence. Two-column CSV
    (name,sequence) is supported. Names are auto-generated as Seq1, Seq2, ...
    when not provided.

    Args:
        path: Path to the plain-text or CSV file

    Returns:
        List of (name, raw_sequence_string) tuples

    Raises:
        FileNotFoundError: if path does not exist
        ValueError: if no valid sequences are found
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Sequence file not found: {path}")

    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()

    results = []
    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Try two-column CSV: name,sequence
        if ',' in line:
            parts = line.split(',', 1)
            name = parts[0].strip()
            seq = parts[1].strip()
            if name and seq:
                results.append((name, seq))
                continue

        # Plain sequence line
        seq = line
        name = f"Seq{len(results)+1}"
        results.append((name, seq))

    if not results:
        raise ValueError(f"No valid sequences found in file: {path}")

    return results
