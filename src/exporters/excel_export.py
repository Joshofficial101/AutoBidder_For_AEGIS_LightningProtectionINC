"""
Excel Bid Sheet Exporter

This module creates professional Excel bid sheets from Bid objects.
The output matches contractor templates with proper formatting.
"""

from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from src.models.bid import Bid
from datetime import date


class ExcelBidExporter:
    """
    Exports Bid objects to formatted Excel spreadsheets.

    Creates a professional bid sheet with:
    - Sheet 1: Bill of Materials (itemized list)
    - Sheet 2: Cost Summary (totals by section)
    - Sheet 3: Final Bid (with markup)
    """

    def __init__(self):
        """Initialize exporter with standard formatting styles."""
        # Define reusable styles
        self.header_font = Font(name='Arial', size=12, bold=True, color='FFFFFF')
        self.header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        self.section_font = Font(name='Arial', size=11, bold=True)
        self.section_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
        self.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

    def export_bid(self, bid: Bid, output_path: Path) -> Path:
        """
        Export a Bid to Excel file.

        Args:
            bid: The Bid object to export
            output_path: Where to save the Excel file

        Returns:
            Path to the created file
        """
        wb = Workbook()

        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            wb.remove(wb['Sheet'])

        # Create three sheets
        self._create_bill_of_materials_sheet(wb, bid)
        self._create_cost_summary_sheet(wb, bid)
        self._create_final_bid_sheet(wb, bid)

        # Save workbook
        wb.save(output_path)
        return output_path

    def _create_bill_of_materials_sheet(self, wb: Workbook, bid: Bid):
        """Create detailed Bill of Materials sheet."""
        ws = wb.create_sheet("Bill of Materials")

        # Title
        ws['A1'] = f"Lightning Protection Bid - {bid.project_name}"
        ws['A1'].font = Font(size=14, bold=True)
        ws['A2'] = f"Date: {date.today().strftime('%m/%d/%Y')}"

        # Headers
        headers = ['Section', 'Item Code', 'Description', 'Material', 'Qty', 'Unit', 'Unit Price', 'Material Cost', 'Labor Cost', 'Total', 'Notes']
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col, value=header)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = self.border

        # Data rows
        current_row = 5
        for section in bid.sections:
            # Section header row
            ws.cell(row=current_row, column=1, value=section.name)
            ws.cell(row=current_row, column=1).font = self.section_font
            ws.cell(row=current_row, column=1).fill = self.section_fill
            for col in range(1, 12):
                ws.cell(row=current_row, column=col).fill = self.section_fill
            current_row += 1

            # Line items
            for item in section.line_items:
                ws.cell(row=current_row, column=1, value="")  # Empty section column
                ws.cell(row=current_row, column=2, value=item.price_item.code)
                ws.cell(row=current_row, column=3, value=item.price_item.name)
                ws.cell(row=current_row, column=4, value=item.price_item.material_type or "")
                ws.cell(row=current_row, column=5, value=item.quantity)
                ws.cell(row=current_row, column=6, value=item.price_item.unit or "ea")
                ws.cell(row=current_row, column=7, value=item.price_item.unit_price)
                ws.cell(row=current_row, column=8, value=item.material_cost)
                ws.cell(row=current_row, column=9, value=item.labor_cost or 0)
                ws.cell(row=current_row, column=10, value=item.material_cost + (item.labor_cost or 0))
                ws.cell(row=current_row, column=11, value=item.reason or "")

                # Format currency cells
                for col in [7, 8, 9, 10]:
                    ws.cell(row=current_row, column=col).number_format = '$#,##0.00'

                current_row += 1

            current_row += 1  # Blank row between sections

        # Column widths
        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 12
        ws.column_dimensions['C'].width = 35
        ws.column_dimensions['D'].width = 12
        ws.column_dimensions['E'].width = 8
        ws.column_dimensions['F'].width = 8
        ws.column_dimensions['G'].width = 12
        ws.column_dimensions['H'].width = 14
        ws.column_dimensions['I'].width = 12
        ws.column_dimensions['J'].width = 12
        ws.column_dimensions['K'].width = 40

    def _create_cost_summary_sheet(self, wb: Workbook, bid: Bid):
        """Create Cost Summary sheet with section totals."""
        ws = wb.create_sheet("Cost Summary")

        # Title
        ws['A1'] = "Cost Summary by Section"
        ws['A1'].font = Font(size=14, bold=True)

        # Headers
        headers = ['Section', 'Material Cost', 'Labor Cost', 'Section Total']
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=3, column=col, value=header)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.alignment = Alignment(horizontal='center')

        # Section totals
        current_row = 4
        for section in bid.sections:
            ws.cell(row=current_row, column=1, value=section.name)
            ws.cell(row=current_row, column=2, value=section.total_material)
            ws.cell(row=current_row, column=3, value=section.total_labor)
            ws.cell(row=current_row, column=4, value=section.section_total)

            # Format currency
            for col in [2, 3, 4]:
                ws.cell(row=current_row, column=col).number_format = '$#,##0.00'

            current_row += 1

        # Totals row
        current_row += 1
        ws.cell(row=current_row, column=1, value="TOTAL")
        ws.cell(row=current_row, column=1).font = Font(bold=True)
        ws.cell(row=current_row, column=2, value=bid.subtotal_material)
        ws.cell(row=current_row, column=3, value=bid.subtotal_labor)
        ws.cell(row=current_row, column=4, value=bid.subtotal)

        for col in [2, 3, 4]:
            cell = ws.cell(row=current_row, column=col)
            cell.number_format = '$#,##0.00'
            cell.font = Font(bold=True)
            cell.fill = self.section_fill

        # Column widths
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 15

    def _create_final_bid_sheet(self, wb: Workbook, bid: Bid):
        """Create Final Bid sheet with markup and totals."""
        ws = wb.create_sheet("Final Bid")

        # Title
        ws['A1'] = f"Final Bid - {bid.project_name}"
        ws['A1'].font = Font(size=14, bold=True)

        # Subtotals
        row = 3
        ws.cell(row=row, column=1, value="Subtotal (Material):")
        ws.cell(row=row, column=2, value=bid.subtotal_material)
        ws.cell(row=row, column=2).number_format = '$#,##0.00'
        row += 1

        ws.cell(row=row, column=1, value="Subtotal (Labor):")
        ws.cell(row=row, column=2, value=bid.subtotal_labor)
        ws.cell(row=row, column=2).number_format = '$#,##0.00'
        row += 1

        ws.cell(row=row, column=1, value="Subtotal:")
        ws.cell(row=row, column=2, value=bid.subtotal)
        ws.cell(row=row, column=2).number_format = '$#,##0.00'
        ws.cell(row=row, column=1).font = Font(bold=True)
        ws.cell(row=row, column=2).font = Font(bold=True)
        row += 2

        # Markup
        ws.cell(row=row, column=1, value=f"Material Markup ({bid.material_markup_pct}%):")
        mat_markup = bid.subtotal_material * (bid.material_markup_pct / 100)
        ws.cell(row=row, column=2, value=mat_markup)
        ws.cell(row=row, column=2).number_format = '$#,##0.00'
        row += 1

        ws.cell(row=row, column=1, value=f"Labor Markup ({bid.labor_markup_pct}%):")
        lab_markup = bid.subtotal_labor * (bid.labor_markup_pct / 100)
        ws.cell(row=row, column=2, value=lab_markup)
        ws.cell(row=row, column=2).number_format = '$#,##0.00'
        row += 1

        ws.cell(row=row, column=1, value="Total with Markup:")
        ws.cell(row=row, column=2, value=bid.total_with_markup)
        ws.cell(row=row, column=2).number_format = '$#,##0.00'
        ws.cell(row=row, column=1).font = Font(bold=True)
        ws.cell(row=row, column=2).font = Font(bold=True)
        row += 2

        # Overhead & Profit
        ws.cell(row=row, column=1, value=f"Overhead ({bid.overhead_pct}%):")
        overhead = bid.total_with_markup * (bid.overhead_pct / 100)
        ws.cell(row=row, column=2, value=overhead)
        ws.cell(row=row, column=2).number_format = '$#,##0.00'
        row += 1

        ws.cell(row=row, column=1, value=f"Profit ({bid.profit_pct}%):")
        profit = bid.total_with_markup * (bid.profit_pct / 100)
        ws.cell(row=row, column=2, value=profit)
        ws.cell(row=row, column=2).number_format = '$#,##0.00'
        row += 2

        # FINAL BID
        ws.cell(row=row, column=1, value="FINAL BID AMOUNT:")
        ws.cell(row=row, column=2, value=bid.final_bid_amount)
        ws.cell(row=row, column=1).font = Font(size=14, bold=True)
        ws.cell(row=row, column=2).font = Font(size=14, bold=True)
        ws.cell(row=row, column=2).number_format = '$#,##0.00'
        ws.cell(row=row, column=2).fill = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')

        # Column widths
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 20
