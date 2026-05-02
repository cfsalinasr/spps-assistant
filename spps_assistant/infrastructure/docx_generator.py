"""python-docx DOCX generator for SPPS synthesis guides."""

from pathlib import Path
from typing import Dict, List, Optional

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from spps_assistant.domain.constants import THREE_LETTER_CODE
from spps_assistant.domain.models import (
    CouplingCycle, SynthesisConfig, Vessel, YieldResult, SolubilityResult
)
from spps_assistant.domain.stoichiometry import (
    calc_volume_stoichiometry, calc_volume_legacy, format_volume_formula
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _token_to_3letter(token: str) -> str:
    """Convert a bracket-notation token (e.g. 'C(Trt)') to its 3-letter display form."""
    from spps_assistant.domain.sequence import parse_token
    try:
        base, prot = parse_token(token)
    except ValueError:
        return token
    three = THREE_LETTER_CODE.get(base, base)
    return f"{three}({prot})" if prot else three


def _set_cell_bg(cell, hex_color: str) -> None:
    """Set a table cell background colour."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color.lstrip('#'))
    tcPr.append(shd)


def _set_cell_borders(table) -> None:
    """Add thin borders to all cells in a table."""
    for row in table.rows:
        for cell in row.cells:
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            tcBorders = OxmlElement('w:tcBorders')
            for border_name in ('top', 'left', 'bottom', 'right'):
                border = OxmlElement(f'w:{border_name}')
                border.set(qn('w:val'), 'single')
                border.set(qn('w:sz'), '4')
                border.set(qn('w:space'), '0')
                border.set(qn('w:color'), '888888')
                tcBorders.append(border)
            tcPr.append(tcBorders)


def _style_header_row(row, bg_hex: str = '2C3E50') -> None:
    """Style a table header row (dark background, white bold text)."""
    for cell in row.cells:
        _set_cell_bg(cell, bg_hex)
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                run.font.size = Pt(9)


def _add_table_with_header(doc: Document, data: List[List[str]],
                            col_widths: Optional[List[float]] = None,
                            header_bg: str = '2C3E50') -> None:
    """Add a table to document with styled header row.

    Args:
        doc: Word Document object
        data: 2D list of strings, first row is header
        col_widths: Optional list of column widths in cm
        header_bg: Header background hex color
    """
    if not data:
        return

    n_rows = len(data)
    n_cols = max(len(row) for row in data)

    table = doc.add_table(rows=n_rows, cols=n_cols)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    # Set column widths
    if col_widths:
        for i, width in enumerate(col_widths):
            if i < len(table.columns):
                for cell in table.columns[i].cells:
                    cell.width = Cm(width)

    for r_idx, row_data in enumerate(data):
        row = table.rows[r_idx]
        for c_idx, cell_text in enumerate(row_data):
            if c_idx < n_cols:
                cell = row.cells[c_idx]
                para = cell.paragraphs[0]
                run = para.add_run(str(cell_text))
                run.font.size = Pt(9)
                para.alignment = WD_ALIGN_PARAGRAPH.LEFT

        if r_idx == 0:
            _style_header_row(row, header_bg)
        elif r_idx % 2 == 0:
            for cell in row.cells:
                _set_cell_bg(cell, 'F8F9FA')

    _set_cell_borders(table)


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    """Add a bold heading paragraph to *doc* at the given heading level."""
    para = doc.add_paragraph(text)
    run = para.runs[0] if para.runs else para.add_run(text)
    run.bold = True
    run.font.size = Pt(14 - level * 2)


def _build_coupling_label(config: SynthesisConfig, token: str) -> str:
    """Build coupling label for DOCX table."""
    three = _token_to_3letter(token)
    act = config.activator
    base = config.base
    if act in ('DIC', 'DCC'):
        if config.use_oxyma:
            return f"{three} + {act} + Oxyma"
        return f"{three} + {act}"
    else:
        if config.use_oxyma and base not in ('None', 'none', ''):
            return f"{three} + {act} + Oxyma + {base}"
        elif config.use_oxyma:
            return f"{three} + {act} + Oxyma"
        return f"{three} + {act} + {base}"


# ---------------------------------------------------------------------------
# Cover page
# ---------------------------------------------------------------------------

def _build_cover(doc: Document, synthesis_name: str, vessels: List[Vessel],
                 yield_results: List[YieldResult]) -> None:
    """Append the cover page (title, metadata table, vessel summary) to *doc*."""
    doc.add_heading('SPPS Synthesis Guide', 0)
    doc.add_heading(synthesis_name, 1)

    # Metadata
    meta = doc.add_table(rows=5, cols=2)
    meta.style = 'Table Grid'
    meta_data = [
        ('Date:', '______________________________'),
        ('Operator:', '______________________________'),
        ('Synthesizer:', '______________________________'),
        ('Project:', '______________________________'),
        ('Page:', '1'),
    ]
    for i, (k, v) in enumerate(meta_data):
        meta.rows[i].cells[0].text = k
        meta.rows[i].cells[1].text = v
        meta.rows[i].cells[0].paragraphs[0].runs[0].bold = True

    doc.add_paragraph()

    # Vessel summary
    doc.add_heading(f'Synthesis Summary — {len(vessels)} vessel(s)', 2)
    yield_map = {yr.vessel_number: yr for yr in yield_results}

    summary_data = [['#', 'Name', 'Sequence (N→C)', 'Len', 'MW (Da)', 'Yield (mg)']]
    for v in vessels:
        yr = yield_map.get(v.number)
        seq = ''.join(v.original_tokens)
        summary_data.append([
            str(v.number), v.name,
            seq[:40] + ('...' if len(seq) > 40 else ''),
            str(v.length),
            f"{yr.peptide_mw:.1f}" if yr else '—',
            f"{yr.theoretical_yield_mg:.1f}" if yr else '—',
        ])

    _add_table_with_header(doc, summary_data)
    doc.add_page_break()


# ---------------------------------------------------------------------------
# Cycle pages
# ---------------------------------------------------------------------------

def _add_cycle_page(doc: Document, cycle: CouplingCycle,
                    config: SynthesisConfig, residue_info_map: Dict) -> None:
    """Add a single coupling cycle page to the DOCX document."""
    from spps_assistant.domain.sequence import parse_token
    from spps_assistant.domain.constants import FMOC_MW_DEFAULTS

    # Header
    p = doc.add_paragraph()
    run = p.add_run(
        f"Cycle {cycle.cycle_number} of {cycle.total_cycles}  |  "
        f"Date: ________________  |  Operator: ________________"
    )
    run.bold = True
    run.font.size = Pt(10)

    # Average resin mmol
    n_vessels = len(cycle.all_vessels)
    avg_resin_mmol = (
        sum(v.resin_mass_g * v.substitution_mmol_g for v in cycle.all_vessels) / n_vessels
        if n_vessels else 0.03
    )

    # AA Dispatch table
    doc.add_heading(f'Cycle {cycle.cycle_number} — AA Dispatch', 3)
    aa_data = [['Residue', 'Fmoc-MW', 'mmol', 'Volume (mL)', 'Formula', 'Status', 'Vessels']]
    for token, vessel_nums in cycle.residues_at_position.items():
        three = _token_to_3letter(token)
        n_v = len(vessel_nums)
        if token in residue_info_map:
            res = residue_info_map[token]
            fmoc_mw = res.fmoc_mw
            stock_conc = res.stock_conc
        else:
            try:
                base, _ = parse_token(token)
            except ValueError:
                base = 'X'
            fmoc_mw = FMOC_MW_DEFAULTS.get(token, FMOC_MW_DEFAULTS.get(base, 353.4))
            stock_conc = 0.5

        if config.volume_mode == 'legacy':
            volume_ml = calc_volume_legacy(n_v)
            formula_str = f"V = {n_v} × 2 mL"
        else:
            volume_ml = calc_volume_stoichiometry(
                n_v, config.aa_equivalents, avg_resin_mmol, stock_conc
            )
            formula_str = format_volume_formula(
                n_v, config.aa_equivalents, avg_resin_mmol, stock_conc, volume_ml
            )

        mmol = n_v * config.aa_equivalents * avg_resin_mmol
        aa_data.append([
            three, f"{fmoc_mw:.1f}", f"{mmol:.4f}", f"{volume_ml:.3f}",
            formula_str, '[ ]',
            ', '.join(str(vn) for vn in sorted(vessel_nums)),
        ])

    _add_table_with_header(doc, aa_data)
    doc.add_paragraph()

    # Deprotection table
    doc.add_heading('Deprotection', 3)
    dep_name = config.deprotection_reagent
    dep_data = [['[ ]', 'Step', 'Details', 'Time']]
    dep_data.append(['[ ]', '1. Deprotection', f'{dep_name} in DMF', '2 × 10 min'])
    dep_data.append(['[ ]', '2. DMF wash', 'DMF (3×)', '3 × 1 min'])
    if config.include_bb_test:
        dep_data.append(['[ ]', '3. BB test', 'Bromophenol Blue in DMF (1×)', '1 × 2 min'])
        dep_data.append(['[ ]', '4. DMF wash', 'DMF (2×)', '2 × 1 min'])
        dep_data.append(['[ ]', '5. DCM wash', 'DCM (2×)', '2 × 1 min'])
    else:
        dep_data.append(['[ ]', '3. DMF wash', 'DMF (2×)', '2 × 1 min'])
        dep_data.append(['[ ]', '4. DCM wash', 'DCM (2×)', '2 × 1 min'])
    if config.include_kaiser_test:
        dep_data.append(['[ ]', 'Kaiser test', 'Coupling completeness check', 'As needed'])

    _add_table_with_header(doc, dep_data, header_bg='1A5276')
    doc.add_paragraph()

    # Coupling table
    doc.add_heading('Coupling', 3)
    first_token = next(iter(cycle.residues_at_position), 'AA')
    coupling_label = _build_coupling_label(config, first_token)

    coup_data = [['[ ]', 'Step', 'Details', 'Time']]
    coup_data.append(['[ ]', '1st coupling', coupling_label, '30 min'])
    coup_data.append(['[ ]', '2nd coupling', f'Repeat: {coupling_label}', '30 min'])
    coup_data.append(['[ ]', '3rd coupling', f'Repeat: {coupling_label}', '30 min'])
    coup_data.append(['[ ]', '4th coupling', f'Repeat: {coupling_label}', '30 min'])
    coup_data.append(['', 'Post-coupling wash', 'DMF (2×1 min), DCM (3×1 min)', '5 min'])

    _add_table_with_header(doc, coup_data, header_bg='1E8449')
    doc.add_paragraph()

    # Vessel assignment
    p = doc.add_paragraph()
    p.add_run('Vessel Assignment:').bold = True
    for vessel in cycle.all_vessels:
        idx = cycle.cycle_number - 1
        if idx < len(vessel.reversed_tokens):
            tok = vessel.reversed_tokens[idx]
            three = _token_to_3letter(tok)
            text = f"  {config.vessel_label} {vessel.number} [{vessel.name}]: {three}"
        else:
            text = f"  {config.vessel_label} {vessel.number} [{vessel.name}]: OUT"
        doc.add_paragraph(text, style='List Bullet')

    # Secondary coupling table (Teabag method only)
    if config.vessel_method == 'Teabag':
        doc.add_heading('Secondary Coupling Verification', 3)
        sec_data = [['Vessel #', 'Name', 'Residue', '1st [ ]', '2nd [ ]', '3rd [ ]', '4th [ ]']]
        for vessel in cycle.all_vessels:
            idx = cycle.cycle_number - 1
            if idx < len(vessel.reversed_tokens):
                tok = vessel.reversed_tokens[idx]
                three = _token_to_3letter(tok)
            else:
                three = 'OUT'
            sec_data.append([
                str(vessel.number), vessel.name, three,
                '[ ]', '[ ]', '[ ]', '[ ]',
            ])
        _add_table_with_header(doc, sec_data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cycle_guide_docx(
    path: Path,
    synthesis_name: str,
    date_str: str,
    vessels: List[Vessel],
    coupling_cycles: List[CouplingCycle],
    config: SynthesisConfig,
    residue_info_map: Dict,
    yield_results: List[YieldResult],
) -> None:
    """Generate a GMP-compliant cycle guide DOCX document."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()

    # Cover
    _build_cover(doc, synthesis_name, vessels, yield_results)

    # Coupling cycle pages
    for i, cycle in enumerate(coupling_cycles):
        _add_cycle_page(doc, cycle, config, residue_info_map)
        if i < len(coupling_cycles) - 1:
            doc.add_page_break()

    doc.save(str(path))


def _add_orthogonal_warning_docx(doc: Document, orthogonal_tokens: List[str]) -> None:
    """Add a red-highlighted warning paragraph for orthogonal protecting groups."""
    from spps_assistant.domain.constants import ORTHOGONAL_PROTECTING_GROUPS
    from spps_assistant.domain.sequence import parse_token

    p = doc.add_paragraph()
    run = p.add_run('\u26a0  ORTHOGONAL PROTECTING GROUP — ADDITIONAL POST-SYNTHESIS STEP REQUIRED')
    run.bold = True
    run.font.color.rgb = RGBColor(0x7B, 0x24, 0x1C)
    run.font.size = Pt(9)

    for tok in orthogonal_tokens:
        try:
            _, prot = parse_token(tok)
        except ValueError:
            prot = ''
        info = ORTHOGONAL_PROTECTING_GROUPS.get(prot, {})
        display = info.get('display', tok)
        msg = info.get('warning', 'Requires special deprotection — not removed by TFA.')
        bp = doc.add_paragraph(style='List Bullet')
        run2 = bp.add_run(f'{display} ({tok}): ')
        run2.bold = True
        run2.font.color.rgb = RGBColor(0x7B, 0x24, 0x1C)
        run2.font.size = Pt(9)
        run3 = bp.add_run(msg)
        run3.font.color.rgb = RGBColor(0x7B, 0x24, 0x1C)
        run3.font.size = Pt(9)


def generate_peptide_info_docx(
    path: Path,
    synthesis_name: str,
    vessels: List[Vessel],
    solubility_results: Dict[int, SolubilityResult],
    yield_results: List[YieldResult],
) -> None:
    """Generate peptide physicochemical info DOCX."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()
    doc.add_heading(f'Peptide Information — {synthesis_name}', 0)

    yield_map = {yr.vessel_number: yr for yr in yield_results}

    for vessel in vessels:
        sol = solubility_results.get(vessel.number)
        yr = yield_map.get(vessel.number)

        doc.add_heading(f'Vessel {vessel.number}: {vessel.name}', 1)

        seq_str = ''.join(vessel.original_tokens)
        rev_str = ''.join(vessel.reversed_tokens)

        info_data = [
            ['Property', 'Value'],
            ['Sequence (N→C)', seq_str],
            ['Synthesis order (C→N)', rev_str],
            ['Length', str(vessel.length)],
            ['Peptide MW (Da)', f"{yr.peptide_mw:.2f}" if yr else '—'],
            ['Theoretical Yield (mg)', f"{yr.theoretical_yield_mg:.2f}" if yr else '—'],
            ['Resin mass (g)', f"{vessel.resin_mass_g:.4f}"],
            ['Resin substitution (mmol/g)', f"{vessel.substitution_mmol_g:.4f}"],
            ['Yield formula', yr.formula_shown if yr else '—'],
        ]

        if sol:
            info_data += [
                ['GRAVY score', f"{sol.gravy:.3f}" if sol.gravy is not None else '—'],
                ['Net charge (pH 7)', f"{sol.net_charge_ph7:.2f}" if sol.net_charge_ph7 is not None else '—'],
                ['pI', f"{sol.pI:.2f}" if sol.pI is not None else '—'],
                ['Hydrophobicity (KD)', f"{sol.kd_avg:.3f}"],
                ['Hydrophobicity (Eisenberg)', f"{sol.eisenberg_avg:.3f}"],
                ['Hydrophobicity (Black & Mould)', f"{sol.black_mould_avg:.3f}"],
                ['Classification', 'Hydrophobic' if sol.is_hydrophobic else 'Hydrophilic'],
                ['Light sensitive', 'Yes' if sol.light_sensitive else 'No'],
                ['Solubilization', sol.recommendation],
            ]

        _add_table_with_header(doc, info_data)

        if sol and sol.orthogonal_groups:
            _add_orthogonal_warning_docx(doc, sol.orthogonal_groups)

        doc.add_paragraph()

    doc.save(str(path))
