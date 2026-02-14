"""
Main Flet GUI Window for LightningBid

This is the primary GUI interface that orchestrates the entire
bidding workflow through a user-friendly graphical interface.
"""

import flet as ft
import json
from datetime import datetime, date
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
from src.database.bid_repository import BidRepository
from src.database.job_repository import JobRepository
from src.gui.login_screen import LoginScreen, create_login_view 
from src.adapters.excel_loader import load_pricing_from_excel
from src.adapters.pdf_loader import parse_pdf_flexible
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

        # Main layout state (enterprise shell)
        self.nav_collapsed = False
        self.active_module = "dashboard"
        self.nav_items = []
        self.nav_rail: Optional[ft.NavigationRail] = None
        self.left_nav_container: Optional[ft.Container] = None
        self.content_container: Optional[ft.Container] = None
        self.module_views: Dict[str, ft.Control] = {}
        
        # --- NEW: DB and Authentication State ---
        self.db = self._initialize_db()
        # NOTE: Repository layer is a temporary local DB adapter.
        # This will be swapped to a SaaS API client later without changing GUI code.
        self.repo = BidRepository(self.db) if self.db else None
        self.job_repo = JobRepository(self.db) if self.db else None
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
        # Track last export paths for recovery (stored in DB autosave for now)
        self.last_excel_export: Optional[str] = None
        self.last_pdf_export: Optional[str] = None
        self.current_bid_id: Optional[int] = None
        
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
        self._force_layout_refresh()

    def _force_layout_refresh(self):
        """Force a layout refresh to avoid click hitbox glitches on Windows."""
        try:
            w = self.page.window.width
            h = self.page.window.height
            # Nudge size by 1px to trigger a layout recalculation
            self.page.window.width = w + 1
            self.page.window.height = h + 1
            self.page.update()
            self.page.window.width = w
            self.page.window.height = h
            self.page.update()
        except Exception:
            pass

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

    # --- SESSION AUTO-SAVE (DB-backed, SaaS-ready) ---
    def _build_session_payload(self) -> Dict[str, Any]:
        """Build a JSON-serializable session snapshot (DB-backed, SaaS-ready)."""
        # NOTE: This JSON payload is stored in SQLite for now.
        # When the SaaS API is added, this payload will be sent to the backend
        # instead of a local DB table.
        workers_clean = [
            {
                "name": w.get("name", "Worker"),
                "wage_per_hour": w.get("wage_per_hour", 0),
                "hours": w.get("hours", 0),
            }
            for w in self.workers
        ]
        
        return {
            "version": 1,
            "saved_at": datetime.utcnow().isoformat(),
            "project_data": self.project_data,
            "workers": workers_clean,
            "pricing_settings": {
                "labor_markup_pct": self.labor_markup_pct,
                "overhead_pct": self.overhead_pct,
                "profit_pct": self.profit_pct,
                "commission_amount": self.commission_amount,
                "tools_rental_amount": self.tools_rental_amount,
                "tools_rental_type": self.tools_rental_type,
                "use_tax_pct": self.use_tax_pct,
                "shipping_amount": self.shipping_amount,
            },
            "file_paths": {
                "excel": str(self.excel_file_path) if self.excel_file_path else None,
                "pdf": str(self.pdf_file_path) if self.pdf_file_path else None,
            },
            "last_exports": {
                "excel": self.last_excel_export,
                "pdf": self.last_pdf_export,
            }
        }
    
    def _save_session(self, reason: str = ""):
        """Persist a session snapshot (DB-backed, SaaS-ready)."""
        if not self.repo or not self.current_user_id:
            return
        try:
            payload = self._build_session_payload()
            payload["reason"] = reason
            self.repo.save_autosave(self.current_user_id, payload)
        except Exception:
            # Avoid breaking the UI for autosave failures
            pass
    
    def _load_session(self) -> Optional[Dict[str, Any]]:
        """Load a saved session snapshot if present (DB-backed, SaaS-ready)."""
        if not self.repo or not self.current_user_id:
            return None
        try:
            data = self.repo.load_autosave(self.current_user_id)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    
    def _clear_session(self):
        """Remove the autosave record (DB-backed, SaaS-ready)."""
        if not self.repo or not self.current_user_id:
            return
        try:
            self.repo.clear_autosave(self.current_user_id)
        except Exception:
            pass
    
    def _apply_session_data(self, data: Dict[str, Any]):
        """Apply session data to UI and state (DB-backed, SaaS-ready)."""
        project_data = data.get("project_data", {})
        self.project_data.update(project_data)
        
        # Update fields if they exist
        if hasattr(self, "project_name_field"):
            self.project_name_field.value = project_data.get("project_name", "")
        if hasattr(self, "height_field"):
            self.height_field.value = str(project_data.get("building_height_ft") or "")
        if hasattr(self, "area_field"):
            self.area_field.value = str(project_data.get("roof_area_sqft") or "")
        if hasattr(self, "perimeter_field"):
            self.perimeter_field.value = str(project_data.get("perimeter_ft") or "")
        if hasattr(self, "corners_field"):
            self.corners_field.value = str(project_data.get("num_corners") or 4)
        if hasattr(self, "material_dropdown"):
            self.material_dropdown.value = project_data.get("preferred_material", "copper")
        if hasattr(self, "metal_roof_checkbox"):
            self.metal_roof_checkbox.value = bool(project_data.get("has_metal_roof", False))
        
        # Restore workers (ensure at least one)
        workers = data.get("workers") or []
        self.workers = workers if workers else [{"name": "Worker 1", "wage_per_hour": 25.0, "hours": 40.0}]
        
        # Restore pricing settings
        pricing = data.get("pricing_settings", {})
        self.labor_markup_pct = float(pricing.get("labor_markup_pct", self.labor_markup_pct))
        self.overhead_pct = float(pricing.get("overhead_pct", self.overhead_pct))
        self.profit_pct = float(pricing.get("profit_pct", self.profit_pct))
        self.commission_amount = float(pricing.get("commission_amount", self.commission_amount))
        self.tools_rental_amount = float(pricing.get("tools_rental_amount", self.tools_rental_amount))
        self.tools_rental_type = pricing.get("tools_rental_type", self.tools_rental_type)
        self.use_tax_pct = float(pricing.get("use_tax_pct", self.use_tax_pct))
        self.shipping_amount = float(pricing.get("shipping_amount", self.shipping_amount))
        
        # Restore file paths (if they still exist)
        file_paths = data.get("file_paths", {})
        excel_path = file_paths.get("excel")
        pdf_path = file_paths.get("pdf")
        if excel_path and Path(excel_path).exists():
            self.excel_file_path = Path(excel_path)
            if hasattr(self, "excel_file_text"):
                self.excel_file_text.value = self.excel_file_path.name
        if pdf_path and Path(pdf_path).exists():
            self.pdf_file_path = Path(pdf_path)
            if hasattr(self, "pdf_file_text"):
                self.pdf_file_text.value = self.pdf_file_path.name
        
        # Restore last export paths (informational only)
        exports = data.get("last_exports", {})
        self.last_excel_export = exports.get("excel")
        self.last_pdf_export = exports.get("pdf")
        
        self.page.update()
    
    def _prompt_restore_session(self):
        """Prompt user to restore a previous session (DB-backed, SaaS-ready)."""
        session_data = self._load_session()
        if not session_data:
            return
        
        def restore_session(_):
            self._apply_session_data(session_data)
            recovery_dialog.open = False
            self.page.update()
        
        def discard_session(_):
            self._clear_session()
            recovery_dialog.open = False
            self.page.update()
        
        recovery_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Restore previous session?"),
            content=ft.Text(
                "We found an autosaved session from your last work. "
                "Would you like to restore it?"
            ),
            actions=[
                ft.TextButton("Discard", on_click=discard_session),
                ft.ElevatedButton("Restore", on_click=restore_session, bgcolor=Colors.GREEN_700, color=Colors.WHITE),
            ],
            actions_alignment=MainAxisAlignment.END,
        )
        self.page.overlay.append(recovery_dialog)
        recovery_dialog.open = True
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
        # Module registry (enterprise shell)
        self.nav_items = [
            {"key": "dashboard", "label": "Dashboard", "icon": ft.Icons.DASHBOARD},
            {"key": "projects", "label": "Projects", "icon": ft.Icons.FOLDER},
            {"key": "bidding", "label": "Bidding", "icon": ft.Icons.REQUEST_QUOTE},
            {"key": "jobs", "label": "Jobs", "icon": ft.Icons.WORK},
            {"key": "calendar", "label": "Calendar", "icon": ft.Icons.CALENDAR_MONTH},
            {"key": "reports", "label": "Reports", "icon": ft.Icons.ASSESSMENT},
        ]

        # Build module views once to preserve control state
        self.module_views = {
            "dashboard": self._build_dashboard_view(),
            "projects": self._build_placeholder_view(
                "Projects",
                "Project lists, filtering, and collaboration tools will appear here."
            ),
            "bidding": self._build_bidding_view(),
            "jobs": self._build_jobs_view(),
            "calendar": self._build_calendar_view(),
            "reports": self._build_placeholder_view(
                "Reports",
                "Reporting, exports, and analytics will appear here."
            ),
        }

        # Ensure file pickers are attached after building bidding view
        self._ensure_file_pickers_in_overlay()

        # Shell layout (left nav + content)
        self.content_container = ft.Container(expand=True)
        self._set_active_module(self.active_module, update=False)
        shell_layout = ft.Row(
            [
                self._build_left_nav(),
                self.content_container
            ],
            expand=True,
            spacing=0
        )

        main_view = ft.View(
            "/",
            [shell_layout],
            padding=0,
            bgcolor=Colors.GREY_100,
            vertical_alignment=MainAxisAlignment.START
        )
        self.page.views.clear()
        self.page.views.append(main_view)
        self.page.update()
        self._force_layout_refresh()
        
        # Offer to restore last session (TEMP until DB migration)
        self._prompt_restore_session()
        
        # Populate bid history if possible
        self._refresh_bid_history()
        self._refresh_recent_bids()

    # --- UI COMPONENT BUILDERS ---

    def _build_left_nav(self) -> ft.Container:
        """Build the collapsible left navigation rail."""
        destinations = [
            ft.NavigationRailDestination(
                icon=item["icon"],
                label=item["label"]
            )
            for item in self.nav_items
        ]
        selected_index = self._nav_index_from_key(self.active_module)
        self.nav_rail = ft.NavigationRail(
            selected_index=selected_index,
            destinations=destinations,
            extended=not self.nav_collapsed,
            min_width=72,
            min_extended_width=220,
            leading=ft.IconButton(
                icon=ft.Icons.MENU,
                tooltip="Collapse menu",
                on_click=self._toggle_nav
            ),
            on_change=self._on_nav_change
        )
        self.left_nav_container = ft.Container(
            content=self.nav_rail,
            width=220 if not self.nav_collapsed else 72,
            bgcolor=Colors.WHITE,
            border=ft.border.only(right=ft.BorderSide(1, Colors.GREY_300)),
            padding=ft.padding.only(top=10, bottom=10)
        )
        return self.left_nav_container

    def _build_content_header(self, title: str, subtitle: Optional[str] = None) -> ft.Container:
        """Builds the top content header."""
        header_text = ft.Column(
            [
                ft.Text(title, size=22, weight=FontWeight.BOLD, color=Colors.BLUE_800),
                ft.Text(subtitle or "Enterprise workspace", size=12, color=Colors.GREY_600),
            ],
            spacing=2
        )
        return ft.Container(
            content=ft.Row(
                [header_text],
                alignment=MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=CrossAxisAlignment.CENTER
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=16),
            bgcolor=Colors.WHITE,
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.GREY_300))
        )

    def _build_tab_bar(self, tabs: list[str]) -> ft.Container:
        """Builds a tabbed header bar."""
        tab_control = ft.Tabs(
            tabs=[ft.Tab(text=tab) for tab in tabs],
            selected_index=0,
            indicator_color=Colors.BLUE_600
        )
        return ft.Container(
            content=tab_control,
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            bgcolor=Colors.WHITE,
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.GREY_200))
        )

    def _build_toolbar(self) -> ft.Container:
        """Builds the search + filter toolbar."""
        search_field = ft.TextField(
            hint_text="Search",
            prefix_icon=ft.Icons.SEARCH,
            height=40,
            expand=True
        )
        filter_btn = ft.OutlinedButton("Filters", icon=ft.Icons.TUNE)
        sort_btn = ft.OutlinedButton("Sort", icon=ft.Icons.SWAP_VERT)
        return ft.Container(
            content=ft.Row(
                [search_field, filter_btn, sort_btn],
                spacing=10
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            bgcolor=Colors.WHITE,
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.GREY_200))
        )

    def _build_module_layout(self, module_key: str) -> ft.Container:
        """Builds the main content area for a module."""
        module_titles = {
            "dashboard": "Dashboard",
            "projects": "Projects",
            "bidding": "Bidding Workspace",
            "jobs": "Job Management",
            "reports": "Reports",
        }
        module_tabs = {
            "dashboard": ["Overview", "Insights"],
            "projects": ["Directory", "Connections"],
            "bidding": ["Overview", "Workflow"],
            "jobs": ["Active Jobs", "Calendar"],
            "reports": ["Summary", "Exports"],
        }
        title = module_titles.get(module_key, "Workspace")
        tabs = module_tabs.get(module_key, ["Overview"])
        content_view = self.module_views.get(module_key, ft.Container())

        return ft.Container(
            content=ft.Column(
                [
                    self._build_content_header(title),
                    self._build_tab_bar(tabs),
                    self._build_toolbar(),
                    ft.Container(
                        content=content_view,
                        expand=True,
                        padding=20
                    )
                ],
                spacing=0,
                expand=True
            ),
            expand=True,
            bgcolor=Colors.GREY_100
        )

    def _build_bidding_view(self) -> ft.Control:
        """Build the bidding module content view."""
        file_section = self._build_file_section()
        project_section = self._build_project_section()
        actions_section = self._build_actions_section()
        bid_display = self._build_bid_display()

        return ft.Container(
            content=ft.Column(
                [
                    file_section,
                    project_section,
                    actions_section,
                    bid_display
                ],
                spacing=16,
                scroll=ScrollMode.AUTO
            ),
            expand=True
        )

    def _build_jobs_view(self) -> ft.Control:
        """Build the jobs management dashboard with Kanban-style status columns."""
        if not self.current_user_id or not self.job_repo:
            return self._build_placeholder_view("Jobs", "Please log in to view jobs.")
        
        # Get all active jobs
        try:
            active_jobs = self.job_repo.get_active_jobs(self.current_user_id)
            
            # Group jobs by status
            jobs_by_status = {
                "awaiting_approval": [],
                "scheduled": [],
                "in_progress": [],
                "inspection": [],
                "completed": []
            }
            
            for job in active_jobs:
                if job.status in jobs_by_status:
                    jobs_by_status[job.status].append(job)
            
            # Build status columns
            columns = []
            status_config = [
                ("awaiting_approval", "Awaiting Approval", Colors.AMBER_500),
                ("scheduled", "Scheduled", Colors.BLUE_500),
                ("in_progress", "In Progress", Colors.ORANGE_500),
                ("inspection", "Inspection", Colors.PURPLE_500),
                ("completed", "Completed", Colors.GREEN_500)
            ]
            
            for status_key, status_label, status_color in status_config:
                job_cards = []
                for job in jobs_by_status[status_key]:
                    job_cards.append(self._build_job_card(job))
                
                if not job_cards:
                    job_cards = [ft.Container(
                        content=ft.Text("No jobs", size=12, color=Colors.GREY_400),
                        padding=10
                    )]
                
                column = ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    width=4,
                                    height=20,
                                    bgcolor=status_color,
                                    border_radius=2
                                ),
                                ft.Text(
                                    status_label,
                                    size=14,
                                    weight=FontWeight.BOLD,
                                    color=Colors.GREY_800
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        str(len(jobs_by_status[status_key])),
                                        size=12,
                                        color=Colors.WHITE
                                    ),
                                    bgcolor=status_color,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                    border_radius=10
                                )
                            ], spacing=8),
                            padding=ft.padding.only(bottom=12)
                        ),
                        ft.Column(job_cards, spacing=8, scroll=ScrollMode.AUTO)
                    ], spacing=0),
                    padding=16,
                    bgcolor=Colors.GREY_50,
                    border_radius=8,
                    expand=True
                )
                columns.append(column)
            
            # Header with actions
            header = ft.Container(
                content=ft.Row([
                    ft.Text("Active Jobs", size=20, weight=FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        "View All Jobs",
                        icon=ft.Icons.LIST,
                        on_click=self._show_all_jobs_list
                    )
                ]),
                padding=ft.padding.only(bottom=16)
            )
            
            return ft.Container(
                content=ft.Column([
                    header,
                    ft.Row(columns, spacing=16, expand=True, scroll=ScrollMode.AUTO)
                ], spacing=0, expand=True),
                expand=True
            )
            
        except Exception as e:
            return self._build_placeholder_view(
                "Error Loading Jobs",
                f"An error occurred: {str(e)}"
            )
    
    def _build_calendar_view(self) -> ft.Control:
        """Build the calendar view for job scheduling and visualization."""
        if not self.current_user_id or not self.job_repo:
            return self._build_placeholder_view("Calendar", "Please log in to view the calendar.")
        
        # Import calendar component
        from src.gui.components.calendar_view import CalendarView
        from datetime import date, timedelta
        
        # Create calendar component
        calendar = CalendarView(
            on_date_click=self._on_calendar_date_click,
            on_job_click=self._on_calendar_job_click
        )
        
        # Load active jobs (calendar filters by date client-side)
        try:
            jobs = self.job_repo.get_active_jobs(self.current_user_id)
            
            calendar.set_jobs(jobs)
            
        except Exception as e:
            print(f"Error loading calendar jobs: {e}")
        
        # Build and return calendar
        return calendar.build()
    
    def _on_calendar_date_click(self, selected_date: date):
        """Handle date click in calendar - open job creation dialog."""
        # Format date for dialog
        date_str = selected_date.strftime("%Y-%m-%d")
        
        # Show dialog to create new job or view jobs on this date
        from datetime import date as date_class
        jobs_on_date = []
        
        try:
            if self.job_repo:
                jobs_on_date = self.job_repo.get_jobs_by_date(
                    self.current_user_id,
                    date_str
                )
        except Exception as e:
            print(f"Error fetching jobs for date: {e}")
        
        # If there are jobs, show them; otherwise offer to create one
        if jobs_on_date:
            self._show_date_jobs_dialog(selected_date, jobs_on_date)
        else:
            self._show_feedback_dialog(
                f"No jobs scheduled for {selected_date.strftime('%B %d, %Y')}",
                Colors.BLUE_500,
                "Calendar"
            )
    
    def _on_calendar_job_click(self, job):
        """Handle job card click in calendar - show job details."""
        self._show_job_details(job)
    
    def _show_date_jobs_dialog(self, selected_date: date, jobs: list):
        """Show dialog with all jobs on a specific date."""
        job_list_items = []
        
        for job in jobs:
            job_list_items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.WORK, color=Colors.BLUE_500),
                    title=ft.Text(job.project_name or f"Job #{job.job_id}"),
                    subtitle=ft.Text(f"Status: {job.status_display}"),
                    trailing=ft.Text(f"${job.bid_amount:,.2f}" if job.bid_amount else ""),
                    on_click=lambda e, j=job: self._on_date_job_selected(e, j)
                )
            )
        
        dialog = ft.AlertDialog(
            title=ft.Text(f"Jobs on {selected_date.strftime('%B %d, %Y')}"),
            content=ft.Container(
                content=ft.Column(job_list_items, spacing=0, scroll=ScrollMode.AUTO),
                width=500,
                height=400
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda e: self._close_dialog())
            ]
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def _on_date_job_selected(self, e, job):
        """Handle selection of a job from the date jobs dialog."""
        # Close the current dialog
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()
        
        # Show job details
        self._show_job_details(job)
    
    def _close_dialog(self):
        """Close the currently open dialog."""
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()
    
    def _build_job_card(self, job) -> ft.Container:
        """Build a card for displaying a job in the Kanban board."""
        # Format scheduled date
        scheduled_display = "Not scheduled"
        if job.scheduled_date:
            try:
                from datetime import datetime
                date_obj = datetime.fromisoformat(job.scheduled_date)
                scheduled_display = date_obj.strftime("%b %d, %Y")
            except:
                scheduled_display = job.scheduled_date
        
        # Get crew info
        crew_display = "No crew assigned"
        crew_list = job.crew_list
        if crew_list:
            crew_display = ", ".join(crew_list[:2])
            if len(crew_list) > 2:
                crew_display += f" +{len(crew_list) - 2} more"
        
        status_action = self._build_job_status_action(job)

        # Build card
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    job.project_name or f"Job #{job.job_id}",
                    size=13,
                    weight=FontWeight.BOLD,
                    color=Colors.GREY_900
                ),
                ft.Row([
                    ft.Icon(ft.Icons.CALENDAR_TODAY, size=12, color=Colors.GREY_500),
                    ft.Text(scheduled_display, size=11, color=Colors.GREY_600)
                ], spacing=4),
                ft.Row([
                    ft.Icon(ft.Icons.PEOPLE, size=12, color=Colors.GREY_500),
                    ft.Text(crew_display, size=11, color=Colors.GREY_600)
                ], spacing=4),
                ft.Row([
                    ft.Icon(ft.Icons.ATTACH_MONEY, size=12, color=Colors.GREY_500),
                    ft.Text(
                        f"${job.bid_amount:,.2f}" if job.bid_amount else "N/A",
                        size=11,
                        color=Colors.GREY_600
                    )
                ], spacing=4),
                status_action if status_action else ft.Container(),
                ft.Divider(height=1, color=Colors.GREY_300),
                # Show Approve button for awaiting approval jobs
                ft.ElevatedButton(
                    "✓ Approve & Schedule",
                    icon=ft.Icons.CHECK_CIRCLE,
                    bgcolor=Colors.GREEN_500,
                    color=Colors.WHITE,
                    on_click=lambda e, j=job: self._show_approve_job_dialog(j),
                    expand=True
                ) if job.status == "awaiting_approval" else ft.Row([
                    ft.TextButton(
                        "View Details",
                        on_click=lambda e, j=job: self._show_job_details(j),
                        style=ft.ButtonStyle(padding=0)
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.MORE_VERT,
                        icon_size=16,
                        on_click=lambda e, j=job: self._show_job_actions(j)
                    )
                ], spacing=0)
            ], spacing=6),
            padding=12,
            bgcolor=Colors.WHITE,
            border=ft.border.all(1, Colors.GREY_300),
            border_radius=8
        )

    def _build_job_status_action(self, job) -> Optional[ft.Control]:
        """Build a quick status transition button for a job card."""
        if job.status == "scheduled":
            return ft.OutlinedButton(
                "Move to In Progress",
                icon=ft.Icons.PLAY_CIRCLE,
                on_click=lambda e, j=job: self._quick_set_job_status(j, "in_progress")
            )
        if job.status == "in_progress":
            return ft.OutlinedButton(
                "Move to Inspection",
                icon=ft.Icons.SEARCH,
                on_click=lambda e, j=job: self._quick_set_job_status(j, "inspection")
            )
        if job.status == "inspection":
            return ft.OutlinedButton(
                "Mark Completed",
                icon=ft.Icons.CHECK_CIRCLE,
                on_click=lambda e, j=job: self._quick_set_job_status(j, "completed")
            )
        return None

    def _quick_set_job_status(self, job, new_status: str):
        """Quickly set job status and refresh relevant views."""
        if not self.job_repo or not self.current_user_id:
            return
        try:
            self.job_repo.update_job_status(
                job.job_id,
                self.current_user_id,
                new_status,
                f"Status changed to {new_status.replace('_', ' ')}"
            )

            # Refresh views
            self.module_views["jobs"] = self._build_jobs_view()
            self.module_views["calendar"] = self._build_calendar_view()
            self.module_views["dashboard"] = self._build_dashboard_view()

            if self.active_module in ["jobs", "calendar", "dashboard"]:
                self._set_active_module(self.active_module)

            self._show_feedback_dialog(
                f"Job moved to {new_status.replace('_', ' ').title()}",
                Colors.GREEN,
                "Success"
            )
        except Exception as ex:
            self._show_feedback_dialog(f"Error updating job: {str(ex)}", Colors.RED, "Error")
    
    def _show_approve_job_dialog(self, job):
        """Show dialog to approve a job and set scheduled date."""
        from datetime import datetime, date
        
        # Date field for scheduled date
        scheduled_date_field = ft.TextField(
            label="Scheduled Date (YYYY-MM-DD)",
            hint_text="2024-01-15",
            width=300,
            autofocus=True
        )
        
        # Notes field
        notes_field = ft.TextField(
            label="Notes (optional)",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=300
        )
        
        def approve_job(e):
            if not scheduled_date_field.value:
                self._show_feedback_dialog("Please enter a scheduled date", Colors.RED, "Error")
                return
            
            if self.job_repo and self.current_user_id:
                try:
                    # Update job status to scheduled and set date
                    self.job_repo.update_job_status(
                        job.job_id,
                        self.current_user_id,
                        "scheduled",
                        notes_field.value or "Job approved and scheduled"
                    )
                    
                    # Update scheduled date
                    self.job_repo.update_job_dates(
                        job.job_id,
                        scheduled_date=scheduled_date_field.value
                    )
                    
                    dialog.open = False
                    
                    # Refresh views
                    self.module_views["jobs"] = self._build_jobs_view()
                    self.module_views["calendar"] = self._build_calendar_view()
                    self.module_views["dashboard"] = self._build_dashboard_view()
                    
                    if self.active_module in ["jobs", "calendar", "dashboard"]:
                        self._set_active_module(self.active_module)
                    
                    self._show_feedback_dialog(
                        f"Job approved and scheduled for {scheduled_date_field.value}",
                        Colors.GREEN,
                        "Success"
                    )
                except Exception as ex:
                    self._show_feedback_dialog(f"Error approving job: {str(ex)}", Colors.RED, "Error")
            
            self.page.update()
        
        def cancel(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text(f"Approve Job: {job.project_name}"),
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=20, color=Colors.BLUE_500),
                        ft.Text(
                            "Approving this job will move it to 'Scheduled' status\nand add it to the calendar.",
                            size=12,
                            color=Colors.GREY_600
                        )
                    ], spacing=8),
                    padding=ft.padding.only(bottom=12),
                    bgcolor=Colors.BLUE_50,
                    border_radius=8
                ),
                scheduled_date_field,
                notes_field,
                ft.Container(
                    content=ft.Column([
                        ft.Text("Job Details:", size=12, weight=FontWeight.BOLD),
                        ft.Text(f"• Bid Amount: ${job.bid_amount:,.2f}" if job.bid_amount else "• Bid Amount: N/A", size=11, color=Colors.GREY_600),
                        ft.Text(f"• Crew: {', '.join(job.crew_list)}" if job.crew_list else "• Crew: Not assigned", size=11, color=Colors.GREY_600)
                    ], spacing=4),
                    padding=ft.padding.only(top=8)
                )
            ], spacing=12, tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton(
                    "Approve & Schedule",
                    icon=ft.Icons.CHECK_CIRCLE,
                    bgcolor=Colors.GREEN_500,
                    color=Colors.WHITE,
                    on_click=approve_job
                )
            ],
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_all_jobs_list(self, e):
        """Show all jobs in a list view."""
        # Placeholder - will be implemented in job details
        self._show_feedback_dialog("List view coming soon!", Colors.BLUE, "Info")
    
    def _show_job_details(self, job):
        """Show detailed view of a job."""
        if not self.job_repo:
            return
        
        # Reload job with full details
        full_job = self.job_repo.get_job(job.job_id)
        if not full_job:
            self._show_feedback_dialog("Job not found", Colors.RED, "Error")
            return
        
        # Format dates
        def format_date(date_str):
            if not date_str:
                return "Not set"
            try:
                from datetime import datetime
                date_obj = datetime.fromisoformat(date_str)
                return date_obj.strftime("%B %d, %Y")
            except:
                return date_str
        
        # Status badge color
        status_colors = {
            "scheduled": Colors.BLUE_500,
            "in_progress": Colors.ORANGE_500,
            "inspection": Colors.PURPLE_500,
            "completed": Colors.GREEN_500,
            "invoiced": Colors.TEAL_500
        }
        status_color = status_colors.get(full_job.status, Colors.GREY_500)
        
        # Build job info section
        job_info = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Job Information", size=16, weight=FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Text(
                            full_job.status_display,
                            color=Colors.WHITE,
                            size=12
                        ),
                        bgcolor=status_color,
                        padding=ft.padding.symmetric(horizontal=12, vertical=4),
                        border_radius=12
                    )
                ]),
                ft.Divider(height=1),
                ft.Row([
                    ft.Icon(ft.Icons.BUSINESS, size=16, color=Colors.GREY_600),
                    ft.Text(f"Project: {full_job.project_name}", size=13)
                ], spacing=8),
                ft.Row([
                    ft.Icon(ft.Icons.CALENDAR_TODAY, size=16, color=Colors.GREY_600),
                    ft.Text(f"Scheduled: {format_date(full_job.scheduled_date)}", size=13)
                ], spacing=8),
                ft.Row([
                    ft.Icon(ft.Icons.PLAY_CIRCLE, size=16, color=Colors.GREY_600),
                    ft.Text(f"Started: {format_date(full_job.start_date)}", size=13)
                ], spacing=8),
                ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=Colors.GREY_600),
                    ft.Text(f"Completed: {format_date(full_job.completion_date)}", size=13)
                ], spacing=8),
                ft.Row([
                    ft.Icon(ft.Icons.ATTACH_MONEY, size=16, color=Colors.GREY_600),
                    ft.Text(
                        f"Bid Amount: ${full_job.bid_amount:,.2f}" if full_job.bid_amount else "N/A",
                        size=13
                    )
                ], spacing=8)
            ], spacing=8),
            padding=16,
            bgcolor=Colors.GREY_50,
            border_radius=8
        )
        
        # Crew section
        crew_list = full_job.crew_list
        crew_display = "No crew assigned"
        if crew_list:
            crew_display = "\n".join([f"• {name}" for name in crew_list])
        
        def assign_crew(e):
            self._show_assign_crew_dialog(full_job)
            close_dialog(e)
        
        crew_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Assigned Crew", size=14, weight=FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.EDIT,
                        icon_size=16,
                        tooltip="Assign Crew",
                        on_click=assign_crew
                    )
                ]),
                ft.Divider(height=1),
                ft.Text(crew_display, size=12, color=Colors.GREY_700)
            ], spacing=8),
            padding=16,
            bgcolor=Colors.GREY_50,
            border_radius=8
        )
        
        # Notes section
        notes_display = full_job.notes or "No notes"
        notes_section = ft.Container(
            content=ft.Column([
                ft.Text("Notes", size=14, weight=FontWeight.BOLD),
                ft.Divider(height=1),
                ft.Text(notes_display, size=12, color=Colors.GREY_700)
            ], spacing=8),
            padding=16,
            bgcolor=Colors.GREY_50,
            border_radius=8
        )
        
        # Documents section
        docs_list = []
        if full_job.documents:
            for doc in full_job.documents[:5]:  # Show first 5
                docs_list.append(ft.Row([
                    ft.Icon(ft.Icons.ATTACH_FILE, size=14, color=Colors.GREY_600),
                    ft.Text(doc.tag or doc.document_type, size=11),
                    ft.Container(expand=True),
                    ft.Text(doc.uploaded_at[:10] if doc.uploaded_at else "", size=10, color=Colors.GREY_500)
                ], spacing=4))
        else:
            docs_list = [ft.Text("No documents uploaded", size=12, color=Colors.GREY_500)]
        
        documents_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Documents & Photos", size=14, weight=FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.TextButton(
                        "Upload",
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=lambda e, j=full_job: self._upload_job_document(j),
                        style=ft.ButtonStyle(padding=0)
                    )
                ]),
                ft.Divider(height=1),
                ft.Column(docs_list, spacing=4)
            ], spacing=8),
            padding=16,
            bgcolor=Colors.GREY_50,
            border_radius=8
        )
        
        # Activity timeline
        activity_items = []
        for activity in full_job.activities[:5]:  # Show first 5
            activity_items.append(ft.Row([
                ft.Container(
                    width=8,
                    height=8,
                    bgcolor=Colors.BLUE_500,
                    border_radius=4
                ),
                ft.Column([
                    ft.Text(activity.description or activity.activity_type, size=11),
                    ft.Text(
                        activity.created_at[:16] if activity.created_at else "",
                        size=9,
                        color=Colors.GREY_500
                    )
                ], spacing=2, expand=True)
            ], spacing=8))
        
        if not activity_items:
            activity_items = [ft.Text("No activity yet", size=12, color=Colors.GREY_500)]
        
        activity_section = ft.Container(
            content=ft.Column([
                ft.Text("Activity Timeline", size=14, weight=FontWeight.BOLD),
                ft.Divider(height=1),
                ft.Column(activity_items, spacing=8)
            ], spacing=8),
            padding=16,
            bgcolor=Colors.GREY_50,
            border_radius=8
        )
        
        # Action buttons
        def close_dialog(e):
            dialog.open = False
            self.page.update()
        
        def update_status(e):
            self._show_update_job_status_dialog(full_job)
            close_dialog(e)
        
        def add_note(e):
            self._show_add_note_dialog(full_job)
            close_dialog(e)
        
        def mark_complete(e):
            self._show_job_completion_checklist(full_job)
            close_dialog(e)
        
        def reschedule(e):
            self._show_reschedule_dialog(full_job)
            close_dialog(e)
        
        actions = ft.Row([
            ft.TextButton("Close", on_click=close_dialog),
            ft.Container(expand=True),
            ft.ElevatedButton("Reschedule", icon=ft.Icons.CALENDAR_MONTH, on_click=reschedule),
            ft.ElevatedButton("Add Note", icon=ft.Icons.NOTE_ADD, on_click=add_note),
            ft.ElevatedButton("Update Status", icon=ft.Icons.UPDATE, on_click=update_status),
            ft.ElevatedButton(
                "Mark Complete",
                icon=ft.Icons.CHECK_CIRCLE,
                bgcolor=Colors.GREEN_600,
                color=Colors.WHITE,
                on_click=mark_complete
            ) if full_job.status in ["in_progress", "inspection"] else ft.Container()
        ])
        
        # Build dialog content
        content = ft.Container(
            content=ft.Column([
                job_info,
                ft.Row([crew_section, notes_section], spacing=12, expand=True),
                documents_section,
                activity_section,
                actions
            ], spacing=12, scroll=ScrollMode.AUTO),
            width=800,
            height=600,
            padding=20
        )
        
        dialog = ft.AlertDialog(
            title=ft.Text(f"Job Details: {full_job.project_name}"),
            content=content,
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_reschedule_dialog(self, job):
        """Show dialog to reschedule a job."""
        from datetime import datetime, date
        
        # Parse current scheduled date
        current_date_str = ""
        if job.scheduled_date:
            try:
                current_date = datetime.fromisoformat(job.scheduled_date).date()
                current_date_str = current_date.strftime("%Y-%m-%d")
            except:
                current_date_str = job.scheduled_date[:10]
        
        # Date picker (using text field for now - Flet doesn't have a built-in date picker)
        scheduled_date_field = ft.TextField(
            label="Scheduled Date (YYYY-MM-DD)",
            value=current_date_str,
            hint_text="2024-01-15",
            width=300
        )
        
        start_date_str = ""
        if job.start_date:
            try:
                start_date = datetime.fromisoformat(job.start_date).date()
                start_date_str = start_date.strftime("%Y-%m-%d")
            except:
                start_date_str = job.start_date[:10]
        
        start_date_field = ft.TextField(
            label="Start Date (YYYY-MM-DD)",
            value=start_date_str,
            hint_text="2024-01-15",
            width=300
        )
        
        completion_date_str = ""
        if job.completion_date:
            try:
                completion_date = datetime.fromisoformat(job.completion_date).date()
                completion_date_str = completion_date.strftime("%Y-%m-%d")
            except:
                completion_date_str = job.completion_date[:10]
        
        completion_date_field = ft.TextField(
            label="Completion Date (YYYY-MM-DD)",
            value=completion_date_str,
            hint_text="2024-01-20",
            width=300
        )
        
        def save_dates(e):
            if self.job_repo:
                try:
                    # Update job dates
                    self.job_repo.update_job_dates(
                        job.job_id,
                        scheduled_date=scheduled_date_field.value or None,
                        start_date=start_date_field.value or None,
                        completion_date=completion_date_field.value or None
                    )
                    
                    dialog.open = False
                    
                    # Refresh calendar and jobs view
                    self.module_views["calendar"] = self._build_calendar_view()
                    self.module_views["jobs"] = self._build_jobs_view()
                    if self.active_module in ["calendar", "jobs"]:
                        self._set_active_module(self.active_module)
                    
                    self._show_feedback_dialog("Job rescheduled successfully", Colors.GREEN, "Success")
                except Exception as ex:
                    self._show_feedback_dialog(f"Error rescheduling job: {str(ex)}", Colors.RED, "Error")
            
            self.page.update()
        
        def cancel(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text(f"Reschedule Job: {job.project_name}"),
            content=ft.Column([
                ft.Text("Update job timeline dates:", size=13, color=Colors.GREY_600),
                scheduled_date_field,
                start_date_field,
                completion_date_field,
                ft.Container(
                    content=ft.Text(
                        "💡 Tip: Leave fields empty to clear dates",
                        size=11,
                        color=Colors.GREY_500,
                        italic=True
                    ),
                    padding=ft.padding.only(top=8)
                )
            ], spacing=12, tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton("Save", icon=ft.Icons.SAVE, on_click=save_dates)
            ],
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_update_job_status_dialog(self, job):
        """Show dialog to update job status."""
        status_options = [
            "awaiting_approval",
            "scheduled",
            "in_progress",
            "inspection",
            "completed",
            "invoiced"
        ]
        
        status_dropdown = ft.Dropdown(
            label="New Status",
            value=job.status,
            options=[ft.dropdown.Option(s, s.replace("_", " ").title()) for s in status_options],
            width=300
        )
        
        note_field = ft.TextField(
            label="Note (optional)",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=300
        )
        
        def save_status(e):
            if self.job_repo and self.current_user_id:
                self.job_repo.update_job_status(
                    job.job_id,
                    self.current_user_id,
                    status_dropdown.value,
                    note_field.value or None
                )
                dialog.open = False
                # Refresh jobs view
                self.module_views["jobs"] = self._build_jobs_view()
                if self.active_module == "jobs":
                    self._set_active_module("jobs")
                self._show_feedback_dialog("Job status updated", Colors.GREEN, "Success")
            self.page.update()
        
        def cancel(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Update Job Status"),
            content=ft.Column([status_dropdown, note_field], spacing=12, tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton("Save", on_click=save_status)
            ],
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_add_note_dialog(self, job):
        """Show dialog to add a note to a job."""
        note_field = ft.TextField(
            label="Note",
            multiline=True,
            min_lines=3,
            max_lines=6,
            width=400
        )
        
        def save_note(e):
            if self.job_repo and self.current_user_id and note_field.value:
                self.job_repo.add_note(job.job_id, self.current_user_id, note_field.value)
                dialog.open = False
                self._show_feedback_dialog("Note added", Colors.GREEN, "Success")
            self.page.update()
        
        def cancel(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Add Note"),
            content=note_field,
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton("Save", on_click=save_note)
            ],
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_assign_crew_dialog(self, job):
        """Show dialog to assign crew members to a job."""
        current_crew = set(job.crew_list)
        
        # Worker selection checkboxes
        worker_checks = []
        for worker in self.workers:
            cb = ft.Checkbox(
                label=worker["name"],
                value=worker["name"] in current_crew
            )
            worker_checks.append(cb)
        
        def save_crew(e):
            if self.job_repo and self.current_user_id:
                # Get selected crew members
                selected_crew = [cb.label for cb in worker_checks if cb.value]
                
                self.job_repo.assign_crew(
                    job.job_id,
                    self.current_user_id,
                    selected_crew
                )
                
                dialog.open = False
                # Refresh jobs view
                self.module_views["jobs"] = self._build_jobs_view()
                if self.active_module == "jobs":
                    self._set_active_module("jobs")
                self._show_feedback_dialog("Crew assigned", Colors.GREEN, "Success")
            self.page.update()
        
        def cancel(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Assign Crew"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Select crew members:", size=12),
                    ft.Divider(height=1),
                    ft.Column(worker_checks, spacing=4)
                ], spacing=8, tight=True),
                width=300
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton("Save", on_click=save_crew)
            ],
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _upload_job_document(self, job):
        """Trigger file picker for uploading job documents/photos."""
        self.current_upload_job_id = job.job_id
        
        # Show dialog to select document type/tag
        tag_dropdown = ft.Dropdown(
            label="Document Type",
            options=[
                ft.dropdown.Option("before", "Before Photo"),
                ft.dropdown.Option("during", "During Photo"),
                ft.dropdown.Option("after", "After Photo"),
                ft.dropdown.Option("inspection", "Inspection Report"),
                ft.dropdown.Option("issue", "Issue/Problem"),
                ft.dropdown.Option("other", "Other Document")
            ],
            value="other",
            width=300
        )
        
        def select_file(e):
            self.current_upload_tag = tag_dropdown.value
            dialog.open = False
            self.page.update()
            # Trigger file picker
            self.job_document_picker.pick_files(
                allow_multiple=True,
                dialog_title="Select Documents/Photos"
            )
        
        def cancel(e):
            dialog.open = False
            self.current_upload_job_id = None
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Upload Document"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Select the type of document you're uploading:", size=12),
                    tag_dropdown
                ], spacing=12, tight=True),
                width=350
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton("Select Files", icon=ft.Icons.FOLDER_OPEN, on_click=select_file)
            ],
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_job_document_selected(self, e: ft.FilePickerResultEvent):
        """Handle job document/photo upload."""
        if not e.files or not self.current_upload_job_id:
            return
        
        try:
            import shutil
            from pathlib import Path
            
            # Create job documents directory
            job_dir = Path(f"data/jobs/{self.current_upload_job_id}")
            job_dir.mkdir(parents=True, exist_ok=True)
            
            uploaded_count = 0
            for file in e.files:
                # Copy file to job directory
                source_path = Path(file.path)
                dest_path = job_dir / source_path.name
                
                shutil.copy2(source_path, dest_path)
                
                # Determine document type
                doc_type = "photo" if source_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif'] else "document"
                
                # Save to database
                if self.job_repo and self.current_user_id:
                    self.job_repo.add_document(
                        self.current_upload_job_id,
                        self.current_user_id,
                        doc_type,
                        str(dest_path),
                        getattr(self, 'current_upload_tag', None)
                    )
                    uploaded_count += 1
            
            self._show_feedback_dialog(f"Uploaded {uploaded_count} document(s)", Colors.GREEN, "Success")
            
            # Refresh jobs view
            self.module_views["jobs"] = self._build_jobs_view()
            if self.active_module == "jobs":
                self._set_active_module("jobs")
            
        except Exception as ex:
            self._show_feedback_dialog(f"Failed to upload: {str(ex)}", Colors.RED, "Error")
        finally:
            self.current_upload_job_id = None
            self.page.update()
    
    def _show_job_completion_checklist(self, job):
        """Show job completion checklist dialog."""
        # Reload job with full details
        full_job = self.job_repo.get_job(job.job_id) if self.job_repo else None
        if not full_job:
            return
        
        # Build checklist items
        materials_cb = ft.Checkbox(label="All materials installed", value=False)
        photos_cb = ft.Checkbox(
            label="Photos uploaded",
            value=len(full_job.documents) > 0,
            disabled=len(full_job.documents) > 0
        )
        inspection_cb = ft.Checkbox(label="Inspection passed", value=False)
        invoice_cb = ft.Checkbox(label="Ready to invoice", value=False)
        
        checklist = ft.Column([
            ft.Text("Complete the following checklist:", size=13, weight=FontWeight.BOLD),
            ft.Divider(height=1),
            materials_cb,
            photos_cb,
            ft.Text(f"({len(full_job.documents)} document(s) uploaded)", size=10, color=Colors.GREY_500),
            inspection_cb,
            invoice_cb
        ], spacing=8)
        
        def complete_job(e):
            # Check if all items are checked
            if not all([materials_cb.value, photos_cb.value, inspection_cb.value, invoice_cb.value]):
                self._show_feedback_dialog("Please complete all checklist items before marking as complete.", Colors.AMBER_300, "Warning")
                return
            
            # Update job status to completed
            if self.job_repo and self.current_user_id:
                self.job_repo.update_job_status(
                    job.job_id,
                    self.current_user_id,
                    "completed",
                    "Job marked as complete via checklist"
                )
                
                dialog.open = False
                self._show_feedback_dialog("Job marked as complete!", Colors.GREEN, "Success")
                
                # Show financial input dialog
                self._show_financial_input_dialog(job)
                
                # Refresh jobs view
                self.module_views["jobs"] = self._build_jobs_view()
                if self.active_module == "jobs":
                    self._set_active_module("jobs")
            
            self.page.update()
        
        def cancel(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text(f"Complete Job: {full_job.project_name}"),
            content=ft.Container(
                content=checklist,
                width=400
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton(
                    "Mark Complete",
                    icon=ft.Icons.CHECK_CIRCLE,
                    bgcolor=Colors.GREEN_600,
                    color=Colors.WHITE,
                    on_click=complete_job
                )
            ],
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_job_actions(self, job):
        """Show action menu for a job."""
        # Placeholder - will be implemented next
        self._show_feedback_dialog("Job actions coming soon!", Colors.BLUE, "Info")
    
    def _build_dashboard_view(self) -> ft.Control:
        """Build the main dashboard with KPIs and business overview."""
        if not self.current_user_id or not self.job_repo:
            return self._build_placeholder_view(
                "Dashboard", 
                "Please log in to view your business dashboard."
            )
        
        try:
            from datetime import datetime
            
            # Get current month metrics
            now = datetime.now()
            all_jobs = self.job_repo.get_all_jobs(self.current_user_id)
            active_jobs = [j for j in all_jobs if j.status in ["scheduled", "in_progress", "inspection"]]
            
            # Calculate basic metrics
            active_jobs_count = len(active_jobs)
            completed_jobs_count = len([j for j in all_jobs if j.status in ["completed", "invoiced"]])
            
            # Calculate revenue and profit (simplified - only from loaded jobs)
            total_revenue = sum(j.bid_amount or 0 for j in all_jobs if j.is_complete)
            
            # Calculate profit from jobs with financials
            total_profit = 0
            for job in all_jobs:
                if job.is_complete:
                    financials = self.job_repo.get_job_financials(job.job_id)
                    if financials:
                        if financials.net_profit is not None:
                            total_profit += financials.net_profit
                        else:
                            # Fallback: compute from available cost fields
                            costs = [
                                financials.actual_materials_cost,
                                financials.actual_labor_cost,
                                financials.overhead_cost,
                                financials.tools_rental_cost,
                                financials.shipping_cost,
                                financials.tax_amount,
                                financials.commission_amount,
                                financials.other_costs,
                            ]
                            total_costs = sum(c for c in costs if c is not None)
                            total_profit += (financials.bid_amount - total_costs)
            
            profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            # Calculate deadline metrics
            from datetime import date, timedelta
            today = date.today()
            upcoming_deadline_jobs = []
            overdue_jobs = []
            todays_jobs = []
            
            for job in active_jobs:
                # Check for jobs today
                if job.scheduled_date:
                    try:
                        job_date = datetime.fromisoformat(job.scheduled_date).date()
                        
                        if job_date == today and job.status in ["scheduled", "in_progress"]:
                            todays_jobs.append(job)
                        
                        # Check for overdue (completion date passed but not completed)
                        if job.completion_date:
                            completion_date = datetime.fromisoformat(job.completion_date).date()
                            if completion_date < today and job.status not in ["completed", "invoiced"]:
                                overdue_jobs.append(job)
                        # Check for upcoming deadlines (within 7 days)
                        elif job_date > today and job_date <= today + timedelta(days=7):
                            upcoming_deadline_jobs.append(job)
                    except:
                        pass
            
            # Build KPI cards
            kpi_cards = ft.Row([
                self._build_kpi_card(
                    "Total Revenue",
                    f"${total_revenue:,.0f}",
                    "This Month",
                    ft.Icons.ATTACH_MONEY,
                    Colors.BLUE_500
                ),
                self._build_kpi_card(
                    "Net Profit",
                    f"${total_profit:,.0f}",
                    "This Month",
                    ft.Icons.TRENDING_UP,
                    Colors.GREEN_500
                ),
                self._build_kpi_card(
                    "Active Jobs",
                    str(active_jobs_count),
                    "In Progress",
                    ft.Icons.WORK,
                    Colors.ORANGE_500
                ),
                self._build_kpi_card(
                    "Profit Margin",
                    f"{profit_margin:.1f}%",
                    "Avg Margin",
                    ft.Icons.PERCENT,
                    Colors.PURPLE_500 if profit_margin > 20 else Colors.AMBER_500
                )
            ], spacing=16, scroll=ScrollMode.AUTO)
            
            # Deadline alerts section
            deadline_alerts = []
            
            # Overdue jobs alert
            if overdue_jobs:
                overdue_items = []
                for job in overdue_jobs[:3]:  # Show up to 3
                    overdue_items.append(
                        ft.Row([
                            ft.Icon(ft.Icons.ERROR, size=16, color=Colors.RED_500),
                            ft.Text(
                                job.project_name or f"Job #{job.job_id}",
                                size=12,
                                color=Colors.GREY_800,
                                weight=FontWeight.BOLD
                            ),
                            ft.Container(expand=True),
                            ft.Text(
                                "OVERDUE",
                                size=10,
                                color=Colors.WHITE,
                                weight=FontWeight.BOLD
                            )
                        ], spacing=8)
                    )
                
                if len(overdue_jobs) > 3:
                    overdue_items.append(
                        ft.Text(f"+{len(overdue_jobs) - 3} more overdue", size=10, color=Colors.RED_700, italic=True)
                    )
                
                deadline_alerts.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.WARNING, size=20, color=Colors.RED_500),
                                ft.Text(
                                    f"{len(overdue_jobs)} Overdue Job{'s' if len(overdue_jobs) != 1 else ''}",
                                    size=14,
                                    weight=FontWeight.BOLD,
                                    color=Colors.RED_900
                                )
                            ], spacing=8),
                            ft.Column(overdue_items, spacing=6)
                        ], spacing=8),
                        padding=12,
                        bgcolor=Colors.RED_500 + "20",  # 20% opacity
                        border=ft.border.all(2, Colors.RED_500),
                        border_radius=8
                    )
                )
            
            # Today's schedule
            if todays_jobs:
                todays_items = []
                for job in todays_jobs[:3]:
                    todays_items.append(
                        ft.Row([
                            ft.Icon(ft.Icons.TODAY, size=16, color=Colors.BLUE_700),
                            ft.Text(
                                job.project_name or f"Job #{job.job_id}",
                                size=12,
                                color=Colors.GREY_800
                            ),
                            ft.Container(expand=True),
                            ft.Text(
                                job.status_display,
                                size=10,
                                color=Colors.BLUE_700
                            )
                        ], spacing=8)
                    )
                
                if len(todays_jobs) > 3:
                    todays_items.append(
                        ft.Text(f"+{len(todays_jobs) - 3} more today", size=10, color=Colors.BLUE_700, italic=True)
                    )
                
                deadline_alerts.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.EVENT, size=20, color=Colors.BLUE_700),
                                ft.Text(
                                    f"Today's Schedule ({len(todays_jobs)} job{'s' if len(todays_jobs) != 1 else ''})",
                                    size=14,
                                    weight=FontWeight.BOLD,
                                    color=Colors.BLUE_900
                                )
                            ], spacing=8),
                            ft.Column(todays_items, spacing=6)
                        ], spacing=8),
                        padding=12,
                        bgcolor=Colors.BLUE_500 + "20",
                        border=ft.border.all(2, Colors.BLUE_500),
                        border_radius=8
                    )
                )
            
            # Upcoming deadlines
            if upcoming_deadline_jobs:
                upcoming_items = []
                for job in upcoming_deadline_jobs[:3]:
                    try:
                        job_date = datetime.fromisoformat(job.scheduled_date).date()
                        days_until = (job_date - today).days
                        upcoming_items.append(
                            ft.Row([
                                ft.Icon(ft.Icons.EVENT_NOTE, size=16, color=Colors.YELLOW_500),
                                ft.Text(
                                    job.project_name or f"Job #{job.job_id}",
                                    size=12,
                                    color=Colors.GREY_800
                                ),
                                ft.Container(expand=True),
                                ft.Text(
                                    f"in {days_until} day{'s' if days_until != 1 else ''}",
                                    size=10,
                                    color=Colors.YELLOW_500
                                )
                            ], spacing=8)
                        )
                    except:
                        pass
                
                if len(upcoming_deadline_jobs) > 3:
                    upcoming_items.append(
                        ft.Text(f"+{len(upcoming_deadline_jobs) - 3} more upcoming", size=10, color=Colors.YELLOW_500, italic=True)
                    )
                
                deadline_alerts.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.SCHEDULE, size=20, color=Colors.YELLOW_500),
                                ft.Text(
                                    f"Upcoming Deadlines (Next 7 Days)",
                                    size=14,
                                    weight=FontWeight.BOLD,
                                    color=Colors.GREY_900
                                )
                            ], spacing=8),
                            ft.Column(upcoming_items, spacing=6)
                        ], spacing=8),
                        padding=12,
                        bgcolor=Colors.YELLOW_500 + "20",
                        border=ft.border.all(2, Colors.YELLOW_500),
                        border_radius=8
                    )
                )
            
            # Recent activity section
            recent_jobs = active_jobs[:5]
            activity_items = []
            for job in recent_jobs:
                status_colors = {
                    "scheduled": Colors.BLUE_100,
                    "in_progress": Colors.ORANGE_100,
                    "inspection": Colors.PURPLE_100,
                    "completed": Colors.GREEN_100
                }
                
                activity_items.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                width=4,
                                height=40,
                                bgcolor=status_colors.get(job.status, Colors.GREY_300),
                                border_radius=2
                            ),
                            ft.Column([
                                ft.Text(job.project_name or f"Job #{job.job_id}", weight=FontWeight.BOLD, size=13),
                                ft.Text(job.status_display, size=11, color=Colors.GREY_600),
                                ft.Text(
                                    f"${job.bid_amount:,.2f}" if job.bid_amount else "N/A",
                                    size=11,
                                    color=Colors.GREY_600
                                )
                            ], spacing=2, expand=True)
                        ], spacing=12),
                        padding=12,
                        bgcolor=Colors.WHITE,
                        border=ft.border.all(1, Colors.GREY_300),
                        border_radius=8
                    )
                )
            
            if not activity_items:
                activity_items = [
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.INBOX, size=48, color=Colors.GREY_400),
                            ft.Text("No recent jobs", size=13, color=Colors.GREY_500)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        padding=40
                    )
                ]
            
            recent_activity = ft.Container(
                content=ft.Column([
                    ft.Text("Recent Activity", size=16, weight=FontWeight.BOLD),
                    ft.Divider(height=1),
                    ft.Column(activity_items, spacing=8)
                ], spacing=12),
                padding=16,
                bgcolor=Colors.WHITE,
                border=ft.border.all(1, Colors.GREY_300),
                border_radius=12
            )
            
            # Quick actions section
            quick_actions = ft.Container(
                content=ft.Column([
                    ft.Text("Quick Actions", size=16, weight=FontWeight.BOLD),
                    ft.Divider(height=1),
                    ft.Column([
                        ft.ElevatedButton(
                            "Create New Bid",
                            icon=ft.Icons.ADD_CIRCLE,
                            on_click=lambda e: self._set_active_module("bidding"),
                            width=200
                        ),
                        ft.ElevatedButton(
                            "View All Jobs",
                            icon=ft.Icons.WORK,
                            on_click=lambda e: self._set_active_module("jobs"),
                            width=200
                        ),
                        ft.ElevatedButton(
                            "Bid Settings",
                            icon=ft.Icons.SETTINGS,
                            on_click=self._show_labor_settings_dialog,
                            width=200
                        )
                    ], spacing=8)
                ], spacing=12),
                padding=16,
                bgcolor=Colors.WHITE,
                border=ft.border.all(1, Colors.GREY_300),
                border_radius=12
            )
            
            # Build dashboard layout
            return ft.Container(
                content=ft.Column([
                    # Welcome message
                    ft.Container(
                        content=ft.Column([
                            ft.Text(
                                f"Welcome back! 👋",
                                size=24,
                                weight=FontWeight.BOLD
                            ),
                            ft.Text(
                                f"Here's your business overview for {now.strftime('%B %Y')}",
                                size=13,
                                color=Colors.GREY_600
                            )
                        ], spacing=4),
                        padding=ft.padding.only(bottom=20)
                    ),
                    
                    # KPI Cards
                    kpi_cards,
                    
                    # Deadline Alerts (if any)
                    ft.Column(deadline_alerts, spacing=12) if deadline_alerts else ft.Container(),
                    
                    # Bottom section: Recent Activity + Quick Actions
                    ft.Row([
                        ft.Container(content=recent_activity, expand=2),
                        ft.Container(content=quick_actions, expand=1)
                    ], spacing=16, expand=True, scroll=ScrollMode.AUTO)
                ], spacing=20, scroll=ScrollMode.AUTO, expand=True),
                expand=True
            )
            
        except Exception as e:
            return self._build_placeholder_view(
                "Dashboard Error",
                f"Error loading dashboard: {str(e)}"
            )
    
    def _build_kpi_card(
        self,
        title: str,
        value: str,
        subtitle: str,
        icon: str,
        color: str
    ) -> ft.Container:
        """Build a KPI card for the dashboard."""
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, size=32, color=color),
                    ft.Container(expand=True),
                ]),
                ft.Text(value, size=28, weight=FontWeight.BOLD, color=Colors.GREY_900),
                ft.Text(title, size=13, weight=FontWeight.W_500, color=Colors.GREY_700),
                ft.Text(subtitle, size=11, color=Colors.GREY_500)
            ], spacing=8),
            padding=20,
            bgcolor=Colors.WHITE,
            border=ft.border.all(1, Colors.GREY_300),
            border_radius=12,
            expand=True,
            height=160
        )
    
    def _convert_bid_to_job(self, e):
        """Convert the current bid to a job."""
        if not self.current_bid_id or not self.job_repo or not self.current_user_id:
            self._show_feedback_dialog("No bid available to convert. Please save the bid first.", Colors.RED, "Error")
            return
        
        # Worker selection checkboxes
        worker_checks = []
        for worker in self.workers:
            cb = ft.Checkbox(label=worker["name"], value=False)
            worker_checks.append(cb)
        
        crew_section = ft.Column([
            ft.Text("Assign Crew:", size=12, weight=FontWeight.BOLD),
            ft.Text("Select crew members to assign to this job", size=11, color=Colors.GREY_600),
            ft.Column(worker_checks, spacing=4)
        ], spacing=8)
        
        def create_job(e):
            # Get selected crew members
            selected_crew = [cb.label for cb in worker_checks if cb.value]
            
            # Create job (no scheduled date yet - will be set upon approval)
            try:
                job_id = self.job_repo.create_job_from_bid(
                    self.current_bid_id,
                    self.current_user_id,
                    scheduled_date=None,  # No date yet - set upon approval
                    assigned_crew=selected_crew if selected_crew else None
                )
                
                # Update bid status to 'accepted'
                if self.repo:
                    from datetime import datetime
                    now = datetime.now().strftime("%Y-%m-%d")
                    self.repo.update_bid_status(
                        self.current_bid_id,
                        "accepted",
                        date_sent=now,
                        date_responded=now
                    )
                
                dialog.open = False
                self._show_feedback_dialog(
                    f"Job #{job_id} created and placed in 'Awaiting Approval' status.\nApprove the job to schedule it.",
                    Colors.GREEN,
                    "Success"
                )
                
                # Refresh jobs view and switch to it
                self.module_views["jobs"] = self._build_jobs_view()
                self.module_views["dashboard"] = self._build_dashboard_view()
                self._set_active_module("jobs")
                
            except Exception as ex:
                self._show_feedback_dialog(f"Failed to create job: {str(ex)}", Colors.RED, "Error")
            
            self.page.update()
        
        def cancel(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Convert Bid to Job"),
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=20, color=Colors.AMBER_600),
                            ft.Column([
                                ft.Text("This will create a job in 'Awaiting Approval' status.", size=12, weight=FontWeight.BOLD),
                                ft.Text("You can approve and schedule the job later.", size=11, color=Colors.GREY_600)
                            ], spacing=2, expand=True)
                        ], spacing=8),
                        padding=12,
                        bgcolor=Colors.AMBER_50,
                        border_radius=8,
                        margin=ft.margin.only(bottom=12)
                    ),
                    ft.Text(
                        f"Project: {self.current_bid.project_name}",
                        size=13,
                        weight=FontWeight.BOLD,
                        color=Colors.GREY_800
                    ),
                    ft.Text(
                        f"Bid Amount: ${self.current_bid.final_bid_amount:,.2f}" if self.current_bid else "Bid Amount: N/A",
                        size=12,
                        color=Colors.GREY_600
                    ),
                    ft.Divider(height=1),
                    crew_section
                ], spacing=12, tight=True),
                width=450
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton("Create Job", icon=ft.Icons.CHECK, on_click=create_job)
            ],
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_financial_input_dialog(self, job):
        """Show dialog to enter actual costs for completed job."""
        if not self.job_repo or not self.current_user_id:
            return
        
        # Get job with bid details
        full_job = self.job_repo.get_job(job.job_id)
        if not full_job:
            return
        
        # Check if financials already exist
        existing_fin = self.job_repo.get_job_financials(job.job_id)
        if not existing_fin and full_job.bid_amount:
            # Create initial financial record with bid estimates
            self.job_repo.create_job_financials(
                job.job_id,
                full_job.bid_amount,
                0,  # estimated materials (from bid)
                0,  # estimated labor hours
                0   # estimated labor cost
            )
            existing_fin = self.job_repo.get_job_financials(job.job_id)
        
        # Build input fields
        materials_field = ft.TextField(
            label="Actual Materials Cost ($)",
            value=str(existing_fin.actual_materials_cost) if existing_fin and existing_fin.actual_materials_cost else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200
        )
        
        labor_hours_field = ft.TextField(
            label="Actual Labor Hours",
            value=str(existing_fin.actual_labor_hours) if existing_fin and existing_fin.actual_labor_hours else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200
        )
        
        labor_cost_field = ft.TextField(
            label="Actual Labor Cost ($)",
            value=str(existing_fin.actual_labor_cost) if existing_fin and existing_fin.actual_labor_cost else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200
        )
        
        overhead_field = ft.TextField(
            label="Overhead Cost ($)",
            value=str(existing_fin.overhead_cost) if existing_fin and existing_fin.overhead_cost else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200
        )
        
        tools_field = ft.TextField(
            label="Tools & Rental ($)",
            value=str(existing_fin.tools_rental_cost) if existing_fin and existing_fin.tools_rental_cost else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200
        )
        
        shipping_field = ft.TextField(
            label="Shipping Cost ($)",
            value=str(existing_fin.shipping_cost) if existing_fin and existing_fin.shipping_cost else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200
        )
        
        tax_field = ft.TextField(
            label="Tax Amount ($)",
            value=str(existing_fin.tax_amount) if existing_fin and existing_fin.tax_amount else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200
        )
        
        commission_field = ft.TextField(
            label="Commission ($)",
            value=str(existing_fin.commission_amount) if existing_fin and existing_fin.commission_amount else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200
        )
        
        other_field = ft.TextField(
            label="Other Costs ($)",
            value=str(existing_fin.other_costs) if existing_fin and existing_fin.other_costs else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200
        )
        
        def save_financials(e):
            try:
                # Parse and save actual costs
                actual_costs = {
                    'actual_materials_cost': float(materials_field.value) if materials_field.value else 0,
                    'actual_labor_hours': float(labor_hours_field.value) if labor_hours_field.value else 0,
                    'actual_labor_cost': float(labor_cost_field.value) if labor_cost_field.value else 0,
                    'overhead_cost': float(overhead_field.value) if overhead_field.value else 0,
                    'tools_rental_cost': float(tools_field.value) if tools_field.value else 0,
                    'shipping_cost': float(shipping_field.value) if shipping_field.value else 0,
                    'tax_amount': float(tax_field.value) if tax_field.value else 0,
                    'commission_amount': float(commission_field.value) if commission_field.value else 0,
                    'other_costs': float(other_field.value) if other_field.value else 0
                }
                
                self.job_repo.update_job_financials(job.job_id, actual_costs)
                
                dialog.open = False
                self._show_feedback_dialog("Financial data saved", Colors.GREEN, "Success")
                # Refresh dashboard to reflect updated profit
                self.module_views["dashboard"] = self._build_dashboard_view()
                if self.active_module == "dashboard":
                    self._set_active_module("dashboard")
                self.page.update()
                
            except ValueError:
                self._show_feedback_dialog("Please enter valid numbers", Colors.RED, "Error")
        
        def skip(e):
            dialog.open = False
            self.page.update()
        
        content = ft.Container(
            content=ft.Column([
                ft.Text(
                    f"Enter actual costs for: {full_job.project_name}",
                    size=13,
                    color=Colors.GREY_700
                ),
                ft.Text(
                    f"Bid Amount: ${full_job.bid_amount:,.2f}" if full_job.bid_amount else "N/A",
                    size=12,
                    weight=FontWeight.BOLD,
                    color=Colors.BLUE_700
                ),
                ft.Divider(height=1),
                ft.Row([materials_field, labor_hours_field], spacing=12),
                ft.Row([labor_cost_field, overhead_field], spacing=12),
                ft.Row([tools_field, shipping_field], spacing=12),
                ft.Row([tax_field, commission_field], spacing=12),
                other_field
            ], spacing=12, scroll=ScrollMode.AUTO),
            width=450,
            height=500
        )
        
        dialog = ft.AlertDialog(
            title=ft.Text("Enter Actual Costs"),
            content=content,
            actions=[
                ft.TextButton("Skip for Now", on_click=skip),
                ft.ElevatedButton("Save", icon=ft.Icons.SAVE, on_click=save_financials)
            ],
            modal=True
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _build_placeholder_view(self, title: str, description: str) -> ft.Control:
        """Simple placeholder content for future modules."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(title, size=18, weight=FontWeight.BOLD),
                    ft.Text(description, size=12, color=Colors.GREY_600),
                ],
                spacing=8
            ),
            padding=20,
            bgcolor=Colors.WHITE,
            border=ft.border.all(1, Colors.GREY_300),
            border_radius=10,
            expand=True
        )

    def _set_active_module(self, module_key: str, update: bool = True):
        """Switch the active module content."""
        self.active_module = module_key
        if self.content_container:
            self.content_container.content = self._build_module_layout(module_key)
        if update:
            self.page.update()

    def _nav_index_from_key(self, module_key: str) -> int:
        for i, item in enumerate(self.nav_items):
            if item["key"] == module_key:
                return i
        return 0

    def _on_nav_change(self, e):
        idx = e.control.selected_index
        if 0 <= idx < len(self.nav_items):
            self._set_active_module(self.nav_items[idx]["key"])

    def _toggle_nav(self, e):
        self.nav_collapsed = not self.nav_collapsed
        if self.nav_rail:
            self.nav_rail.extended = not self.nav_collapsed
        if self.left_nav_container:
            self.left_nav_container.width = 72 if self.nav_collapsed else 220
        self.page.update()

    def _ensure_file_pickers_in_overlay(self):
        """Ensure file pickers are attached to the page overlay."""
        for picker in [
            getattr(self, "excel_file_picker", None),
            getattr(self, "pdf_file_picker", None),
            getattr(self, "excel_save_picker", None),
            getattr(self, "pdf_save_picker", None),
            getattr(self, "job_document_picker", None),
        ]:
            if picker and picker not in self.page.overlay:
                self.page.overlay.append(picker)
    
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
        
        # Job document/photo picker (for job uploads)
        self.job_document_picker = ft.FilePicker(
            on_result=self._on_job_document_selected
        )
        self.current_upload_job_id = None  # Track which job we're uploading to
        
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
            padding=16,
            bgcolor=Colors.WHITE,
            border=ft.border.all(1, Colors.GREY_300),
            border_radius=12
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
        
        # Bid history selector (DB-backed)
        self.bid_history_dropdown = ft.Dropdown(
            label="Bid History",
            options=[],
            width=300
        )
        
        self.load_bid_btn = ft.ElevatedButton(
            "Load Bid",
            on_click=self._load_selected_bid
        )
        
        # Recent bids list (DB-backed)
        self.recent_bids_list = ft.ListView(
            height=160,
            spacing=6,
            padding=6
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
                    ,
                    ft.Row([
                        self.bid_history_dropdown,
                        self.load_bid_btn
                    ], spacing=10)
                    ,
                    ft.Text("Recent Bids", weight=FontWeight.BOLD, size=14),
                    self.recent_bids_list
                ],
                spacing=10
            ),
            padding=16,
            bgcolor=Colors.WHITE,
            border=ft.border.all(1, Colors.GREY_300),
            border_radius=12
        )
    
    def _build_actions_section(self) -> ft.Container:
        """Build action buttons section."""
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
            content=ft.Row(
                [
                    self.labor_settings_btn,
                    self.calculate_btn
                ],
                spacing=10
            ),
            padding=16,
            bgcolor=Colors.WHITE,
            border=ft.border.all(1, Colors.GREY_300),
            border_radius=12
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
        
        # Convert to Job button (Phase 1: Job Management)
        self.convert_to_job_btn = ft.ElevatedButton(
            "✅ Convert to Job",
            icon=ft.Icons.WORK,
            on_click=self._convert_bid_to_job,
            disabled=True,
            bgcolor=Colors.GREEN_600,
            color=Colors.WHITE
        )
        
        # Build export buttons row (always include, just disabled initially)
        export_buttons_row = ft.Row([
            self.export_excel_btn,
            self.export_pdf_btn,
            ft.Container(width=20),  # Spacer
            self.convert_to_job_btn
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
            padding=16,
            bgcolor=Colors.WHITE,
            border=ft.border.all(1, Colors.GREY_300),
            border_radius=12
        )
    
    # --- EVENT HANDLERS ---
    
    # File Input Handlers
    def _on_excel_selected(self, e: ft.FilePickerResultEvent):
        """Handle Excel file selection and automatically load it."""
        try:
            if e.files and len(e.files) > 0:
                file_path = e.files[0].path
                self.excel_file_path = Path(file_path)
                self.excel_file_text.value = f"Selected: {e.files[0].name}"
                self.excel_file_text.color = Colors.GREEN
                self.page.update()
                
                # Automatically load the Excel file
                self._load_excel(e)
        except Exception as ex:
            self._show_feedback_dialog(f"Error selecting file: {str(ex)}", Colors.RED)
    
    def _on_pdf_selected(self, e: ft.FilePickerResultEvent):
        """Handle PDF file selection and automatically parse it."""
        try:
            if e.files and len(e.files) > 0:
                file_path = e.files[0].path
                self.pdf_file_path = Path(file_path)
                self.pdf_file_text.value = f"Selected: {e.files[0].name}"
                self.pdf_file_text.color = Colors.GREEN
                self.page.update()
                
                # Automatically parse the PDF file
                self._parse_pdf(e)
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
        
        # Auto-save session after any project field change (TEMP until DB migration)
        self._save_session(reason="project_field_change")
        # Refresh bid history list if possible
        self._refresh_bid_history()
    
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
        """Parse PDF and extract project data with live progress indicator."""
        if not self.pdf_file_path or not self.pdf_file_path.exists():
            self._show_feedback_dialog("Please select a PDF file first", Colors.RED)
            return
        
        # Create progress dialog components
        self.pdf_progress_bar = ft.ProgressBar(width=400, value=0)
        self.pdf_progress_text = ft.Text(
            "Starting PDF analysis...", 
            size=14, 
            text_align=ft.TextAlign.CENTER
        )
        self.pdf_progress_percentage = ft.Text(
            "0%", 
            size=24, 
            weight=FontWeight.BOLD, 
            color=Colors.BLUE_700
        )
        
        progress_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.SEARCH, color=Colors.BLUE_700),
                ft.Text("Searching PDF", size=18, weight=FontWeight.BOLD)
            ], spacing=10),
            content=ft.Container(
                content=ft.Column([
                    self.pdf_progress_percentage,
                    self.pdf_progress_bar,
                    self.pdf_progress_text,
                    ft.Text(
                        "Using optimized PyMuPDF parser",
                        size=12,
                        color=Colors.GREY_600,
                        italic=True
                    )
                ], 
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15,
                tight=True),
                padding=20,
                width=450
            ),
        )
        
        self.page.overlay.append(progress_dlg)
        progress_dlg.open = True
        self.page.update()
        
        def update_progress(current: int, total: int, message: str):
            """Callback to update progress UI."""
            try:
                self.pdf_progress_bar.value = current / 100
                self.pdf_progress_percentage.value = f"{current}%"
                self.pdf_progress_text.value = message
                self.page.update()
            except Exception:
                pass  # Ignore UI update errors
        
        try:
            print(f"\n{'='*60}")
            print(f"PARSING PDF: {self.pdf_file_path.name}")
            print(f"{'='*60}")
            
            # Extract data from PDF with progress callback
            extracted_data = parse_pdf_flexible(
                self.pdf_file_path, 
                progress_callback=update_progress
            )
            
            # Get extraction time from metadata
            extraction_time = extracted_data.get("extraction_metadata", {}).get(
                "extraction_time_seconds", 0
            )
            
            print(f"{'='*60}\n")
            
            # Update project fields with extracted data
            dims_found = False
            
            if extracted_data["project_info"]["project_name"]:
                self.project_name_field.value = extracted_data["project_info"]["project_name"]
                self.project_data["project_name"] = extracted_data["project_info"]["project_name"]
            
            dims = extracted_data["building_dimensions"]
            if dims["height"]:
                self.height_field.value = str(dims["height"])
                self._validate_dimension_field(
                    str(dims["height"]),
                    "height",
                    self.height_field,
                    self.height_error,
                    "building_height_ft"
                )
                dims_found = True
            
            if dims["area"]:
                self.area_field.value = str(dims["area"])
                self._validate_dimension_field(
                    str(dims["area"]),
                    "area",
                    self.area_field,
                    self.area_error,
                    "roof_area_sqft"
                )
                dims_found = True
            
            if dims["perimeter"]:
                self.perimeter_field.value = str(dims["perimeter"])
                self._validate_dimension_field(
                    str(dims["perimeter"]),
                    "perimeter",
                    self.perimeter_field,
                    self.perimeter_error,
                    "perimeter_ft"
                )
                dims_found = True
            
            # Material preferences
            mat_prefs = extracted_data["material_preferences"]
            if mat_prefs["preferred_material"]:
                self.material_dropdown.value = mat_prefs["preferred_material"]
                self.project_data["preferred_material"] = mat_prefs["preferred_material"]
            
            if mat_prefs["has_metal_roof"]:
                self.metal_roof_checkbox.value = True
                self.project_data["has_metal_roof"] = True
            
            # Update corners
            if extracted_data.get("num_corners"):
                self.corners_field.value = str(extracted_data["num_corners"])
                self.project_data["num_corners"] = extracted_data["num_corners"]
            
            # Close progress dialog
            progress_dlg.open = False
            self.page.update()
            
            # Show appropriate success message
            if dims_found:
                self._show_feedback_dialog(
                    f"PDF parsed successfully in {extraction_time:.1f} seconds!\n"
                    f"Dimensions extracted from {self.pdf_file_path.name}",
                    Colors.GREEN
                )
            else:
                # No dimensions found - CAD drawing with embedded graphics
                self._show_feedback_dialog(
                    f"PDF scanned in {extraction_time:.1f} seconds.\n\n"
                    f"This appears to be a CAD drawing with dimensions embedded in graphics.\n"
                    f"Please enter the building dimensions manually:\n"
                    f"- Height, Area, Perimeter from the floor plan",
                    Colors.AMBER_700,
                    title="Manual Entry Needed"
                )
            
            self.page.update()
            
            # Auto-save session after successful parse
            self._save_session(reason="pdf_parsed")
            
        except Exception as ex:
            # Close progress dialog
            progress_dlg.open = False
            self.page.update()
            
            print(f"\n[ERROR] PDF Parsing failed: {ex}\n")
            import traceback
            traceback.print_exc()
            
            error_message = (
                "We couldn't parse the PDF. The file may be scanned-only, "
                "corrupted, or protected."
            )
            
            def retry_parse(_):
                error_dialog.open = False
                self.page.update()
                self._parse_pdf(None)
            
            def choose_another(_):
                error_dialog.open = False
                self.page.update()
                self.pdf_file_picker.pick_files(
                    allowed_extensions=["pdf"],
                    dialog_title="Select PDF Specification File"
                )
            
            def cancel(_):
                error_dialog.open = False
                self.page.update()
            
            error_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("PDF Parse Error"),
                content=ft.Text(f"{error_message}\n\nDetails: {str(ex)[:120]}"),
                actions=[
                    ft.TextButton("Cancel", on_click=cancel),
                    ft.TextButton("Choose Another", on_click=choose_another),
                    ft.ElevatedButton("Retry", on_click=retry_parse, bgcolor=Colors.BLUE_700, color=Colors.WHITE),
                ],
                actions_alignment=MainAxisAlignment.END,
            )
            self.page.overlay.append(error_dialog)
            error_dialog.open = True
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
            
            # Auto-save session after successful load (TEMP until DB migration)
            self._save_session(reason="excel_loaded")
            
            # Update calculate button state (checks both pricing and validation)
            self._update_calculate_button_state()
            
            self.page.update()
            
        except Exception as ex:
            self.page.splash = None
            error_message = (
                "We couldn't load the Excel pricing file. The file may be corrupted, "
                "locked by another program, or missing required columns."
            )
            
            def retry_load(_):
                error_dialog.open = False
                self.page.update()
                self._load_excel(None)
            
            def choose_another(_):
                error_dialog.open = False
                self.page.update()
                self.excel_file_picker.pick_files(
                    allowed_extensions=["xlsx", "xls"],
                    dialog_title="Select Excel Pricing File"
                )
            
            def cancel(_):
                error_dialog.open = False
                self.page.update()
            
            error_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Excel Load Error"),
                content=ft.Text(f"{error_message}\n\nDetails: {str(ex)[:120]}"),
                actions=[
                    ft.TextButton("Cancel", on_click=cancel),
                    ft.TextButton("Choose Another", on_click=choose_another),
                    ft.ElevatedButton("Retry", on_click=retry_load, bgcolor=Colors.BLUE_700, color=Colors.WHITE),
                ],
                actions_alignment=MainAxisAlignment.END,
            )
            self.page.overlay.append(error_dialog)
            error_dialog.open = True
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
            
            # Guard: if no sections/items were generated, stop and warn user
            if not self.current_bid.sections:
                self.page.splash = None
                self._show_feedback_dialog(
                    "No bid items were generated. Check your inputs and pricing catalog.",
                    Colors.RED
                )
                self.page.update()
                return
            
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
            
            # Persist bid to DB (SaaS-ready repo layer)
            if self.repo and self.current_user_id:
                project_id = self.repo.get_or_create_project(
                    self.current_user_id,
                    self.project_data.get("project_name", "Untitled Project"),
                    self.project_data
                )
                self.current_bid_id = self.repo.create_bid(
                    self.current_user_id,
                    project_id,
                    self.current_bid,
                    self.workers
                )
                self._refresh_bid_history()
                self._refresh_recent_bids()
            
            # Auto-save session after calculation (TEMP until DB migration)
            self._save_session(reason="bid_calculated")
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
        self.convert_to_job_btn.disabled = False
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
            
            # Track last export + autosave (TEMP until DB migration)
            self.last_excel_export = str(excel_output)
            self._save_session(reason="excel_exported")
            
            if self.repo and self.current_user_id and self.current_bid_id:
                self.repo.save_export(self.current_bid_id, "excel", str(excel_output))
        except PermissionError:
            self._show_feedback_dialog(
                "Excel export failed: file is open or you don't have permission. "
                "Close the file or choose another location.",
                Colors.RED
            )
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
            
            # Track last export + autosave (TEMP until DB migration)
            self.last_pdf_export = str(pdf_output)
            self._save_session(reason="pdf_exported")
            
            if self.repo and self.current_user_id and self.current_bid_id:
                self.repo.save_export(self.current_bid_id, "pdf", str(pdf_output))
        except PermissionError:
            self._show_feedback_dialog(
                "PDF export failed: file is open or you don't have permission. "
                "Close the file or choose another location.",
                Colors.RED
            )
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
            # Auto-save after worker changes (TEMP until DB migration)
            self._save_session(reason="worker_added")
        
        def remove_worker(idx):
            """Remove a worker from the list."""
            if len(self.workers) > 1:  # Keep at least one worker
                self.workers.pop(idx)
                update_worker_list()
                self.page.update()
                # Auto-save after worker changes (TEMP until DB migration)
                self._save_session(reason="worker_removed")
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
                
                # Auto-save settings (TEMP until DB migration)
                self._save_session(reason="bid_settings_saved")
                
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
            # Auto-save after worker edit (TEMP until DB migration)
            self._save_session(reason="worker_name_changed")
    
    def _update_worker_hours(self, idx: int, hours_str: str):
        """Update worker hours."""
        try:
            hours = float(hours_str)
            if idx < len(self.workers) and hours > 0:
                self.workers[idx]["hours"] = hours
                self._update_worker_total(idx)
                # Auto-save after worker edit (TEMP until DB migration)
                self._save_session(reason="worker_hours_changed")
        except ValueError:
            pass  # Ignore invalid input during typing
    
    def _update_worker_wage(self, idx: int, wage_str: str):
        """Update worker wage."""
        try:
            wage = float(wage_str)
            if idx < len(self.workers) and wage > 0:
                self.workers[idx]["wage_per_hour"] = wage
                self._update_worker_total(idx)
                # Auto-save after worker edit (TEMP until DB migration)
                self._save_session(reason="worker_wage_changed")
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

    # --- DB-backed bid history ---
    def _refresh_bid_history(self):
        """Refresh bid history dropdown based on customer + project."""
        if not self.repo or not self.current_user_id:
            return
        if not hasattr(self, "bid_history_dropdown"):
            return
        
        project_name = (self.project_data.get("project_name") or "").strip()
        if not project_name:
            self.bid_history_dropdown.options = []
            if self.bid_history_dropdown.page:
                self.bid_history_dropdown.update()
            return
        
        try:
            project_id = self.repo.get_or_create_project(
                self.current_user_id,
                project_name,
                self.project_data
            )
            bids = self.repo.list_bids(self.current_user_id, project_id)
            options = []
            for bid in bids:
                label = f"{bid['created_at']} - ${bid['final_amount']:.2f}"
                options.append(ft.dropdown.Option(str(bid["bid_id"]), label))
            self.bid_history_dropdown.options = options
            if self.bid_history_dropdown.page:
                self.bid_history_dropdown.update()
        except Exception:
            # Ignore history refresh failures
            pass
    
    def _refresh_recent_bids(self):
        """Refresh recent bids list (works even without customer/project inputs)."""
        if not self.repo or not self.current_user_id or not hasattr(self, "recent_bids_list"):
            return
        try:
            recent = self.repo.list_recent_bids(self.current_user_id, limit=10)
            self.recent_bids_list.controls.clear()
            if not recent:
                self.recent_bids_list.controls.append(
                    ft.Text("No recent bids yet.", color=Colors.GREY_600)
                )
            else:
                for item in recent:
                    label = f"{item['created_at']} • {item['project_name']} • ${item['final_amount']:.2f}"
                    load_btn = ft.TextButton(
                        "Load",
                        on_click=lambda e, bid_id=item["bid_id"]: self._load_recent_bid(bid_id)
                    )
                    self.recent_bids_list.controls.append(
                        ft.Row([ft.Text(label, expand=True), load_btn], alignment=MainAxisAlignment.SPACE_BETWEEN)
                    )
            self.recent_bids_list.update()
        except Exception:
            pass
    
    def _load_recent_bid(self, bid_id: int):
        """Load a bid selected from the recent list."""
        if not self.repo or not self.current_user_id:
            return
        try:
            data = self.repo.load_bid(bid_id)
            if not data:
                self._show_feedback_dialog("Selected bid not found.", Colors.RED)
                return
            
            self._apply_session_data({
                "project_data": data["project_data"],
                "workers": data["workers"],
                "pricing_settings": data["settings"],
                "file_paths": {},
                "last_exports": {},
            })
            self.current_bid = data["bid"]
            self.current_bid_id = bid_id
            self._update_bid_display()
            self._refresh_recent_bids()
            self._show_feedback_dialog("Bid loaded from history.", Colors.GREEN)
        except Exception as ex:
            self._show_feedback_dialog(f"Error loading bid: {str(ex)[:100]}", Colors.RED)
    
    def _load_selected_bid(self, e):
        """Load a selected bid from history into the UI."""
        if not self.repo or not self.current_user_id:
            return
        if not self.bid_history_dropdown.value:
            self._show_feedback_dialog("Select a bid from history first.", Colors.AMBER_600)
            return
        
        try:
            bid_id = int(self.bid_history_dropdown.value)
            data = self.repo.load_bid(bid_id)
            if not data:
                self._show_feedback_dialog("Selected bid not found.", Colors.RED)
                return
            
            self._apply_session_data({
                "project_data": data["project_data"],
                "workers": data["workers"],
                "pricing_settings": data["settings"],
                "file_paths": {},
                "last_exports": {},
            })
            self.current_bid = data["bid"]
            self.current_bid_id = bid_id
            self._update_bid_display()
            self._show_feedback_dialog("Bid loaded from history.", Colors.GREEN)
        except Exception as ex:
            self._show_feedback_dialog(f"Error loading bid: {str(ex)[:100]}", Colors.RED)
    
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

