"""ReportLab PDF generator for SPPS synthesis guides and peptide info sheets."""

from pathlib import Path
from typing import Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, SimpleDocTemplate,
    Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from spps_assistant.domain.constants import THREE_LETTER_CODE
from spps_assistant.domain.models import (
    CouplingCycle, SynthesisConfig, Vessel, YieldResult, SolubilityResult, MaterialsRow
)
from spps_assistant.domain.stoichiometry import (
    calc_volume_stoichiometry, calc_volume_legacy, calc_mass_mg, format_volume_formula
)

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

_styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    'SPPSTitle', fontSize=16, fontName='Helvetica-Bold',
    alignment=TA_CENTER, spaceAfter=6
)
SECTION_STYLE = ParagraphStyle(
    'SPPSSection', fontSize=11, fontName='Helvetica-Bold',
    alignment=TA_LEFT, spaceAfter=3, spaceBefore=6
)
BODY_STYLE = ParagraphStyle(
    'SPPSBody', fontSize=9, fontName='Helvetica',
    alignment=TA_LEFT, spaceAfter=2
)
SMALL_STYLE = ParagraphStyle(
    'SPPSSmall', fontSize=8, fontName='Helvetica',
    alignment=TA_LEFT, spaceAfter=1
)
HEADER_STYLE = ParagraphStyle(
    'SPPSHeader', fontSize=10, fontName='Helvetica-Bold',
    alignment=TA_CENTER, spaceAfter=4
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TABLE_HEADER_STYLE = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 9),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8F9FA'), colors.white]),
    ('FONTSIZE', (0, 1), (-1, -1), 8),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
])

DEPROTECTION_STYLE = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A5276')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 9),
    ('FONTSIZE', (0, 1), (-1, -1), 8),
    ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # checkbox column centered
    ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#EBF5FB'), colors.white]),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
])

COUPLING_STYLE = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E8449')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 9),
    ('FONTSIZE', (0, 1), (-1, -1), 8),
    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
    ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#EAFAF1'), colors.white]),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
])


def _token_to_3letter(token: str) -> str:
    """Convert token to 3-letter display name."""
    from spps_assistant.domain.sequence import parse_token
    try:
        base, prot = parse_token(token)
    except ValueError:
        return token
    three = THREE_LETTER_CODE.get(base, base)
    return f"{three}({prot})" if prot else three


def _build_coupling_label(config: SynthesisConfig, token: str) -> str:
    """Build activator/coupling label string for GMP table."""
    three = _token_to_3letter(token)
    act = config.activator
    base = config.base

    if act in ('DIC', 'DCC'):
        if config.use_oxyma:
            return f"{three} + {act} + Oxyma"
        else:
            return f"{three} + {act}"
    else:
        # HBTU/TBTU/HCTU
        if config.use_oxyma and base not in ('None', 'none', ''):
            return f"{three} + {act} + Oxyma + {base}"
        elif config.use_oxyma:
            return f"{three} + {act} + Oxyma"
        else:
            return f"{three} + {act} + {base}"


def _header_paragraph(
    synthesis_name: str,
    date_str: str,
    cycle_num: Optional[int],
    total_cycles: Optional[int],
) -> List:
    """Build a simple header paragraph list for cycle pages."""
    if cycle_num is not None:
        text = (
            f"<b>{synthesis_name}</b>  |  Date: ________________  |  "
            f"Operator: ________________  |  "
            f"Cycle <b>{cycle_num}</b> of <b>{total_cycles}</b>"
        )
    else:
        text = f"<b>{synthesis_name}</b>  |  Date: ________________  |  Operator: ________________"
    return [Paragraph(text, BODY_STYLE), Spacer(1, 4 * mm)]


# ---------------------------------------------------------------------------
# Cover page helpers
# ---------------------------------------------------------------------------

