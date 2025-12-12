"""
Main Flet GUI Window for LightningBid

This is the primary GUI interface that orchestrates the entire
bidding workflow through a user-friendly graphical interface.
"""

import flet as ft
from pathlib import Path
from typing import Optional, Dict, Any
# FIX: Explicitly import all constant classes (Colors, FontWeight, etc.)
from flet import Colors, ThemeMode, FontWeight, ScrollMode, MainAxisAlignment, CrossAxisAlignment
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database.db_connector import DBConnector 
from src.gui.login_screen import LoginScreen, create_login_view 
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
        # FIX: Use imported ThemeMode
        self.page.theme_mode = ThemeMode.LIGHT 
        self.page.window.width = 1200
        self.page.window.height = 800
        self.page.window.min_width = 1000
        self.page.window.min_height = 600
        
        # --- NEW: DB and Authentication State ---
        self.db = self._initialize_db()
        self.current_user_id: Optional[int] = None
        # ----------------------------------------
        
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
        
        # --- NEW CODE: Initialize Global Dialog for Feedback ---
        self.feedback_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Notice"),
            content=ft.Text(""),
            actions=[
                ft.TextButton("OK", on_click=self._close_feedback_dialog),
            ],
            # FIX: Use imported MainAxisAlignment
            actions_alignment=MainAxisAlignment.END, 
        )
        self.page.overlay.append(self.feedback_dialog)
        # ----------------------------------------------------

        self._show_login_screen()

    # --- NEW METHOD: DB INITIALIZATION ---
    def _initialize_db(self) -> Optional[DBConnector]:
        """Initializes and returns the database connector."""
        try:
            connector = DBConnector()
            print("Database connection successful.")
            return connector
        except Exception as e:
            # FIX: Use imported Colors
            self._show_feedback_dialog(f"Fatal DB Error: {e}", Colors.RED) 
            return None 

    # --- NEW METHOD: SHOW LOGIN SCREEN ---
    def _show_login_screen(self):
        """Switches the page content to the login view."""
        login_view = create_login_view(
            on_login_submit=self._handle_login_attempt,
            on_create_account_click=self._handle_create_account 
        )
        self.page.views.clear()
        self.page.views.append(login_view)
        self.page.update()

    # --- NEW METHOD: LOGIN HANDLER ---
    def _handle_login_attempt(self, username: str, password: str):
        """
        Handles the sign-in button click by checking credentials against the DB (DEMO MODE).
        """
        if not username or not password:
            # FIX: Use imported Colors
            self._show_feedback_dialog("Please enter both username and password.", Colors.AMBER_600)
            return
            
        if self.db is None:
            # FIX: Use imported Colors
            self._show_feedback_dialog("Database connection failed. Cannot log in.", Colors.RED)
            return

        # 1. Fetch user data by username
        user_data = self.db.get_user_by_username(username)

        if user_data:
            user_id, stored_username, stored_password = user_data 
            
            # 2. DEMO VERIFICATION: Use the DEMO function from auth_utils
            from src.database.auth_utils import verify_password
            
            if verify_password(password, stored_password):
                # FIX: Use imported Colors
                self._show_feedback_dialog(f"Login successful for {stored_username}!", Colors.GREEN_700)
                self.current_user_id = user_id 
                self._build_main_ui() 
                return

        # If user not found OR password verification failed:
        # FIX: Use imported Colors
        self._show_feedback_dialog("Login failed: Invalid username or password.", Colors.RED_700)

    def _handle_create_account(self, username: str, password: str, email: str):
        """Handles the user registration process (DEMO MODE)."""
        if not username or not password or not email:
            # FIX: Use imported Colors
            self._show_feedback_dialog("Please fill out all fields: Username, Password, and Email.", Colors.AMBER_600)
            return
            
        if self.db is None:
            # FIX: Use imported Colors
            self._show_feedback_dialog("Database connection failed. Cannot create account.", Colors.RED)
            return

        # Use the DEMO Hashing function
        from src.database.auth_utils import hash_password
        
        hashed_pw = hash_password(password) 
        
        user_id = self.db.create_user(username, email, hashed_pw)
        
        if user_id:
            # FIX: Use imported Colors
            self._show_feedback_dialog(f"Account for '{username}' created successfully!", Colors.GREEN_700)
        else:
            # FIX: Use imported Colors
            self._show_feedback_dialog(f"Account creation failed: Username or Email already exists.", Colors.RED_700)

    # --- MODIFIED/RENAMED METHOD: Original _build_ui is now _build_main_ui ---
    def _build_main_ui(self):
        """Build the main user interface and display it."""
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
        self.page.overlay.append(self.excel_save_picker)
        self.page.overlay.append(self.pdf_save_picker)
        
        # Layout
        main_view_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "LightningBid - Lightning Protection Bidding System",
                        size=24,
                        # FIX: Use imported FontWeight
                        weight=FontWeight.BOLD,
                        # FIX: Use imported Colors
                        color=Colors.BLUE_700
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
                # FIX: Use imported ScrollMode
                scroll=ScrollMode.AUTO,
                spacing=15
            ),
            padding=20,
            expand=True
        )
        
        # NEW: Create a new View and update the page
        main_view = ft.View(
            "/",
            [
                main_view_content
            ],
            # FIX: Use imported MainAxisAlignment
            vertical_alignment=MainAxisAlignment.START 
        )
        self.page.views.clear()
        self.page.views.append(main_view)
        self.page.update()

    # The rest of the class methods have their internal constant usages fixed below.
    
    def _build_file_section(self) -> ft.Container:
        """Build file selection section."""
        # Excel file picker (for input)
        self.excel_file_picker = ft.FilePicker(
            on_result=self._on_excel_selected
        )
        
        # Excel save picker (for export)
        self.excel_save_picker = ft.FilePicker(
            on_result=self._on_excel_save_selected
        )
        
        # PDF save picker (for export)
        self.pdf_save_picker = ft.FilePicker(
            on_result=self._on_pdf_save_selected
        )
        
        self.excel_file_text = ft.Text(
            "No Excel file selected",
            size=12,
            # FIX: Use imported Colors
            color=Colors.GREY
        )
        
        excel_btn = ft.ElevatedButton(
            "📊 Select Excel Pricing File",
            on_click=lambda _: self.excel_file_picker.pick_files(
                allowed_extensions=["xlsx", "xls"],
                dialog_title="Select Excel Pricing File"
            )
        )
        
        # PDF file picker (for input)
        self.pdf_file_picker = ft.FilePicker(
            on_result=self._on_pdf_selected
        )
        
        self.pdf_file_text = ft.Text(
            "No PDF file selected",
            size=12,
            # FIX: Use imported Colors
            color=Colors.GREY
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
                    ft.Text("File Selection", size=18, weight=FontWeight.BOLD),
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
            # FIX: Use imported Colors
            bgcolor=Colors.GREY_100,
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
                    ft.Text("Project Information", size=18, weight=FontWeight.BOLD),
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
            # FIX: Use imported Colors
            bgcolor=Colors.GREY_100,
            border_radius=10
        )
    
    def _build_actions_section(self) -> ft.Container:
        """Build action buttons section."""
        self.parse_pdf_btn = ft.ElevatedButton(
            "📄 Parse PDF",
            on_click=self._parse_pdf,
            disabled=False
        )
        
        self.load_excel_btn = ft.ElevatedButton(
            "📥 Load Excel",
            on_click=self._load_excel,
            disabled=False
        )
        
        self.calculate_btn = ft.ElevatedButton(
            "💰 Calculate Bid",
            on_click=self._calculate_bid,
            disabled=True,
            color=Colors.WHITE,
            bgcolor=Colors.GREEN_700
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
            color=Colors.GREY
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
                    ft.Text("Bid Results", size=18, weight=FontWeight.BOLD),
                    self.bid_summary_text,
                    self.bid_table,
                    export_buttons_row
                ],
                spacing=10
            ),
            padding=10,
            bgcolor=Colors.BLUE_50,
            border_radius=10
        )
    
    # Event handlers
    def _on_excel_selected(self, e: ft.FilePickerResultEvent):
        """Handle Excel file selection."""
        try:
            if e.files and len(e.files) > 0:
                file_path = e.files[0].path
                self.excel_file_path = Path(file_path)
                self.excel_file_text.value = f"Selected: {e.files[0].name}"
                self.excel_file_text.color = Colors.GREEN
                self.load_excel_btn.disabled = False
                self.page.update()
        except Exception as ex:
            self._show_feedback_dialog(f"Error selecting file: {str(ex)}", Colors.RED)
    
    def _on_pdf_selected(self, e: ft.FilePickerResultEvent):
        """Handle PDF file selection."""
        try:
            if e.files and len(e.files) > 0:
                file_path = e.files[0].path
                self.pdf_file_path = Path(file_path)
                self.pdf_file_text.value = f"Selected: {e.files[0].name}"
                self.pdf_file_text.color = Colors.GREEN
                self.parse_pdf_btn.disabled = False
                self.page.update()
        except Exception as ex:
            self._show_feedback_dialog(f"Error selecting file: {str(ex)}", Colors.RED)
    
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
        if not self.pdf_file_path or not self.pdf_file_path.exists():
            self._show_feedback_dialog("Please select a PDF file first", Colors.RED)
            return
        
        try:
            self.page.splash = ft.ProgressBar()
            self.page.update()
            
            print(f"DEBUG: Parsing PDF at {self.pdf_file_path}")
            
            # Extract data from PDF
            extracted_data = extract_project_data(self.pdf_file_path)
            print(f"DEBUG: PDF parsed, extracted data keys: {list(extracted_data.keys())}")  # Debug output
            
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
            self._show_feedback_dialog("PDF parsed successfully!", Colors.GREEN)
            self.page.update()
            
        except Exception as ex:
            import traceback
            error_msg = str(ex)
            print(f"DEBUG ERROR: {error_msg}")  # Debug output
            print(traceback.format_exc())  # Full traceback
            self.page.splash = None
            self._show_feedback_dialog(f"Error parsing PDF: {str(ex)[:100]}", Colors.RED)
            self.page.update()
    
    def _load_excel(self, e):
        """Load Excel pricing file."""
        if not self.excel_file_path or not self.excel_file_path.exists():
            self._show_feedback_dialog("Please select an Excel file first", Colors.RED)
            return
        
        try:
            self.page.splash = ft.ProgressBar()
            self.page.update()
            
            print(f"DEBUG: Loading Excel at {self.excel_file_path}")
            
            # Load pricing from Excel
            self.price_catalog = load_pricing_from_excel(self.excel_file_path)
            
            print(f"DEBUG: Loaded {len(self.price_catalog)} items")
            
            self.page.splash = None
            self._show_feedback_dialog(
                f"Loaded {len(self.price_catalog)} pricing items!",
                Colors.GREEN
            )
            
            # Enable calculate button if we have pricing
            if self.price_catalog:
                self.calculate_btn.disabled = False
                print(f"DEBUG: Calculate button enabled")  # Debug output
            
            self.page.update()
            
        except Exception as ex:
            import traceback
            error_msg = str(ex)
            print(f"DEBUG ERROR: {error_msg}")  # Debug output
            print(traceback.format_exc())  # Full traceback
            self.page.splash = None
            self._show_feedback_dialog(f"Error loading Excel: {str(ex)[:100]}", Colors.RED)
            self.page.update()
    
    def _calculate_bid(self, e):
        """Calculate bid based on current project data."""
        if not self.price_catalog:
            self._show_feedback_dialog("Please load Excel pricing file first", Colors.RED)
            return
        
        print(f"DEBUG: Calculating bid with {len(self.price_catalog)} items")
        
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
            
            print(f"DEBUG: Project data: {self.project_data}")  # Debug output
            
            # Calculate bid
            calculator = BidCalculator(self.price_catalog, compliance_code=self.compliance_code)
            self.current_bid = calculator.calculate_bid(self.project_data)
            
            print(f"DEBUG: Bid calculated, sections: {len(self.current_bid.sections)}")  # Debug output
            print(f"DEBUG: Final bid amount: ${self.current_bid.final_bid_amount:,.2f}")  # Debug output
            
            # Update display
            self._update_bid_display()
            
            self.page.splash = None
            self._show_feedback_dialog("Bid calculated successfully!", Colors.GREEN)
            self.page.update()
            
        except Exception as ex:
            import traceback
            error_msg = str(ex)
            print(f"DEBUG ERROR: {error_msg}")  # Debug output
            print(traceback.format_exc())  # Full traceback
            self.page.splash = None
            self._show_feedback_dialog(f"Error calculating bid: {str(ex)[:100]}", Colors.RED)
            self.page.update()
    
    def _update_bid_display(self):
        """Update the bid display with current bid data."""
        if not self.current_bid:
            print("DEBUG: No bid to display")
            return
        
        print(f"DEBUG: Updating bid display for {self.current_bid.project_name}")  # Debug output
        
        # Update summary text
        self.bid_summary_text.value = (
            f"Project: {self.current_bid.project_name}\n"
            f"Subtotal: ${self.current_bid.subtotal:,.2f}\n"
            f"Total with Markup: ${self.current_bid.total_with_markup:,.2f}\n"
            f"FINAL BID AMOUNT: ${self.current_bid.final_bid_amount:,.2f}"
        )
        self.bid_summary_text.color = Colors.BLACK
        self.bid_summary_text.size = 14
        self.bid_summary_text.weight = FontWeight.BOLD
        
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
        
        print(f"DEBUG: Bid display updated, table visible: {self.bid_table.visible}")  # Debug output
        self.page.update()  # Make sure to update the page after changing display
    
    def _export_excel(self, e):
        """Export bid to Excel - opens save dialog."""
        if not self.current_bid:
            self._show_snackbar("Please calculate a bid first", ft.Colors.RED)
            return
        
        try:
            excel_exporter = ExcelBidExporter()
            excel_output = self.output_dir / f"bid_{self.current_bid.project_name.replace(' ', '_')}.xlsx"
            excel_exporter.export_bid(self.current_bid, excel_output)
            self._show_feedback_dialog(f"Excel exported to: {excel_output.name}", Colors.GREEN)
        except Exception as ex:
            self._show_feedback_dialog(f"Error exporting Excel: {str(ex)[:100]}", Colors.RED)
    
    def _export_pdf(self, e):
        """Export bid to PDF - opens save dialog."""
        if not self.current_bid:
            self._show_snackbar("Please calculate a bid first", ft.Colors.RED)
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
            self._show_feedback_dialog(f"PDF exported to: {pdf_output.name}", Colors.GREEN)
        except Exception as ex:
            self._show_feedback_dialog(f"Error exporting PDF: {str(ex)[:100]}", Colors.RED)
    
    # --- NEW FEEDBACK METHODS (Replaces _show_snackbar) ---
    def _close_feedback_dialog(self, e):
        """Closes the generic feedback dialog."""
        self.feedback_dialog.open = False
        self.page.update()

    def _show_feedback_dialog(self, message: str, color, title: str = "Notice"):
        """Show a persistent AlertDialog notification instead of a Snackbar."""
        # Update content and style
        self.feedback_dialog.title.value = title
        self.feedback_dialog.content.value = message
        self.feedback_dialog.content.color = color
        
        # Open the dialog
        self.feedback_dialog.open = True
        self.page.update()


def main(page: ft.Page):
    """Main entry point for Flet application."""
    app = LightningBidApp(page)


if __name__ == "__main__":
    ft.app(target=main)