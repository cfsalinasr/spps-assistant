"""FASTA and plain-text sequence file parsers."""

from pathlib import Path
from typing import List, Optional, Tuple


def _read_lines(path: Path) -> List[str]:
    """Read a file and return its non-stripped lines."""
    text = path.read_text(encoding='utf-8')
    return text.splitlines()


def _save_fasta_entry(current_name: str, current_seq_parts: List[str],
                      results: List[Tuple[str, str]]) -> None:
    """Append a completed FASTA entry to results if non-empty."""
    if current_name:
        seq = ''.join(current_seq_parts)
        if seq:
            results.append((current_name, seq))


def _parse_fasta_header(line: str, n_previous: int) -> str:
    """Extract the sequence name from a FASTA header line."""
    header = line[1:].strip()
    parts = header.split(None, 1)
    return parts[0] if parts else f"Seq{n_previous + 1}"


def _parse_fasta_lines(lines: List[str]) -> List[Tuple[str, str]]:
    """Parse lines of a FASTA file into (name, sequence) tuples."""
    results: List[Tuple[str, str]] = []
    current_name: str = ''
    current_seq_parts: List[str] = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith(';'):
            continue
        if line.startswith('>'):
            _save_fasta_entry(current_name, current_seq_parts, results)
            current_name = _parse_fasta_header(line, len(results))
            current_seq_parts = []
        else:
            current_seq_parts.append(line)

    _save_fasta_entry(current_name, current_seq_parts, results)
    return results


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

    lines = _read_lines(path)

    has_header = any(line.startswith('>') for line in lines)
    if not has_header:
        return parse_plain_text(path)

    results = _parse_fasta_lines(lines)

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

    lines = _read_lines(path)

    results = []
    for line in lines:
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
