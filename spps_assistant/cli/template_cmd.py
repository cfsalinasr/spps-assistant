"""spps-assistant template — generate blank materials input templates."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command('template')
@click.option('--output-dir', '-o', default='.', type=click.Path(),
              help='Directory to write template files (default: current directory).')
def template(output_dir: str) -> None:
    """Generate blank materials input template files.

    Creates two files:
        spps_materials_template.csv   — CSV template for Fmoc-AA MW values
        spps_materials_template.xlsx  — XLSX version for spreadsheet editing

    Fill these in and pass to --materials when running 'generate' or 'materials'.
    """
    import csv
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    headers = [
        'ResidueCode', 'ProtectionGroup', 'FmocMW_g_mol',
        'FreeAA_MW_g_mol', 'StockConc_M', 'Notes'
    ]

    example_rows = [
        ['A', '', '311.3', '71.08', '0.5', 'Fmoc-Ala-OH'],
        ['G', '', '297.3', '57.05', '0.5', 'Fmoc-Gly-OH'],
        ['C', 'Trt', '585.7', '103.14', '0.5', 'Fmoc-Cys(Trt)-OH'],
        ['K', 'Boc', '468.6', '128.17', '0.5', 'Fmoc-Lys(Boc)-OH'],
    ]

    # CSV template
    csv_path = out_path / 'spps_materials_template.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(example_rows)
        # Blank rows for user to fill in
        for _ in range(20):
            writer.writerow([''] * len(headers))

    console.print(f"  [green]CSV template:[/green] {csv_path}")

    # XLSX template
    xlsx_path = out_path / 'spps_materials_template.xlsx'
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Materials'

    thin_side = Side(style='thin', color='AAAAAA')
    thin_border = Border(
        left=thin_side, right=thin_side, top=thin_side, bottom=thin_side
    )

    # Header row
    col_widths = [14, 18, 18, 18, 14, 35]
    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(name='Calibri', size=13, bold=True, color='FFFFFF')
        cell.fill = PatternFill(fill_type='solid', fgColor='2C3E50')
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[1].height = 28

    # Example rows
    for row_idx, row_data in enumerate(example_rows, start=2):
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = Font(name='Calibri', size=12)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center', vertical='center')
            if row_idx % 2 == 0:
                cell.fill = PatternFill(fill_type='solid', fgColor='EBF5FB')

    # Blank rows
    for row_idx in range(len(example_rows) + 2, len(example_rows) + 22):
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx, value='')
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center', vertical='center')

    ws.freeze_panes = 'A2'
    wb.save(str(xlsx_path))

    console.print(f"  [green]XLSX template:[/green] {xlsx_path}")

    console.print(Panel(
        "Fill in your Fmoc-AA molecular weights and pass the file to\n"
        "  [bold]spps-assistant generate --materials <file>[/bold]\n"
        "  [bold]spps-assistant materials --materials <file>[/bold]\n\n"
        "Required columns: ResidueCode, ProtectionGroup, FmocMW_g_mol,\n"
        "                  FreeAA_MW_g_mol, StockConc_M",
        title="Materials Template",
        border_style="cyan",
    ))
