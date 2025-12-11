"""
Main Flet GUI Window for LightningBid

This is the primary GUI interface that orchestrates the entire
bidding workflow through a user-friendly graphical interface.
"""

import flet as ft
from pathlib import Path
from typing import Optional, Dict, Any
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.adapters.excel_loader import load_pricing_from_excel
from src.adapters.pdf_loader import extract_project_data
from src.calculator.bid_calc import BidCalculator
from src.exporters.excel_export import ExcelBidExporter
from src.exporters.pdf_export import PDFSubmittalExporter
from src.models.items import PriceItem


class LightningBidApp:
    """
    Main application class for LightningBid GUI.
    
    This class manages the entire GUI state and workflow.
    """
    
    def __init__(self, page: ft.Page):
        """Initialize the application."""
        self.page = page
        self.page.title = "LightningBid - Lightning Protection Bidding System"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window.width = 1200
        self.page.window.height = 800
        self.page.window.min_width = 1000
        self.page.window.min_height = 600
        
        # Application state
        self.price_catalog: list[PriceItem] = []
        self.current_bid = None
        self.project_data: Dict[str, Any] = {
            "project_name": "",
            "building_height_ft": None,
            "roof_area_sqft": None,
            "num_corners": 4,
            "perimeter_ft": None,
            "num_downleads": 2,
            "soil_type": "normal",
            "has_metal_roof": False,
            "preferred_material": "copper"
        }
        self.compliance_code = "UL 96A"
        
        # File paths
        self.excel_file_path: Optional[Path] = None
        self.pdf_file_path: Optional[Path] = None
        self.output_dir = Path(__file__).parent.parent.parent / "data" / "outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build UI
        self._build_ui()
    
    def _build_ui(self):
        """Build the main user interface."""
        # File selection section
        file_section = self._build_file_section()
        
        # Project information section
        project_section = self._build_project_section()
        
        # Actions section
        actions_section = self._build_actions_section()
        
        # Bid display section
        bid_display = self._build_bid_display()
        
        # Add file pickers to overlay (must be done after page is ready)
        self.page.overlay.append(self.excel_file_picker)
        self.page.overlay.append(self.pdf_file_picker)
        
        # Layout
        self.page.add(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "LightningBid - Lightning Protection Bidding System",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLUE_700
                        ),
                        ft.Divider(),
                        file_section,
                        ft.Divider(),
                        project_section,
                        ft.Divider(),
                        actions_section,
                        ft.Divider(),
                        bid_display,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    spacing=15
                ),
                padding=20,
                expand=True
            )
        )
    
    def _build_file_section(self) -> ft.Container:
        """Build file selection section."""
        # Excel file picker
        self.excel_file_picker = ft.FilePicker(
            on_result=self._on_excel_selected
        )
        
        self.excel_file_text = ft.Text(
            "No Excel file selected",
            size=12,
            color=ft.Colors.GREY
        )
        
        excel_btn = ft.ElevatedButton(
            "📊 Select Excel Pricing File",
            on_click=lambda _: self.excel_file_picker.pick_files(
                allowed_extensions=["xlsx", "xls"],
                dialog_title="Select Excel Pricing File"
            )
        )
        
        # PDF file picker
        self.pdf_file_picker = ft.FilePicker(
            on_result=self._on_pdf_selected
        )
        
        self.pdf_file_text = ft.Text(
            "No PDF file selected",
            size=12,
            color=ft.Colors.GREY
        )
        
        pdf_btn = ft.ElevatedButton(
            "📄 Select PDF Specification",
            on_click=lambda _: self.pdf_file_picker.pick_files(
                allowed_extensions=["pdf"],
                dialog_title="Select PDF Specification File"
            )
        )
        
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("File Selection", size=18, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            ft.Column([excel_btn, self.excel_file_text], tight=True),
                            ft.Column([pdf_btn, self.pdf_file_text], tight=True),
                        ],
                        spacing=20
                    )
                ],
                spacing=10
            ),
            padding=10,
            bgcolor=ft.Colors.GREY_100,
            border_radius=10
        )
    
    def _build_project_section(self) -> ft.Container:
        """Build project information input section."""
        # Project name
        self.project_name_field = ft.TextField(
            label="Project Name",
            hint_text="Enter project name",
            value="",
            on_change=self._on_project_field_change
        )
        
        # Building dimensions
        self.height_field = ft.TextField(
            label="Building Height (ft)",
            hint_text="e.g., 35.0",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_project_field_change
        )
        
        self.area_field = ft.TextField(
            label="Roof Area (sqft)",
            hint_text="e.g., 5000.0",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_project_field_change
        )
        
        self.perimeter_field = ft.TextField(
            label="Perimeter (ft)",
            hint_text="e.g., 280.0",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_project_field_change
        )
        
        # Material and compliance
        self.material_dropdown = ft.Dropdown(
            label="Preferred Material",
            options=[
                ft.dropdown.Option("copper", "Copper"),
                ft.dropdown.Option("aluminum", "Aluminum"),
            ],
            value="copper",
            on_change=self._on_project_field_change
        )
        
        self.compliance_dropdown = ft.Dropdown(
            label="Compliance Standard",
            options=[
                ft.dropdown.Option("UL 96A", "UL 96A"),
                ft.dropdown.Option("NFPA 780", "NFPA 780"),
            ],
            value="UL 96A",
            on_change=self._on_compliance_change
        )
        
        # Options
        self.metal_roof_checkbox = ft.Checkbox(
            label="Has Metal Roof",
            value=False,
            on_change=self._on_project_field_change
        )
        
        self.corners_field = ft.TextField(
            label="Number of Corners",
            value="4",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_project_field_change
        )
        
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Project Information", size=18, weight=ft.FontWeight.BOLD),
                    ft.Row([self.project_name_field], expand=True),
                    ft.Row([
                        self.height_field,
                        self.area_field,
                        self.perimeter_field
                    ], expand=True),
                    ft.Row([
                        self.material_dropdown,
                        self.compliance_dropdown
                    ], expand=True),
                    ft.Row([
                        self.metal_roof_checkbox,
                        self.corners_field
                    ])
                ],
                spacing=10
            ),
            padding=10,
            bgcolor=ft.Colors.GREY_100,
            border_radius=10
        )
    
    def _build_actions_section(self) -> ft.Container:
        """Build action buttons section."""
        self.parse_pdf_btn = ft.ElevatedButton(
            "🔍 Parse PDF",
            on_click=self._parse_pdf,
            disabled=True
        )
        
        self.load_excel_btn = ft.ElevatedButton(
            "📥 Load Excel",
            on_click=self._load_excel,
            disabled=True
        )
        
        self.calculate_btn = ft.ElevatedButton(
            "💰 Calculate Bid",
            on_click=self._calculate_bid,
            disabled=True,
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.GREEN_700
        )
        
        return ft.Container(
            content=ft.Row(
                [
                    self.parse_pdf_btn,
                    self.load_excel_btn,
                    self.calculate_btn
                ],
                spacing=10
            ),
            padding=10
        )
    
    def _build_bid_display(self) -> ft.Container:
        """Build bid results display section."""
        self.bid_summary_text = ft.Text(
            "No bid calculated yet. Load files and click 'Calculate Bid'.",
            size=14,
            color=ft.Colors.GREY
        )
        
        self.bid_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Section")),
                ft.DataColumn(ft.Text("Items"), numeric=True),
                ft.DataColumn(ft.Text("Material Cost"), numeric=True),
                ft.DataColumn(ft.Text("Labor Cost"), numeric=True),
                ft.DataColumn(ft.Text("Total"), numeric=True),
            ],
            rows=[],
            visible=False
        )
        
        self.export_excel_btn = ft.ElevatedButton(
            "📊 Export Excel",
            on_click=self._export_excel,
            disabled=True
        )
        
        self.export_pdf_btn = ft.ElevatedButton(
            "📄 Export PDF",
            on_click=self._export_pdf,
            disabled=True
        )
        
        # Build export buttons row (always include, just disabled initially)
        export_buttons_row = ft.Row([
            self.export_excel_btn,
            self.export_pdf_btn
        ], spacing=10)
        
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Bid Results", size=18, weight=ft.FontWeight.BOLD),
                    self.bid_summary_text,
                    self.bid_table,
                    export_buttons_row
                ],
                spacing=10
            ),
            padding=10,
            bgcolor=ft.Colors.BLUE_50,
            border_radius=10
        )
    
    # Event handlers
    def _on_excel_selected(self, e: ft.FilePickerResultEvent):
        """Handle Excel file selection."""
        if e.files and len(e.files) > 0:
            self.excel_file_path = Path(e.files[0].path)
            self.excel_file_text.value = f"Selected: {e.files[0].name}"
            self.excel_file_text.color = ft.Colors.GREEN
            self.load_excel_btn.disabled = False
            self.page.update()
    
    def _on_pdf_selected(self, e: ft.FilePickerResultEvent):
        """Handle PDF file selection."""
        if e.files and len(e.files) > 0:
            self.pdf_file_path = Path(e.files[0].path)
            self.pdf_file_text.value = f"Selected: {e.files[0].name}"
            self.pdf_file_text.color = ft.Colors.GREEN
            self.parse_pdf_btn.disabled = False
            self.page.update()
    
    def _on_project_field_change(self, e):
        """Handle project field changes."""
        # Update project_data dictionary
        if hasattr(e.control, 'value'):
            field_name = e.control.label.lower().replace(" ", "_")
            if "project name" in e.control.label.lower():
                self.project_data["project_name"] = e.control.value
            elif "height" in e.control.label.lower():
                try:
                    self.project_data["building_height_ft"] = float(e.control.value) if e.control.value else None
                except ValueError:
                    pass
            elif "area" in e.control.label.lower():
                try:
                    self.project_data["roof_area_sqft"] = float(e.control.value) if e.control.value else None
                except ValueError:
                    pass
            elif "perimeter" in e.control.label.lower():
                try:
                    self.project_data["perimeter_ft"] = float(e.control.value) if e.control.value else None
                except ValueError:
                    pass
            elif "corners" in e.control.label.lower():
                try:
                    self.project_data["num_corners"] = int(e.control.value) if e.control.value else 4
                except ValueError:
                    pass
    
    def _on_compliance_change(self, e):
        """Handle compliance standard change."""
        self.compliance_code = e.control.value
        self.project_data["compliance_standard"] = e.control.value
    
    def _parse_pdf(self, e):
        """Parse PDF and extract project data."""
        if not self.pdf_file_path:
            self._show_snackbar("Please select a PDF file first", ft.Colors.RED)
            return
        
        try:
            self.page.splash = ft.ProgressBar()
            self.page.update()
            
            # Extract data from PDF
            extracted_data = extract_project_data(self.pdf_file_path)
            
            # Update project fields with extracted data
            if extracted_data["project_info"]["project_name"]:
                self.project_name_field.value = extracted_data["project_info"]["project_name"]
                self.project_data["project_name"] = extracted_data["project_info"]["project_name"]
            
            dims = extracted_data["building_dimensions"]
            if dims["height"]:
                self.height_field.value = str(dims["height"])
                self.project_data["building_height_ft"] = dims["height"]
            
            if dims["area"]:
                self.area_field.value = str(dims["area"])
                self.project_data["roof_area_sqft"] = dims["area"]
            
            if dims["perimeter"]:
                self.perimeter_field.value = str(dims["perimeter"])
                self.project_data["perimeter_ft"] = dims["perimeter"]
            
            # Material preferences
            mat_prefs = extracted_data["material_preferences"]
            if mat_prefs["preferred_material"]:
                self.material_dropdown.value = mat_prefs["preferred_material"]
                self.project_data["preferred_material"] = mat_prefs["preferred_material"]
            
            if mat_prefs["has_metal_roof"]:
                self.metal_roof_checkbox.value = True
                self.project_data["has_metal_roof"] = True
            
            # Compliance standard
            if extracted_data.get("compliance_standard"):
                self.compliance_code = extracted_data["compliance_standard"]
                self.compliance_dropdown.value = extracted_data["compliance_standard"]
            
            # Update corners
            if extracted_data.get("num_corners"):
                self.corners_field.value = str(extracted_data["num_corners"])
                self.project_data["num_corners"] = extracted_data["num_corners"]
            
            self.page.splash = None
            self._show_snackbar("PDF parsed successfully!", ft.Colors.GREEN)
            self.page.update()
            
        except Exception as ex:
            self.page.splash = None
            self._show_snackbar(f"Error parsing PDF: {str(ex)[:100]}", ft.Colors.RED)
            self.page.update()
    
    def _load_excel(self, e):
        """Load Excel pricing file."""
        if not self.excel_file_path:
            self._show_snackbar("Please select an Excel file first", ft.Colors.RED)
            return
        
        try:
            self.page.splash = ft.ProgressBar()
            self.page.update()
            
            # Load pricing from Excel
            self.price_catalog = load_pricing_from_excel(self.excel_file_path)
            
            self.page.splash = None
            self._show_snackbar(
                f"Loaded {len(self.price_catalog)} pricing items!",
                ft.Colors.GREEN
            )
            
            # Enable calculate button if we have pricing
            if self.price_catalog:
                self.calculate_btn.disabled = False
            
            self.page.update()
            
        except Exception as ex:
            self.page.splash = None
            self._show_snackbar(f"Error loading Excel: {str(ex)[:100]}", ft.Colors.RED)
            self.page.update()
    
    def _calculate_bid(self, e):
        """Calculate bid based on current project data."""
        if not self.price_catalog:
            self._show_snackbar("Please load Excel pricing file first", ft.Colors.RED)
            return
        
        # Validate required fields
        if not self.project_data.get("project_name"):
            self.project_data["project_name"] = "Lightning Protection Project"
        
        if not self.project_data.get("building_height_ft"):
            self.project_data["building_height_ft"] = 35.0
        
        if not self.project_data.get("roof_area_sqft"):
            self.project_data["roof_area_sqft"] = 5000.0
        
        if not self.project_data.get("perimeter_ft"):
            # Estimate from area
            import math
            side_length = math.sqrt(self.project_data["roof_area_sqft"])
            self.project_data["perimeter_ft"] = side_length * 4
        
        try:
            self.page.splash = ft.ProgressBar()
            self.page.update()
            
            # Calculate bid
            calculator = BidCalculator(self.price_catalog, compliance_code=self.compliance_code)
            self.current_bid = calculator.calculate_bid(self.project_data)
            
            # Update display
            self._update_bid_display()
            
            self.page.splash = None
            self._show_snackbar("Bid calculated successfully!", ft.Colors.GREEN)
            self.page.update()
            
        except Exception as ex:
            self.page.splash = None
            self._show_snackbar(f"Error calculating bid: {str(ex)[:100]}", ft.Colors.RED)
            self.page.update()
    
    def _update_bid_display(self):
        """Update the bid display with current bid data."""
        if not self.current_bid:
            return
        
        # Update summary text
        self.bid_summary_text.value = (
            f"Project: {self.current_bid.project_name}\n"
            f"Subtotal: ${self.current_bid.subtotal:,.2f}\n"
            f"Total with Markup: ${self.current_bid.total_with_markup:,.2f}\n"
            f"FINAL BID AMOUNT: ${self.current_bid.final_bid_amount:,.2f}"
        )
        self.bid_summary_text.color = ft.Colors.BLACK
        self.bid_summary_text.size = 14
        self.bid_summary_text.weight = ft.FontWeight.BOLD
        
        # Update table
        self.bid_table.rows = []
        for section in self.current_bid.sections:
            self.bid_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(section.name)),
                        ft.DataCell(ft.Text(str(len(section.line_items)))),
                        ft.DataCell(ft.Text(f"${section.total_material:,.2f}")),
                        ft.DataCell(ft.Text(f"${section.total_labor:,.2f}")),
                        ft.DataCell(ft.Text(f"${section.section_total:,.2f}")),
                    ]
                )
            )
        
        self.bid_table.visible = True
        self.export_excel_btn.disabled = False
        self.export_pdf_btn.disabled = False
    
    def _export_excel(self, e):
        """Export bid to Excel."""
        if not self.current_bid:
            return
        
        try:
            excel_exporter = ExcelBidExporter()
            excel_output = self.output_dir / f"bid_{self.current_bid.project_name.replace(' ', '_')}.xlsx"
            excel_exporter.export_bid(self.current_bid, excel_output)
            self._show_snackbar(f"Excel exported to: {excel_output.name}", ft.Colors.GREEN)
        except Exception as ex:
            self._show_snackbar(f"Error exporting Excel: {str(ex)[:100]}", ft.Colors.RED)
    
    def _export_pdf(self, e):
        """Export bid to PDF."""
        if not self.current_bid:
            return
        
        try:
            pdf_exporter = PDFSubmittalExporter(
                contractor_name="ABC Lightning Protection Co.",
                contractor_info={
                    "address": "123 Main St, Your City, ST 12345",
                    "phone": "(555) 123-4567",
                    "email": "info@abclightning.com",
                    "license": "LP-12345"
                }
            )
            pdf_output = self.output_dir / f"submittal_{self.current_bid.project_name.replace(' ', '_')}.pdf"
            pdf_exporter.export_submittal(self.current_bid, pdf_output, self.compliance_code)
            self._show_snackbar(f"PDF exported to: {pdf_output.name}", ft.Colors.GREEN)
        except Exception as ex:
            self._show_snackbar(f"Error exporting PDF: {str(ex)[:100]}", ft.Colors.RED)
    
    def _show_snackbar(self, message: str, color):
        """Show a snackbar notification."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color
        )
        self.page.snack_bar.open = True
        self.page.update()


def main(page: ft.Page):
    """Main entry point for Flet application."""
    app = LightningBidApp(page)


if __name__ == "__main__":
    ft.app(target=main)