def _build_cover_elements(
    synthesis_name: str,
    date_str: str,
    vessels: List[Vessel],
    yield_results: List[YieldResult],
) -> List:
    """Build cover page flowables."""
    elems = []

    elems.append(Spacer(1, 15 * mm))
    elems.append(Paragraph("SPPS Synthesis Guide", TITLE_STYLE))
    elems.append(Paragraph(synthesis_name, TITLE_STYLE))
    elems.append(Spacer(1, 8 * mm))

    # Metadata table
    meta_data = [
        ['Date:', '______________________________'],
        ['Operator:', '______________________________'],
        ['Synthesizer:', '______________________________'],
        ['Project:', '______________________________'],
        ['Page:', '1'],
    ]
    meta_table = Table(meta_data, colWidths=[4 * cm, 10 * cm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    elems.append(meta_table)
    elems.append(Spacer(1, 10 * mm))

    # Vessel summary table
    elems.append(Paragraph(f"Synthesis Summary — {len(vessels)} vessel(s)", SECTION_STYLE))

    yield_map = {yr.vessel_number: yr for yr in yield_results}

    summary_data = [
        ['#', 'Name', 'Sequence (N→C)', 'Length', 'Peptide MW (Da)', 'Yield est. (mg)']
    ]
    for v in vessels:
        yr = yield_map.get(v.number)
        seq_display = ''.join(v.original_tokens)
        summary_data.append([
            str(v.number),
            v.name,
            seq_display[:40] + ('...' if len(seq_display) > 40 else ''),
            str(v.length),
            f"{yr.peptide_mw:.1f}" if yr else '—',
            f"{yr.theoretical_yield_mg:.1f}" if yr else '—',
        ])

    sum_table = Table(
        summary_data,
        colWidths=[1.2 * cm, 3.5 * cm, 6.5 * cm, 1.5 * cm, 3.0 * cm, 2.5 * cm],
    )
    sum_table.setStyle(TABLE_HEADER_STYLE)
    elems.append(sum_table)
    elems.append(PageBreak())
    return elems


# ---------------------------------------------------------------------------
# Cycle page helpers
# ---------------------------------------------------------------------------

def _build_aa_dispatch_table(
    cycle: CouplingCycle,
    config: SynthesisConfig,
    residue_info_map: Dict,
) -> Table:
    """Build the AA dispatch table for a coupling cycle page."""
    from spps_assistant.domain.sequence import parse_token

    # Compute resin_mmol using average resin mass across all vessels
    total_resin_mmol = 0.0
    n_vessels = len(cycle.all_vessels)
    for v in cycle.all_vessels:
        total_resin_mmol += v.resin_mass_g * v.substitution_mmol_g
    avg_resin_mmol = total_resin_mmol / n_vessels if n_vessels else 0.03

    data = [['Residue (3-letter)', 'Fmoc-MW (g/mol)', 'mmol', 'Volume (mL)', 'Formula', 'Status', 'Vessels']]

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
            from spps_assistant.domain.constants import FMOC_MW_DEFAULTS
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
        vessels_str = ', '.join(str(vn) for vn in sorted(vessel_nums))

        data.append([
            three,
            f"{fmoc_mw:.1f}",
            f"{mmol:.4f}",
            f"{volume_ml:.3f}",
            formula_str,
            '[ ]',
            vessels_str,
        ])

    col_widths = [2.5 * cm, 2.5 * cm, 1.8 * cm, 2.2 * cm, 7.0 * cm, 1.2 * cm, 2.5 * cm]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TABLE_HEADER_STYLE)
    return table


def _build_deprotection_table(config: SynthesisConfig) -> Table:
    """Build the GMP deprotection steps table."""
    rows = [['[ ]', 'Step', 'Details', 'Time']]

    dep_name = config.deprotection_reagent
    rows.append(['[ ]', '1. Deprotection', f'{dep_name} in DMF', '2 × 10 min'])
    rows.append(['[ ]', '2. DMF wash', 'DMF (3×)', '3 × 1 min'])

    if config.include_bb_test:
        rows.append(['[ ]', '3. Bromophenol Blue test', 'Bromophenol Blue in DMF (1×)', '1 × 2 min'])
        rows.append(['[ ]', '4. DMF wash', 'DMF (2×)', '2 × 1 min'])
        rows.append(['[ ]', '5. DCM wash', 'DCM (2×)', '2 × 1 min'])
    else:
        rows.append(['[ ]', '3. DMF wash', 'DMF (2×)', '2 × 1 min'])
        rows.append(['[ ]', '4. DCM wash', 'DCM (2×)', '2 × 1 min'])

    if config.include_kaiser_test:
        rows.append(['[ ]', 'Kaiser test', 'Coupling completeness check', 'As needed'])

    col_widths = [1.0 * cm, 4.0 * cm, 8.0 * cm, 3.0 * cm]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(DEPROTECTION_STYLE)
    return table


def _build_coupling_table(config: SynthesisConfig, cycle: CouplingCycle) -> Table:
    """Build the GMP coupling steps table."""
    # Get a representative token for this cycle
    first_token = next(iter(cycle.residues_at_position), 'AA')
    coupling_label = _build_coupling_label(config, first_token)

    rows = [['[ ]', 'Step', 'Details', 'Time']]
    rows.append(['[ ]', '1st coupling', coupling_label, '30 min'])
    rows.append(['[ ]', '2nd coupling', f'Repeat: {coupling_label}', '30 min'])
    rows.append(['[ ]', '3rd coupling', f'Repeat: {coupling_label}', '30 min'])
    rows.append(['[ ]', '4th coupling', f'Repeat: {coupling_label}', '30 min'])
    rows.append(['', 'Post-coupling wash', 'DMF (2×1 min), DCM (3×1 min)', '5 min'])

    col_widths = [1.0 * cm, 3.0 * cm, 10.0 * cm, 2.5 * cm]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(COUPLING_STYLE)
    return table


def _build_vessel_assignment_line(cycle: CouplingCycle, config: SynthesisConfig) -> List:
    """Build vessel assignment text lines for the bottom of a cycle page."""
    elems = []
    elems.append(Paragraph("Vessel Assignment:", SECTION_STYLE))
    for vessel in cycle.all_vessels:
        idx = cycle.cycle_number - 1
        if idx < len(vessel.reversed_tokens):
            tok = vessel.reversed_tokens[idx]
            three = _token_to_3letter(tok)
            line = (
                f"{config.vessel_label} <b>{vessel.number}</b> [{vessel.name}]: "
                f"{three}"
            )
        else:
            line = f"{config.vessel_label} <b>{vessel.number}</b> [{vessel.name}]: OUT"
        elems.append(Paragraph(line, SMALL_STYLE))
    return elems


def _build_secondary_coupling_table(cycle: CouplingCycle, config: SynthesisConfig) -> Optional[Table]:
    """Build the secondary coupling verification table (Teabag method only)."""
    if config.vessel_method != 'Teabag':
        return None

    rows = [['Vessel #', 'Name', 'Residue', '1st [ ]', '2nd [ ]', '3rd [ ]', '4th [ ]']]
    for vessel in cycle.all_vessels:
        idx = cycle.cycle_number - 1
        if idx < len(vessel.reversed_tokens):
            tok = vessel.reversed_tokens[idx]
            three = _token_to_3letter(tok)
        else:
            three = 'OUT'
        rows.append([
            str(vessel.number), vessel.name, three,
            '[ ]', '[ ]', '[ ]', '[ ]'
        ])

    col_widths = [1.5 * cm, 4.0 * cm, 2.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(TABLE_HEADER_STYLE)
    return table


def _build_cycle_page_elements(
    cycle: CouplingCycle,
    config: SynthesisConfig,
    residue_info_map: Dict,
) -> List:
    """Build all flowables for a single coupling cycle page."""
    elems = []

    # Header
    elems.extend(_header_paragraph('', '', cycle.cycle_number, cycle.total_cycles))

    # AA dispatch
    elems.append(Paragraph(
        f"Cycle {cycle.cycle_number} of {cycle.total_cycles} — AA Dispatch",
        SECTION_STYLE
    ))
    elems.append(_build_aa_dispatch_table(cycle, config, residue_info_map))
    elems.append(Spacer(1, 3 * mm))

    # Deprotection
    elems.append(Paragraph("Deprotection", SECTION_STYLE))
    elems.append(_build_deprotection_table(config))
    elems.append(Spacer(1, 3 * mm))

    # Coupling
    elems.append(Paragraph("Coupling", SECTION_STYLE))
    elems.append(_build_coupling_table(config, cycle))
    elems.append(Spacer(1, 3 * mm))

    # Vessel assignment
    elems.extend(_build_vessel_assignment_line(cycle, config))
    elems.append(Spacer(1, 3 * mm))

    # Secondary coupling table (Teabag only)
    sec_table = _build_secondary_coupling_table(cycle, config)
    if sec_table is not None:
        elems.append(Paragraph("Secondary Coupling Verification", SECTION_STYLE))
        elems.append(sec_table)

    return elems


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cycle_guide_pdf(
    path: Path,
    synthesis_name: str,
    date_str: str,
    vessels: List[Vessel],
    coupling_cycles: List[CouplingCycle],
    config: SynthesisConfig,
    residue_info_map: Dict,
    yield_results: List[YieldResult],
) -> None:
    """Generate a GMP-compliant cycle guide PDF.

    Args:
        path: Output PDF file path
        synthesis_name: Name of the synthesis run
        date_str: ISO date string
        vessels: List of Vessel objects
        coupling_cycles: Ordered list of CouplingCycle objects
        config: SynthesisConfig parameters
        residue_info_map: Token -> ResidueInfo map
        yield_results: List of YieldResult per vessel
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    elements = []

    # Cover page
    elements.extend(
        _build_cover_elements(synthesis_name, date_str, vessels, yield_results)
    )

    # One page per coupling cycle
    for cycle in coupling_cycles:
        cycle_elems = _build_cycle_page_elements(cycle, config, residue_info_map)
        # Synthesis name header at top of each cycle page
        header = Paragraph(
            f"<b>{synthesis_name}</b>  |  Cycle {cycle.cycle_number}/{cycle.total_cycles}  "
            f"|  Date: ________________  |  Operator: ________________",
            BODY_STYLE,
        )
        elements.append(header)
        elements.append(Spacer(1, 2 * mm))
        # Skip first element (already added header above)
        for elem in cycle_elems[2:]:
            elements.append(elem)
        elements.append(PageBreak())

    doc.build(elements)


def _add_orthogonal_warning_pdf(elements: list, orthogonal_tokens: List[str]) -> None:
    """Append a red-bordered warning box for orthogonal protecting groups."""
    from spps_assistant.domain.constants import ORTHOGONAL_PROTECTING_GROUPS
    from spps_assistant.domain.sequence import parse_token

    warning_lines = ['\u26a0  ORTHOGONAL PROTECTING GROUP — ADDITIONAL POST-SYNTHESIS STEP REQUIRED']
    for tok in orthogonal_tokens:
        try:
            _, prot = parse_token(tok)
        except ValueError:
            prot = ''
        info = ORTHOGONAL_PROTECTING_GROUPS.get(prot, {})
        display = info.get('display', tok)
        msg = info.get('warning', 'Requires special deprotection — not removed by TFA.')
        warning_lines.append(f'{display} ({tok}): {msg}')

    warn_style = ParagraphStyle(
        'OrthoWarn', fontSize=8, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#7B241C'),
        leftPadding=6, rightPadding=6,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        'OrthoBody', fontSize=8, fontName='Helvetica',
        textColor=colors.HexColor('#7B241C'),
        leftPadding=6, rightPadding=6,
        spaceAfter=1,
    )

    box_content = [[Paragraph(warning_lines[0], warn_style)]]
    for line in warning_lines[1:]:
        box_content.append([Paragraph(line, body_style)])

    box_table = Table(box_content, colWidths=[17.5 * cm])
    box_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#C0392B')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FDEDEC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(box_table)


def generate_peptide_info_pdf(
    path: Path,
    synthesis_name: str,
    vessels: List[Vessel],
    solubility_results: Dict[int, SolubilityResult],
    yield_results: List[YieldResult],
) -> None:
    """Generate peptide physicochemical info PDF.

    Args:
        path: Output PDF path
        synthesis_name: Synthesis name
        vessels: List of Vessel objects
        solubility_results: vessel_number -> SolubilityResult
        yield_results: List of YieldResult objects
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )

    elements = []
    elements.append(Paragraph(f"Peptide Information — {synthesis_name}", TITLE_STYLE))
    elements.append(Spacer(1, 5 * mm))

    yield_map = {yr.vessel_number: yr for yr in yield_results}

    for vessel in vessels:
        sol = solubility_results.get(vessel.number)
        yr = yield_map.get(vessel.number)

        elements.append(Paragraph(
            f"Vessel {vessel.number}: {vessel.name}",
            SECTION_STYLE,
        ))

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
                ['Hydrophobicity (KD avg)', f"{sol.kd_avg:.3f}"],
                ['Hydrophobicity (Eisenberg)', f"{sol.eisenberg_avg:.3f}"],
                ['Hydrophobicity (Black & Mould)', f"{sol.black_mould_avg:.3f}"],
                ['Classification', 'Hydrophobic' if sol.is_hydrophobic else 'Hydrophilic'],
                ['Light sensitive', 'Yes (protect from light)' if sol.light_sensitive else 'No'],
                ['Solubilization', sol.recommendation],
            ]

        info_table = Table(info_data, colWidths=[6 * cm, 11.5 * cm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8F9FA'), colors.white]),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))

        elements.append(info_table)

        if sol and sol.orthogonal_groups:
            elements.append(Spacer(1, 2 * mm))
            _add_orthogonal_warning_pdf(elements, sol.orthogonal_groups)

        elements.append(Spacer(1, 5 * mm))

    doc.build(elements)


def generate_materials_pdf(
    path: Path,
    synthesis_name: str,
    materials_rows: List[MaterialsRow],
    config_summary: Dict,
) -> None:
    """Generate a materials list PDF.

    Args:
        path: Output PDF path
        synthesis_name: Synthesis name
        materials_rows: List of MaterialsRow objects
        config_summary: Dict of config key-value pairs to display
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )

    elements = []
    elements.append(Paragraph(f"Materials List — {synthesis_name}", TITLE_STYLE))
    elements.append(Spacer(1, 4 * mm))

    # Config summary
    conf_data = [['Parameter', 'Value']]
    for k, v in config_summary.items():
        conf_data.append([str(k), str(v)])
    conf_table = Table(conf_data, colWidths=[6 * cm, 6 * cm])
    conf_table.setStyle(TABLE_HEADER_STYLE)
    elements.append(conf_table)
    elements.append(Spacer(1, 4 * mm))

    # Materials table
    mat_data = [[
        'Residue', 'Protection', 'Fmoc-MW (g/mol)',
        'mmol needed', 'Mass (mg)', 'Stock (M)', 'Volume (mL)', 'Notes'
    ]]
    for row in materials_rows:
        mat_data.append([
            row.token,
            row.protection,
            f"{row.fmoc_mw:.1f}",
            f"{row.mmol_needed:.4f}",
            f"{row.mass_mg:.2f}",
            f"{row.stock_conc:.2f}",
            f"{row.volume_ml:.3f}",
            row.notes,
        ])

    col_widths = [2.0 * cm, 2.5 * cm, 2.5 * cm, 2.2 * cm, 2.5 * cm, 2.0 * cm, 2.5 * cm, 3.5 * cm]
    mat_table = Table(mat_data, colWidths=col_widths)
    mat_table.setStyle(TABLE_HEADER_STYLE)
    elements.append(mat_table)

    doc.build(elements)
