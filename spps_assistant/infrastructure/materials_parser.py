"""CSV/XLSX materials file parser."""

import csv
from pathlib import Path
from typing import Dict, List, Optional


def _parse_float(val, default: float) -> float:
    """Parse float, accepting both '.' and ',' as decimal separator."""
    if val is None or str(val).strip() == '':
        return default
    try:
        return float(str(val).replace(',', '.'))
    except (ValueError, TypeError):
        return default


def parse_materials_csv(path: Path) -> List[Dict]:
    """Parse a materials CSV file into a list of dicts.

    Expected columns (case-insensitive, flexible order):
        ResidueCode, ProtectionGroup, FmocMW_g_mol, FreeAA_MW_g_mol,
        Density_g_mL, Notes
        (StockConc_M also accepted for backward compatibility)

    Args:
        path: Path to the CSV file

    Returns:
        List of dicts with normalized keys

    Raises:
        FileNotFoundError: if file does not exist
        ValueError: if required columns are missing
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Materials file not found: {path}")

    results = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Empty or invalid CSV: {path}")

        for row in reader:
            norm_row = {k.lower().strip(): v.strip() for k, v in row.items() if k}

            residue_code = (
                norm_row.get('residuecode') or
                norm_row.get('residue_code') or
                norm_row.get('code', '')
            ).strip().upper()

            if not residue_code:
                continue

            protection = (
                norm_row.get('protectiongroup') or
                norm_row.get('protection_group') or
                norm_row.get('protection', '')
            ).strip()

            fmoc_mw = _parse_float(
                norm_row.get('fmocmw_g_mol') or
                norm_row.get('fmoc_mw_g_mol') or
                norm_row.get('fmocmw') or
                norm_row.get('mw_g_mol') or '',
                0.0
            )

            free_mw = _parse_float(
                norm_row.get('freeaa_mw_g_mol') or
                norm_row.get('free_mw_g_mol') or
                norm_row.get('freemw') or '',
                0.0
            )

            stock_conc = _parse_float(
                norm_row.get('stockconc_m') or
                norm_row.get('stock_conc_m') or
                norm_row.get('stock_conc') or '',
                0.5
            )

            density_g_ml: Optional[float] = None
            raw_density = (
                norm_row.get('density_g_ml') or
                norm_row.get('density') or ''
            )
            if raw_density:
                density_g_ml = _parse_float(raw_density, None)

            notes = norm_row.get('notes', '')

            token = f"{residue_code}({protection})" if protection else residue_code

            results.append({
                'token': token,
                'base_code': residue_code,
                'protection': protection,
                'fmoc_mw': fmoc_mw,
                'free_mw': free_mw,
                'stock_conc': stock_conc,
                'density_g_ml': density_g_ml,
                'notes': notes,
            })

    return results


def parse_materials_xlsx(path: Path) -> List[Dict]:
    """Parse a materials XLSX file.

    Args:
        path: Path to the XLSX file

    Returns:
        List of dicts (same format as parse_materials_csv)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Materials file not found: {path}")

    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl is required to parse XLSX files: pip install openpyxl")

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if header_row is None:
        return []

    headers = [str(h).lower().strip() if h is not None else '' for h in header_row]

    results = []
    for row in rows_iter:
        row_dict = {
            headers[i]: (str(row[i]).strip() if row[i] is not None else '')
            for i in range(min(len(headers), len(row)))
        }

        residue_code = (
            row_dict.get('residuecode') or
            row_dict.get('residue_code') or
            row_dict.get('code', '')
        ).upper().strip()

        if not residue_code:
            continue

        protection = (
            row_dict.get('protectiongroup') or
            row_dict.get('protection_group') or
            row_dict.get('protection', '')
        ).strip()

        fmoc_mw = _parse_float(
            row_dict.get('fmocmw_g_mol') or
            row_dict.get('fmoc_mw_g_mol') or
            row_dict.get('mw_g_mol') or '',
            0.0
        )
        free_mw = _parse_float(
            row_dict.get('freeaa_mw_g_mol') or
            row_dict.get('free_mw_g_mol') or '',
            0.0
        )
        stock_conc = _parse_float(
            row_dict.get('stockconc_m') or
            row_dict.get('stock_conc_m') or '',
            0.5
        )

        density_g_ml: Optional[float] = None
        raw_density = row_dict.get('density_g_ml') or row_dict.get('density') or ''
        if raw_density:
            density_g_ml = _parse_float(raw_density, None)

        notes = row_dict.get('notes', '')

        token = f"{residue_code}({protection})" if protection else residue_code

        results.append({
            'token': token,
            'base_code': residue_code,
            'protection': protection,
            'fmoc_mw': fmoc_mw,
            'free_mw': free_mw,
            'stock_conc': stock_conc,
            'density_g_ml': density_g_ml,
            'notes': notes,
        })

    wb.close()
    return results


def load_materials_file(path: Path) -> List[Dict]:
    """Auto-detect and parse a materials file (CSV or XLSX).

    Args:
        path: Path to CSV or XLSX materials file

    Returns:
        List of residue dicts
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.xlsx':
        return parse_materials_xlsx(path)
    elif suffix in ('.csv', '.txt'):
        return parse_materials_csv(path)
    else:
        try:
            return parse_materials_csv(path)
        except Exception:
            return parse_materials_xlsx(path)
