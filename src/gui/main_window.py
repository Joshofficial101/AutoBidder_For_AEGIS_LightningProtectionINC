"""
Main Flet GUI Window for LightningBid

This is the primary GUI interface that orchestrates the entire
bidding workflow through a user-friendly graphical interface.
"""

import flet as ft
from pathlib import Path
from typing import Optional, Dict, Any
# FIX: Explicitly import all constant classes for Windows compatibility
from flet import Colors, ThemeMode, FontWeight, ScrollMode, MainAxisAlignment, CrossAxisAlignment
import sys
import tkinter as tk
from tkinter import filedialog

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
from src.validators.js_validator import DimensionValidator


class LightningBidApp:
    """
    Main application class for LightningBid GUI.
    
    This class manages the entire GUI state and workflow.
    """
    
    def __init__(self, page: ft.Page):
        """Initialize the application."""
        self.page = page
        self.page.title = "Lightning Protection Bidding System"
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
        
        # Labor settings - worker-based system (each worker has their own hours)
        self.workers = [
            {"name": "Worker 1", "wage_per_hour": 25.0, "hours": 40.0}  # Default worker
        ]
        
        # Pricing settings (configurable percentages and additional costs)
        self.labor_markup_pct = 20.0      # Labor markup percentage
        self.overhead_pct = 10.0          # Overhead percentage
        self.profit_pct = 10.0            # Profit percentage
        self.commission_amount = 0.0      # Commission (flat amount)
        self.tools_rental_amount = 0.0    # Tools & rental (flat amount or percentage)
        self.tools_rental_type = "$"      # Tools & rental type: "$" or "%"
        self.use_tax_pct = 0.0            # Use tax percentage (applied to materials + shipping)
        self.shipping_amount = 0.0        # Shipping cost (flat amount)
        
        # Validation state tracking
        self.validation_errors = {
            "height": False,
            "area": False,
            "perimeter": False
        }
        
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
        
        # --- NEW: Initialize JavaScript Validator ---
        try:
            self.dimension_validator = DimensionValidator()
        except Exception as e:
            print(f"Warning: Could not initialize dimension validator: {e}")
            self.dimension_validator = None
        # --------------------------------------------

        self._show_login_screen()

    # --- DB INITIALIZATION ---
    def _initialize_db(self) -> Optional[DBConnector]:
        """Initializes and returns the database connector."""
        try:
            connector = DBConnector()
            print("Database connection successful.")
            return connector
        except Exception as e:
            
            self._show_feedback_dialog(f"Fatal DB Error: {e}", Colors.RED) 
            return None 

    # --- SHOW LOGIN SCREEN ---
    def _show_login_screen(self):
        """Switches the page content to the login view."""
        login_view = create_login_view(
            on_login_submit=self._handle_login_attempt,
            on_create_account_click=self._handle_create_account 
        )
        self.page.views.clear()
        self.page.views.append(login_view)
        self.page.update()

    # --- LOGIN HANDLER ---
    def _handle_login_attempt(self, username: str, password: str):
        """
        Handles the sign-in button click by checking credentials against the DB (DEMO MODE).
        """
        if not username or not password:
            
            self._show_feedback_dialog("Please enter both username and password.", Colors.AMBER_600)
            return
            
        if self.db is None:
            
            self._show_feedback_dialog("Database connection failed. Cannot log in.", Colors.RED)
            return

        # 1. Fetch user data by username
        user_data = self.db.get_user_by_username(username)

        if user_data:
            user_id, stored_username, stored_password = user_data 
            
            # 2. DEMO VERIFICATION: Use the DEMO function from auth_utils
            from src.database.auth_utils import verify_password
            
            if verify_password(password, stored_password):
                
                self._show_feedback_dialog(f"Login successful for {stored_username}!", Colors.GREEN_700)
                self.current_user_id = user_id 
                self._build_main_ui() 
                return

        # If user not found OR password verification failed:
        self._show_feedback_dialog("Login failed: Invalid username or password.", Colors.RED_700)

    def _handle_create_account(self, username: str, password: str, email: str):
        """Handles the user registration process (DEMO MODE)."""
        if not username or not password or not email:
            
            self._show_feedback_dialog("Please fill out all fields: Username, Password, and Email.", Colors.AMBER_600)
            return
            
        if self.db is None:
            
            self._show_feedback_dialog("Database connection failed. Cannot create account.", Colors.RED)
            return

        # Use the DEMO Hashing function
        from src.database.auth_utils import hash_password
        
        hashed_pw = hash_password(password) 
        
        user_id = self.db.create_user(username, email, hashed_pw)
        
        if user_id:
            
            self._show_feedback_dialog(f"Account for '{username}' created successfully!", Colors.GREEN_700)
        else:
            
            self._show_feedback_dialog(f"Account creation failed: Username or Email already exists.", Colors.RED_700)

    # --- BUILD MAIN UI ---
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
        
        # The file pickers for saving were introduced in the merged code:
        self.page.overlay.append(self.excel_save_picker)
        self.page.overlay.append(self.pdf_save_picker)
        
        # Debug: Verify file pickers are in overlay
        print(f"DEBUG: File pickers in overlay: excel_save={self.excel_save_picker in self.page.overlay}, pdf_save={self.pdf_save_picker in self.page.overlay}")
        self.page.update()
        
        # Layout
        main_view_content = ft.Container( 
            content=ft.Column(
                [
                    ft.Text(
                        "Lightning Protection Bidding System",
                        size=24,
                        weight=FontWeight.BOLD,
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
            vertical_alignment=MainAxisAlignment.START 
        )
        self.page.views.clear()
        self.page.views.append(main_view)
        self.page.update()

    # --- UI COMPONENT BUILDERS ---
    
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
        
        # Building dimensions with validation
        self.height_field = ft.TextField(
            label="Building Height (ft)",
            hint_text="e.g., 35.0",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_project_field_change
        )
        
        self.height_error = ft.Text(
            "",
            size=12,
            color=Colors.RED,
            visible=False
        )
        
        self.area_field = ft.TextField(
            label="Roof Area (sqft)",
            hint_text="e.g., 5000.0",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_project_field_change
        )
        
        self.area_error = ft.Text(
            "",
            size=12,
            color=Colors.RED,
            visible=False
        )
        
        self.perimeter_field = ft.TextField(
            label="Perimeter (ft)",
            hint_text="e.g., 280.0",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_project_field_change
        )
        
        self.perimeter_error = ft.Text(
            "",
            size=12,
            color=Colors.RED,
            visible=False
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
        
        # Compliance display (read-only - always uses both standards)
        self.compliance_display = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.VERIFIED_USER, color=Colors.GREEN_700, size=20),
                ft.Text(
                    "UL 96A + NFPA 780 (Comprehensive)",
                    size=14,
                    weight=FontWeight.BOLD,
                    color=Colors.GREEN_700
                )
            ], spacing=8),
            padding=10,
            bgcolor=Colors.GREEN_50,
            border_radius=5
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
                        ft.Column([
                            self.height_field,
                            self.height_error
                        ], spacing=2, expand=True),
                        ft.Column([
                            self.area_field,
                            self.area_error
                        ], spacing=2, expand=True),
                        ft.Column([
                            self.perimeter_field,
                            self.perimeter_error
                        ], spacing=2, expand=True)
                    ], expand=True),
                    ft.Row([
                        self.material_dropdown,
                        self.compliance_display
                    ], expand=True),
                    ft.Row([
                        self.metal_roof_checkbox,
                        self.corners_field
                    ])
                ],
                spacing=10
            ),
            padding=10,
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
        
        self.labor_settings_btn = ft.ElevatedButton(
            "⚙️ Bid Settings",
            on_click=self._show_labor_settings_dialog,
            disabled=False,
            color=Colors.WHITE,
            bgcolor=Colors.BLUE_700
        )
        
        return ft.Container(
            content=            ft.Row(
                [
                    self.parse_pdf_btn,
                    self.load_excel_btn,
                    self.labor_settings_btn,
                    self.calculate_btn
                ],
                spacing=10
            ),
            padding=10
        )
    
    def _build_bid_display(self) -> ft.Container:
        """Build bid results display section."""
        
        # The export buttons must be updated to trigger the save file dialog
        # The updated handler logic is inside the on_click lambda below.
        
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
        
        # FIX: Update on_click to trigger the save file dialog
        self.export_excel_btn = ft.ElevatedButton(
            "📊 Export Excel",
            on_click=self._trigger_excel_save_dialog,
            disabled=True
        )
        
        # FIX: Update on_click to trigger the save file dialog
        self.export_pdf_btn = ft.ElevatedButton(
            "📄 Export PDF",
            on_click=self._trigger_pdf_save_dialog,
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
    
    # --- EVENT HANDLERS ---
    
    # File Input Handlers
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

    # --- FIX: MISSING SAVE HANDLER METHODS (Introduced by the merge) ---
    def _trigger_excel_save_dialog(self, e):
        """Trigger the Excel save file dialog with the current bid's project name."""
        try:
            print("DEBUG: Excel save dialog triggered")
            
            if self.current_bid:
                # Clean filename - remove invalid characters
                clean_name = "".join(c for c in self.current_bid.project_name if c.isalnum() or c in (' ', '-', '_')).strip()
                clean_name = clean_name.replace(' ', '_')
                file_name = f"bid_{clean_name}.xlsx"
            else:
                file_name = "bid_output.xlsx"
            
            # Try Flet's file picker first
            try:
                if self.excel_save_picker and self.excel_save_picker in self.page.overlay:
                    print(f"DEBUG: Trying Flet FilePicker with filename: {file_name}")
                    self.excel_save_picker.save_file(
                        allowed_extensions=["xlsx"],
                        file_name=file_name,
                        dialog_title="Save Excel Bid File"
                    )
                    self.page.update()
                    print("DEBUG: Flet save_file() called")
                    # Wait a moment to see if dialog appears
                    import time
                    time.sleep(0.1)
                    return
            except Exception as flet_ex:
                print(f"DEBUG: Flet FilePicker failed: {flet_ex}")
            
            # Fallback to tkinter file dialog (more reliable on Windows)
            print("DEBUG: Using tkinter fallback for file save")
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.attributes('-topmost', True)  # Bring dialog to front
            
            file_path = filedialog.asksaveasfilename(
                title="Save Excel Bid File",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialfile=file_name
            )
            
            root.destroy()
            
            if file_path:
                # Ensure the file path has .xlsx extension
                file_path_obj = Path(file_path)
                if file_path_obj.suffix.lower() != '.xlsx':
                    file_path = str(file_path_obj.with_suffix('.xlsx'))
                    print(f"DEBUG: Added .xlsx extension to path: {file_path}")
                
                print(f"DEBUG: User selected path: {file_path}")
                self._export_excel(file_path)
            else:
                print("DEBUG: User canceled file save")
                self._show_feedback_dialog("Excel export canceled.", Colors.AMBER_300)
                
        except Exception as ex:
            print(f"ERROR in _trigger_excel_save_dialog: {ex}")
            import traceback
            traceback.print_exc()
            self._show_feedback_dialog(f"Error opening save dialog: {str(ex)[:100]}", Colors.RED)
    
    def _trigger_pdf_save_dialog(self, e):
        """Trigger the PDF save file dialog with the current bid's project name."""
        try:
            print("DEBUG: PDF save dialog triggered")
            
            if self.current_bid:
                # Clean filename - remove invalid characters
                clean_name = "".join(c for c in self.current_bid.project_name if c.isalnum() or c in (' ', '-', '_')).strip()
                clean_name = clean_name.replace(' ', '_')
                file_name = f"submittal_{clean_name}.pdf"
            else:
                file_name = "submittal_output.pdf"
            
            # Try Flet's file picker first
            try:
                if self.pdf_save_picker and self.pdf_save_picker in self.page.overlay:
                    print(f"DEBUG: Trying Flet FilePicker with filename: {file_name}")
                    self.pdf_save_picker.save_file(
                        allowed_extensions=["pdf"],
                        file_name=file_name,
                        dialog_title="Save PDF Submittal File"
                    )
                    self.page.update()
                    print("DEBUG: Flet save_file() called")
                    # Wait a moment to see if dialog appears
                    import time
                    time.sleep(0.1)
                    return
            except Exception as flet_ex:
                print(f"DEBUG: Flet FilePicker failed: {flet_ex}")
            
            # Fallback to tkinter file dialog (more reliable on Windows)
            print("DEBUG: Using tkinter fallback for file save")
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.attributes('-topmost', True)  # Bring dialog to front
            
            file_path = filedialog.asksaveasfilename(
                title="Save PDF Submittal File",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=file_name
            )
            
            root.destroy()
            
            if file_path:
                # Ensure the file path has .pdf extension
                file_path_obj = Path(file_path)
                if file_path_obj.suffix.lower() != '.pdf':
                    file_path = str(file_path_obj.with_suffix('.pdf'))
                    print(f"DEBUG: Added .pdf extension to path: {file_path}")
                
                print(f"DEBUG: User selected path: {file_path}")
                self._export_pdf(file_path)
            else:
                print("DEBUG: User canceled file save")
                self._show_feedback_dialog("PDF export canceled.", Colors.AMBER_300)
                
        except Exception as ex:
            print(f"ERROR in _trigger_pdf_save_dialog: {ex}")
            import traceback
            traceback.print_exc()
            self._show_feedback_dialog(f"Error opening save dialog: {str(ex)[:100]}", Colors.RED)
    
    def _on_excel_save_selected(self, e: ft.FilePickerResultEvent):
        """Handler for the Excel save dialog result."""
        # This resolves the AttributeError seen during the merge.
        if e.path:
            self._export_excel(e.path)
        else:
            self._show_feedback_dialog("Excel export canceled.", Colors.AMBER_300)

    def _on_pdf_save_selected(self, e: ft.FilePickerResultEvent):
        """Handler for the PDF save dialog result."""
        # This resolves the AttributeError seen during the merge.
        if e.path:
            self._export_pdf(e.path)
        else:
            self._show_feedback_dialog("PDF export canceled.", Colors.AMBER_300)
    # ---------------------------------------------------------------------
    
    def _on_project_field_change(self, e):
        """Handle project field changes with real-time validation."""
        # Update project_data dictionary
        if hasattr(e.control, 'value'):
            field_name = e.control.label.lower().replace(" ", "_")
            if "project name" in e.control.label.lower():
                self.project_data["project_name"] = e.control.value
            elif "preferred material" in e.control.label.lower():
                self.project_data["preferred_material"] = e.control.value
            elif "metal roof" in e.control.label.lower():
                self.project_data["has_metal_roof"] = bool(e.control.value)
            elif "height" in e.control.label.lower():
                # Real-time validation for height
                self._validate_dimension_field(
                    e.control.value,
                    "height",
                    self.height_field,
                    self.height_error,
                    "building_height_ft"
                )
            elif "area" in e.control.label.lower():
                # Real-time validation for area
                self._validate_dimension_field(
                    e.control.value,
                    "area",
                    self.area_field,
                    self.area_error,
                    "roof_area_sqft"
                )
            elif "perimeter" in e.control.label.lower():
                # Real-time validation for perimeter
                self._validate_dimension_field(
                    e.control.value,
                    "perimeter",
                    self.perimeter_field,
                    self.perimeter_error,
                    "perimeter_ft"
                )
            elif "corners" in e.control.label.lower():
                try:
                    self.project_data["num_corners"] = int(e.control.value) if e.control.value else 4
                except ValueError:
                    pass
    
    def _validate_dimension_field(self, value: str, field_type: str, 
                                   field_control: ft.TextField, 
                                   error_control: ft.Text,
                                   data_key: str):
        """
        Validate a dimension field using JavaScript validator and update UI.
        
        Args:
            value: The input value to validate
            field_type: Type of field ("height", "area", "perimeter")
            field_control: The TextField control to update
            error_control: The error message Text control
            data_key: Key in project_data to update
        """
        if self.dimension_validator is None:
            # Fallback if validator not available - just try to parse
            try:
                if value:
                    self.project_data[data_key] = float(value)
                else:
                    self.project_data[data_key] = None
            except ValueError:
                pass
            return
        
        # Get validation result from JavaScript
        if field_type == "height":
            result = self.dimension_validator.validate_height(value)
        elif field_type == "area":
            result = self.dimension_validator.validate_area(value)
        elif field_type == "perimeter":
            result = self.dimension_validator.validate_perimeter(value)
        else:
            return
        
        # Update UI based on validation result
        if result["valid"]:
            # Valid input - clear error, reset border color
            field_control.border_color = None
            error_control.visible = False
            error_control.value = ""
            self.validation_errors[field_type] = False
            
            # Update project data if value is not empty
            if value:
                try:
                    self.project_data[data_key] = float(value)
                except ValueError:
                    self.project_data[data_key] = None
            else:
                self.project_data[data_key] = None
        else:
            # Invalid input - show error, set red border
            field_control.border_color = Colors.RED
            error_control.value = result["error"]
            error_control.visible = True
            self.validation_errors[field_type] = True
            
            # Don't update project_data for invalid input
            # Keep previous valid value if any
        
        # Update the controls
        field_control.update()
        error_control.update()
        
        # Update Calculate Bid button state based on validation
        self._update_calculate_button_state()
    
    # Compliance is now always DUAL - no need for change handler
    
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
            
            # Update project fields with extracted data
            if extracted_data["project_info"]["project_name"]:
                self.project_name_field.value = extracted_data["project_info"]["project_name"]
                self.project_data["project_name"] = extracted_data["project_info"]["project_name"]
            
            dims = extracted_data["building_dimensions"]
            if dims["height"]:
                self.height_field.value = str(dims["height"])
                # Trigger validation when field is populated from PDF
                self._validate_dimension_field(
                    str(dims["height"]),
                    "height",
                    self.height_field,
                    self.height_error,
                    "building_height_ft"
                )
            
            if dims["area"]:
                self.area_field.value = str(dims["area"])
                # Trigger validation when field is populated from PDF
                self._validate_dimension_field(
                    str(dims["area"]),
                    "area",
                    self.area_field,
                    self.area_error,
                    "roof_area_sqft"
                )
            
            if dims["perimeter"]:
                self.perimeter_field.value = str(dims["perimeter"])
                # Trigger validation when field is populated from PDF
                self._validate_dimension_field(
                    str(dims["perimeter"]),
                    "perimeter",
                    self.perimeter_field,
                    self.perimeter_error,
                    "perimeter_ft"
                )
            
            # Material preferences
            mat_prefs = extracted_data["material_preferences"]
            if mat_prefs["preferred_material"]:
                self.material_dropdown.value = mat_prefs["preferred_material"]
                self.project_data["preferred_material"] = mat_prefs["preferred_material"]
            
            if mat_prefs["has_metal_roof"]:
                self.metal_roof_checkbox.value = True
                self.project_data["has_metal_roof"] = True
            
            # Compliance standard (now always using DUAL - UL 96A + NFPA 780)
            # No need to set since we always use both standards now
            
            # Update corners
            if extracted_data.get("num_corners"):
                self.corners_field.value = str(extracted_data["num_corners"])
                self.project_data["num_corners"] = extracted_data["num_corners"]
            
            self.page.splash = None
            self._show_feedback_dialog("PDF parsed successfully!", Colors.GREEN)
            self.page.update()
            
        except Exception as ex:
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
            
            # Update calculate button state (checks both pricing and validation)
            self._update_calculate_button_state()
            
            self.page.update()
            
        except Exception as ex:
            self.page.splash = None
            self._show_feedback_dialog(f"Error loading Excel: {str(ex)[:100]}", Colors.RED)
            self.page.update()
    
    def _update_calculate_button_state(self):
        """Update the Calculate Bid button state based on validation errors."""
        if hasattr(self, 'calculate_btn'):
            # Disable button if any field has validation errors
            has_errors = any(self.validation_errors.values())
            # Also check if pricing is loaded
            has_pricing = len(self.price_catalog) > 0
            self.calculate_btn.disabled = has_errors or not has_pricing
            self.calculate_btn.update()
    
    def _apply_worker_labor_costs(self):
        """Replace catalog labor with worker-based labor costs."""
        if not self.current_bid:
            return
        
        # Calculate total project labor cost from workers (each worker has own hours)
        total_project_labor_cost = sum(
            worker.get("hours", 0) * worker["wage_per_hour"] 
            for worker in self.workers
        )
        
        # Distribute labor cost across sections proportionally by material cost
        if self.current_bid.subtotal_material > 0:
            for section in self.current_bid.sections:
                # Each section gets labor proportional to its material cost
                section_ratio = section.total_material / self.current_bid.subtotal_material
                section_labor = total_project_labor_cost * section_ratio
                
                # Distribute section labor across line items equally
                if section.line_items:
                    labor_per_item = section_labor / len(section.line_items)
                    for line_item in section.line_items:
                        line_item.labor_cost = labor_per_item
        else:
            # Fallback: distribute evenly across all line items
            total_items = sum(len(s.line_items) for s in self.current_bid.sections)
            if total_items > 0:
                labor_per_item = total_project_labor_cost / total_items
                for section in self.current_bid.sections:
                    for line_item in section.line_items:
                        line_item.labor_cost = labor_per_item
    
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
            
            # Add pricing settings to project data
            self.project_data["labor_markup_pct"] = self.labor_markup_pct
            self.project_data["overhead_pct"] = self.overhead_pct
            self.project_data["profit_pct"] = self.profit_pct
            self.project_data["commission_amount"] = self.commission_amount
            self.project_data["tools_rental_amount"] = self.tools_rental_amount
            self.project_data["tools_rental_type"] = self.tools_rental_type
            self.project_data["use_tax_pct"] = self.use_tax_pct
            self.project_data["shipping_amount"] = self.shipping_amount
            
            # Calculate bid using dual compliance (UL 96A + NFPA 780)
            calculator = BidCalculator(self.price_catalog, compliance_code="DUAL")
            self.current_bid = calculator.calculate_bid(self.project_data)
            
            # Apply worker-based labor costs
            self._apply_worker_labor_costs()
            
            # Update display
            self._update_bid_display()
            
            self.page.splash = None
            
            # Show success with worker info
            total_hours = sum(w.get("hours", 0) for w in self.workers)
            worker_summary = f"{len(self.workers)} worker(s), {total_hours:.1f} total hours"
            self._show_feedback_dialog(
                f"Bid calculated successfully!\nCrew: {worker_summary}",
                Colors.GREEN
            )
            self.page.update()
            
        except Exception as ex:
            self.page.splash = None
            self._show_feedback_dialog(f"Error calculating bid: {str(ex)[:100]}", Colors.RED)
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
        self.bid_summary_text.color = Colors.BLACK
        self.bid_summary_text.size = 14
        self.bid_summary_text.weight = FontWeight.BOLD
        
        # Add cost per square foot reality check
        if self.project_data.get("roof_area_sqft"):
            cost_per_sqft = self.current_bid.final_bid_amount / self.project_data["roof_area_sqft"]
            roof_area = self.project_data["roof_area_sqft"]
            
            # Add to summary
            self.bid_summary_text.value += f"\n\nCost per sqft: ${cost_per_sqft:.2f}"
            
            # Scale warning thresholds based on building size
            # Small buildings have higher $/sqft, large buildings have lower $/sqft
            if roof_area < 10000:
                # Small building thresholds
                low_threshold = 1.50
                high_threshold = 8.0
            elif roof_area > 20000:
                # Large building thresholds (costs don't scale linearly)
                low_threshold = 0.60
                high_threshold = 5.0
            else:
                # Medium building - scale proportionally
                # Interpolate between small and large thresholds
                scale_factor = (roof_area - 10000) / 10000  # 0 to 1
                low_threshold = 1.50 - (0.90 * scale_factor)  # 1.50 to 0.60
                high_threshold = 8.0 - (3.0 * scale_factor)  # 8.0 to 5.0
            
            # Warn if outside scaled range
            if cost_per_sqft > high_threshold:
                self.bid_summary_text.value += f"\n⚠️ WARNING: High cost/sqft (typical for {int(roof_area):,} sqft: ${low_threshold:.2f}-${high_threshold:.2f}/sqft)"
                self.bid_summary_text.color = Colors.ORANGE
            elif cost_per_sqft < low_threshold:
                self.bid_summary_text.value += f"\n⚠️ WARNING: Low cost/sqft - verify quantities (typical: ${low_threshold:.2f}-${high_threshold:.2f}/sqft)"
                self.bid_summary_text.color = Colors.ORANGE
        
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
        self.page.update()
    
    # --- MODIFIED EXPORT METHODS (Accepts path from save dialog) ---
    def _export_excel(self, output_path: str): 
        """Export bid to Excel using the path selected by the user."""
        if not self.current_bid:
            return
        
        try:
            # Ensure the path has .xlsx extension
            excel_output = Path(output_path)
            if excel_output.suffix.lower() != '.xlsx':
                excel_output = excel_output.with_suffix('.xlsx')
                print(f"DEBUG: Ensuring .xlsx extension: {excel_output}")
            
            excel_exporter = ExcelBidExporter()
            excel_exporter.export_bid(self.current_bid, excel_output, workers=self.workers)
            print(f"DEBUG: Excel successfully exported to: {excel_output}")
            self._show_feedback_dialog(f"Excel exported to: {excel_output.name}", Colors.GREEN)
        except Exception as ex:
            print(f"ERROR exporting Excel: {ex}")
            import traceback
            traceback.print_exc()
            self._show_feedback_dialog(f"Error exporting Excel: {str(ex)[:100]}", Colors.RED)
    
    def _export_pdf(self, output_path: str): 
        """Export bid to PDF using the path selected by the user."""
        if not self.current_bid:
            return
        
        try:
            # Ensure the path has .pdf extension
            pdf_output = Path(output_path)
            if pdf_output.suffix.lower() != '.pdf':
                pdf_output = pdf_output.with_suffix('.pdf')
                print(f"DEBUG: Ensuring .pdf extension: {pdf_output}")
            
            pdf_exporter = PDFSubmittalExporter(
                contractor_name="ABC Lightning Protection Co.",
                contractor_info={
                    "address": "123 Main St, Your City, ST 12345",
                    "phone": "(555) 123-4567",
                    "email": "info@abclightning.com",
                    "license": "LP-12345"
                }
            )
            pdf_exporter.export_submittal(self.current_bid, pdf_output, "UL 96A + NFPA 780")
            print(f"DEBUG: PDF successfully exported to: {pdf_output}")
            self._show_feedback_dialog(f"PDF exported to: {pdf_output.name}", Colors.GREEN)
        except Exception as ex:
            print(f"ERROR exporting PDF: {ex}")
            import traceback
            traceback.print_exc()
            self._show_feedback_dialog(f"Error exporting PDF: {str(ex)[:100]}", Colors.RED)
    
    # --- LABOR & CREW SETTINGS DIALOG ---
    def _show_labor_settings_dialog(self, e):
        """Show dialog to manage workers, pricing, and bid settings."""
        
        # Worker list container that we'll update
        worker_list_column = ft.Column([], spacing=10)
        
        # Pricing fields
        labor_markup_field = ft.TextField(
            label="Labor Markup (%)",
            value=str(self.labor_markup_pct),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=140,
            hint_text="Default: 20%"
        )
        
        overhead_field = ft.TextField(
            label="Overhead (%)",
            value=str(self.overhead_pct),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=140,
            hint_text="Default: 10%"
        )
        
        profit_field = ft.TextField(
            label="Profit (%)",
            value=str(self.profit_pct),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=140,
            hint_text="Default: 10%"
        )
        
        commission_field = ft.TextField(
            label="Commission ($)",
            value=str(self.commission_amount) if self.commission_amount > 0 else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=140,
            hint_text="Flat amount"
        )
        
        # Tools & Rental type selector
        tools_rental_type_dropdown = ft.Dropdown(
            label="Type",
            options=[
                ft.dropdown.Option("$", "$"),
                ft.dropdown.Option("%", "%"),
            ],
            value=self.tools_rental_type,
            width=80,
            text_size=14,
            content_padding=10
        )
        
        tools_rental_field = ft.TextField(
            label="Tools & Rental",
            value=str(self.tools_rental_amount) if self.tools_rental_amount > 0 else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=110,
            hint_text="Amount"
        )
        
        use_tax_field = ft.TextField(
            label="Use Tax (%)",
            value=str(self.use_tax_pct) if self.use_tax_pct > 0 else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=140,
            hint_text="Applied to materials + shipping"
        )
        
        shipping_field = ft.TextField(
            label="Shipping ($)",
            value=str(self.shipping_amount) if self.shipping_amount > 0 else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=140,
            hint_text="Flat amount"
        )
        
        # Container for dialog content
        dialog_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Configure your crew, pricing, and bid settings:",
                        size=14,
                        color=Colors.GREY_700
                    ),
                    ft.Divider(),
                    
                    # Workers section
                    ft.Text("Workers (set hours and wage for each):", weight=FontWeight.BOLD),
                    worker_list_column,
                    # Add worker button will be inserted here dynamically
                    
                    ft.Divider(),
                    
                    # Pricing section
                    ft.Text("Pricing & Markup:", weight=FontWeight.BOLD, size=14),
                    ft.Row([
                        labor_markup_field,
                        overhead_field,
                        profit_field
                    ], spacing=10),
                    
                    ft.Text("Material & Shipping:", weight=FontWeight.BOLD, size=14),
                    ft.Row([
                        shipping_field,
                        use_tax_field
                    ], spacing=10),
                    
                    ft.Text("Additional Costs:", weight=FontWeight.BOLD, size=14),
                    ft.Row([
                        commission_field,
                    ], spacing=10),
                    ft.Row([
                        tools_rental_field,
                        tools_rental_type_dropdown
                    ], spacing=5, alignment=MainAxisAlignment.START),
                ],
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                tight=True
            ),
            width=600,
            height=600,
            padding=20
        )
        
        # Create the dialog first
        labor_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Bid Settings", size=20, weight=FontWeight.BOLD),
            content=dialog_content,
            actions=[],  # Will be populated later
            actions_alignment=MainAxisAlignment.END,
        )
        
        def update_worker_list():
            """Refresh the worker list display."""
            worker_list_column.controls.clear()
            
            for idx, worker in enumerate(self.workers):
                # Create fields for this worker
                name_field = ft.TextField(
                    label=f"Worker {idx + 1} Name",
                    value=worker["name"],
                    width=150,
                    on_change=lambda e, i=idx: self._update_worker_name(i, e.control.value)
                )
                
                hours_field = ft.TextField(
                    label="Hours",
                    value=str(worker.get("hours", 40.0)),
                    keyboard_type=ft.KeyboardType.NUMBER,
                    width=80,
                    on_change=lambda e, i=idx: self._update_worker_hours(i, e.control.value)
                )
                
                wage_field = ft.TextField(
                    label="Wage ($/hr)",
                    value=str(worker["wage_per_hour"]),
                    keyboard_type=ft.KeyboardType.NUMBER,
                    width=100,
                    on_change=lambda e, i=idx: self._update_worker_wage(i, e.control.value)
                )
                
                # Calculate and display worker total
                worker_total = worker.get("hours", 40.0) * worker["wage_per_hour"]
                total_text = ft.Text(
                    f"${worker_total:,.2f}",
                    size=12,
                    weight=FontWeight.BOLD,
                    color=Colors.GREEN_700,
                    width=80
                )
                worker["_total_text"] = total_text
                
                remove_btn = ft.IconButton(
                    icon=ft.Icons.DELETE,
                    icon_color=Colors.RED,
                    tooltip="Remove worker",
                    on_click=lambda e, i=idx: remove_worker(i)
                )
                
                worker_row = ft.Row(
                    [name_field, hours_field, wage_field, total_text, remove_btn],
                    spacing=10,
                    alignment=MainAxisAlignment.START
                )
                
                worker_list_column.controls.append(worker_row)
        
        def add_worker(e):
            """Add a new worker to the list."""
            worker_num = len(self.workers) + 1
            self.workers.append({
                "name": f"Worker {worker_num}",
                "wage_per_hour": 25.0,
                "hours": 40.0
            })
            update_worker_list()
            self.page.update()
        
        def remove_worker(idx):
            """Remove a worker from the list."""
            if len(self.workers) > 1:  # Keep at least one worker
                self.workers.pop(idx)
                update_worker_list()
                self.page.update()
            else:
                self._show_feedback_dialog("You must have at least one worker", Colors.AMBER_600)
        
        def save_labor_settings(e):
            """Save the labor and pricing settings and close dialog."""
            try:
                # Validate all workers
                for worker in self.workers:
                    hours = worker.get("hours", 0)
                    wage = worker["wage_per_hour"]
                    
                    if hours <= 0 or hours > 1000:
                        self._show_feedback_dialog(
                            f"{worker['name']}: Hours must be between 0 and 1000",
                            Colors.RED
                        )
                        return
                    
                    if wage <= 0 or wage > 500:
                        self._show_feedback_dialog(
                            f"{worker['name']}: Wage must be between $0 and $500/hr",
                            Colors.RED
                        )
                        return
                
                # Validate and save pricing settings
                labor_markup = float(labor_markup_field.value) if labor_markup_field.value else 0.0
                overhead = float(overhead_field.value) if overhead_field.value else 0.0
                profit = float(profit_field.value) if profit_field.value else 0.0
                commission = float(commission_field.value) if commission_field.value else 0.0
                tools_rental = float(tools_rental_field.value) if tools_rental_field.value else 0.0
                tools_rental_type = tools_rental_type_dropdown.value
                use_tax = float(use_tax_field.value) if use_tax_field.value else 0.0
                shipping = float(shipping_field.value) if shipping_field.value else 0.0
                
                # Validate percentages (reasonable ranges)
                if labor_markup < 0 or labor_markup > 100:
                    self._show_feedback_dialog("Labor markup must be between 0% and 100%", Colors.RED)
                    return
                if overhead < 0 or overhead > 100:
                    self._show_feedback_dialog("Overhead must be between 0% and 100%", Colors.RED)
                    return
                if profit < 0 or profit > 100:
                    self._show_feedback_dialog("Profit must be between 0% and 100%", Colors.RED)
                    return
                if use_tax < 0 or use_tax > 100:
                    self._show_feedback_dialog("Use tax must be between 0% and 100%", Colors.RED)
                    return
                if commission < 0:
                    self._show_feedback_dialog("Commission cannot be negative", Colors.RED)
                    return
                if tools_rental < 0:
                    self._show_feedback_dialog("Tools & rental cannot be negative", Colors.RED)
                    return
                if shipping < 0:
                    self._show_feedback_dialog("Shipping cannot be negative", Colors.RED)
                    return
                
                # Save pricing settings
                self.labor_markup_pct = labor_markup
                self.overhead_pct = overhead
                self.profit_pct = profit
                self.commission_amount = commission
                self.tools_rental_amount = tools_rental
                self.tools_rental_type = tools_rental_type
                self.use_tax_pct = use_tax
                self.shipping_amount = shipping
                
                # Calculate total labor cost summary
                total_labor_cost = sum(w.get("hours", 0) * w["wage_per_hour"] for w in self.workers)
                total_hours = sum(w.get("hours", 0) for w in self.workers)
                
                # Close dialog
                labor_dialog.open = False
                self.page.update()
                
                # Show success message
                self._show_feedback_dialog(
                    f"Bid settings saved!\n"
                    f"Workers: {len(self.workers)} | Hours: {total_hours:.1f} | Labor: ${total_labor_cost:,.2f}\n"
                    f"Markups: Labor {labor_markup}%, Overhead {overhead}%, Profit {profit}%",
                    Colors.GREEN
                )
                
                # If bid already calculated, recalculate with new settings
                if self.current_bid and self.price_catalog:
                    self._calculate_bid(None)
                    
            except ValueError:
                self._show_feedback_dialog("Please enter valid numbers for all fields", Colors.RED)
        
        def cancel_dialog(e):
            """Close dialog without saving."""
            # Restore original values if user cancels
            labor_dialog.open = False
            self.page.update()
        
        # Add worker button
        add_worker_btn = ft.ElevatedButton(
            "➕ Add Worker",
            on_click=add_worker,
            icon=ft.Icons.PERSON_ADD
        )
        
        # Insert the add_worker button right after worker_list_column (position 3: header text, worker list, button)
        dialog_content.content.controls.insert(3, add_worker_btn)
        
        # Set dialog actions
        labor_dialog.actions = [
            ft.TextButton("Cancel", on_click=cancel_dialog),
            ft.ElevatedButton(
                "Save Settings",
                on_click=save_labor_settings,
                bgcolor=Colors.GREEN_700,
                color=Colors.WHITE
            ),
        ]
        
        # Initial worker list population
        update_worker_list()
        
        # Add to overlay and show
        self.page.overlay.append(labor_dialog)
        labor_dialog.open = True
        self.page.update()
    
    def _update_worker_name(self, idx: int, name: str):
        """Update worker name."""
        if idx < len(self.workers):
            self.workers[idx]["name"] = name
    
    def _update_worker_hours(self, idx: int, hours_str: str):
        """Update worker hours."""
        try:
            hours = float(hours_str)
            if idx < len(self.workers) and hours > 0:
                self.workers[idx]["hours"] = hours
                self._update_worker_total(idx)
        except ValueError:
            pass  # Ignore invalid input during typing
    
    def _update_worker_wage(self, idx: int, wage_str: str):
        """Update worker wage."""
        try:
            wage = float(wage_str)
            if idx < len(self.workers) and wage > 0:
                self.workers[idx]["wage_per_hour"] = wage
                self._update_worker_total(idx)
        except ValueError:
            pass  # Ignore invalid input during typing

    def _update_worker_total(self, idx: int):
        """Update the worker total cost display if present."""
        if idx >= len(self.workers):
            return
        worker = self.workers[idx]
        total_text = worker.get("_total_text")
        if total_text:
            worker_total = worker.get("hours", 0) * worker.get("wage_per_hour", 0)
            total_text.value = f"${worker_total:,.2f}"
            total_text.update()
    
    # --- FEEDBACK METHODS ---
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