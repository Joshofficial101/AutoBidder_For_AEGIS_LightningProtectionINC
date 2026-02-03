"""
Calendar View Component for Job Scheduling

Provides month, week, and day views for visualizing and managing job schedules.
"""

import flet as ft
from datetime import datetime, date, timedelta
from typing import List, Dict, Callable, Optional
from calendar import monthrange, month_name, day_name
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.models.job import Job


class Colors:
    """Color constants matching the main app theme."""
    WHITE = "#FFFFFF"
    GREY_50 = "#F9FAFB"
    GREY_100 = "#F3F4F6"
    GREY_200 = "#E5E7EB"
    GREY_300 = "#D1D5DB"
    GREY_400 = "#9CA3AF"
    GREY_500 = "#6B7280"
    GREY_600 = "#4B5563"
    GREY_700 = "#374151"
    GREY_800 = "#1F2937"
    BLUE_50 = "#EFF6FF"
    BLUE_500 = "#3B82F6"
    BLUE_700 = "#1D4ED8"
    ORANGE_50 = "#FFF7ED"
    ORANGE_500 = "#F97316"
    PURPLE_50 = "#FAF5FF"
    PURPLE_500 = "#A855F7"
    GREEN_50 = "#F0FDF4"
    GREEN_500 = "#22C55E"
    GREEN_700 = "#15803D"
    RED_500 = "#EF4444"
    YELLOW_500 = "#EAB308"


class CalendarView:
    """
    A comprehensive calendar component with multiple view modes.
    """
    
    def __init__(
        self,
        on_date_click: Optional[Callable] = None,
        on_job_click: Optional[Callable] = None,
        initial_date: Optional[date] = None
    ):
        """
        Initialize the calendar view.
        
        Args:
            on_date_click: Callback when a date is clicked (receives date object)
            on_job_click: Callback when a job card is clicked (receives Job object)
            initial_date: Starting date for the calendar (defaults to today)
        """
        self.on_date_click = on_date_click
        self.on_job_click = on_job_click
        self.current_date = initial_date or date.today()
        self.view_mode = "month"  # month, week, or day
        self.jobs_data: List[Job] = []
        self.filter_status: Optional[str] = None
        self.filter_crew: Optional[str] = None
        
        # UI Controls
        self.calendar_container: Optional[ft.Container] = None
        self.view_mode_selector: Optional[ft.SegmentedButton] = None
        self.month_year_text: Optional[ft.Text] = None
    
    def set_jobs(self, jobs: List[Job]):
        """Update the jobs data and refresh the calendar."""
        self.jobs_data = jobs
    
    def get_filtered_jobs(self) -> List[Job]:
        """Get jobs filtered by current filter settings."""
        filtered = self.jobs_data
        
        if self.filter_status:
            filtered = [j for j in filtered if j.status == self.filter_status]
        
        if self.filter_crew:
            filtered = [j for j in filtered if self.filter_crew in (j.assigned_crew or "")]
        
        return filtered
    
    def get_jobs_for_date(self, target_date: date) -> List[Job]:
        """Get all jobs scheduled for a specific date."""
        date_str = target_date.strftime("%Y-%m-%d")
        jobs = []
        
        for job in self.get_filtered_jobs():
            # Check if job falls on this date
            if job.scheduled_date and job.scheduled_date.startswith(date_str):
                jobs.append(job)
            elif job.start_date and job.start_date.startswith(date_str):
                jobs.append(job)
            elif job.completion_date and job.completion_date.startswith(date_str):
                jobs.append(job)
        
        return jobs
    
    def get_status_color(self, status: str) -> tuple[str, str]:
        """Get background and text color for a status."""
        status_colors = {
            "scheduled": (Colors.BLUE_50, Colors.BLUE_700),
            "in_progress": (Colors.ORANGE_50, Colors.ORANGE_500),
            "inspection": (Colors.PURPLE_50, Colors.PURPLE_500),
            "completed": (Colors.GREEN_50, Colors.GREEN_700),
        }
        return status_colors.get(status, (Colors.GREY_100, Colors.GREY_700))
    
    def build(self) -> ft.Container:
        """Build and return the calendar view container."""
        # Header with navigation and view switcher
        header = self._build_header()
        
        # Calendar content based on view mode
        if self.view_mode == "month":
            calendar_content = self._build_month_view()
        elif self.view_mode == "week":
            calendar_content = self._build_week_view()
        else:  # day
            calendar_content = self._build_day_view()
        
        self.calendar_container = ft.Container(
            content=ft.Column(
                [header, calendar_content],
                spacing=0,
                expand=True
            ),
            expand=True
        )
        
        return self.calendar_container
    
    def _build_header(self) -> ft.Container:
        """Build the calendar header with navigation and controls."""
        # Month/Year display
        if self.view_mode == "month":
            title = f"{month_name[self.current_date.month]} {self.current_date.year}"
        elif self.view_mode == "week":
            week_start = self.current_date - timedelta(days=self.current_date.weekday())
            week_end = week_start + timedelta(days=6)
            title = f"Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
        else:
            title = self.current_date.strftime("%A, %B %d, %Y")
        
        self.month_year_text = ft.Text(
            title,
            size=24,
            weight=ft.FontWeight.BOLD,
            color=Colors.GREY_800
        )
        
        # Navigation buttons
        prev_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            on_click=self._on_prev_period,
            tooltip="Previous"
        )
        
        today_btn = ft.TextButton(
            "Today",
            on_click=self._on_today_click,
            tooltip="Jump to today"
        )
        
        next_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            on_click=self._on_next_period,
            tooltip="Next"
        )
        
        # View mode selector
        self.view_mode_selector = ft.SegmentedButton(
            selected={"month"},
            allow_empty_selection=False,
            allow_multiple_selection=False,
            segments=[
                ft.Segment(value="month", label=ft.Text("Month"), icon=ft.Icon(ft.Icons.CALENDAR_VIEW_MONTH)),
                ft.Segment(value="week", label=ft.Text("Week"), icon=ft.Icon(ft.Icons.CALENDAR_VIEW_WEEK)),
                ft.Segment(value="day", label=ft.Text("Day"), icon=ft.Icon(ft.Icons.CALENDAR_VIEW_DAY)),
            ],
            on_change=self._on_view_mode_change
        )
        
        # Filter controls
        status_filter = ft.Dropdown(
            label="Filter by Status",
            hint_text="All Statuses",
            value=self.filter_status,
            options=[
                ft.dropdown.Option("", "All Statuses"),
                ft.dropdown.Option("scheduled", "Scheduled"),
                ft.dropdown.Option("in_progress", "In Progress"),
                ft.dropdown.Option("inspection", "Inspection"),
                ft.dropdown.Option("completed", "Completed"),
            ],
            width=180,
            on_change=self._on_status_filter_change
        )
        
        # Get unique crew names from jobs
        crew_names = set()
        for job in self.jobs_data:
            if job.assigned_crew:
                try:
                    import json
                    crew_list = json.loads(job.assigned_crew) if isinstance(job.assigned_crew, str) else job.assigned_crew
                    if isinstance(crew_list, list):
                        crew_names.update(crew_list)
                except:
                    pass
        
        crew_options = [ft.dropdown.Option("", "All Crew")]
        for crew_name in sorted(crew_names):
            crew_options.append(ft.dropdown.Option(crew_name, crew_name))
        
        crew_filter = ft.Dropdown(
            label="Filter by Crew",
            hint_text="All Crew",
            value=self.filter_crew,
            options=crew_options,
            width=180,
            on_change=self._on_crew_filter_change
        )
        
        # Clear filters button
        clear_filters_btn = ft.TextButton(
            "Clear Filters",
            icon=ft.Icons.CLEAR,
            on_click=self._on_clear_filters,
            visible=(self.filter_status is not None or self.filter_crew is not None)
        )
        
        return ft.Container(
            content=ft.Column([
                # Top row: Navigation and view selector
                ft.Row(
                    [
                        # Left side: Navigation
                        ft.Row(
                            [prev_btn, today_btn, next_btn, self.month_year_text],
                            spacing=8,
                            alignment=ft.MainAxisAlignment.START
                        ),
                        # Right side: View selector
                        self.view_mode_selector
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                # Bottom row: Filters
                ft.Row(
                    [
                        ft.Icon(ft.Icons.FILTER_ALT, size=20, color=Colors.GREY_600),
                        status_filter,
                        crew_filter,
                        clear_filters_btn
                    ],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.START
                )
            ], spacing=12),
            padding=16,
            bgcolor=Colors.WHITE,
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.GREY_300))
        )
    
    def _build_month_view(self) -> ft.Container:
        """Build the month grid view."""
        year = self.current_date.year
        month = self.current_date.month
        
        # Get first day of month and number of days
        first_day_weekday = date(year, month, 1).weekday()
        num_days = monthrange(year, month)[1]
        
        # Build header row with day names
        day_headers = []
        for i in range(7):
            day_headers.append(
                ft.Container(
                    content=ft.Text(
                        day_name[i][:3],  # Mon, Tue, etc.
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=Colors.GREY_600,
                        text_align=ft.TextAlign.CENTER
                    ),
                    expand=True,
                    alignment=ft.alignment.center,
                    padding=8
                )
            )
        
        header_row = ft.Row(day_headers, spacing=0, expand=True)
        
        # Build calendar grid
        calendar_rows = []
        current_day = 1
        
        for week in range(6):  # Max 6 weeks in a month
            week_cells = []
            
            for weekday in range(7):
                # Calculate which day this cell represents
                cell_position = week * 7 + weekday
                
                if cell_position < first_day_weekday or current_day > num_days:
                    # Empty cell (padding)
                    week_cells.append(
                        ft.Container(
                            expand=True,
                            bgcolor=Colors.GREY_50,
                            border=ft.border.all(1, Colors.GREY_200)
                        )
                    )
                else:
                    # Day cell with jobs
                    day_date = date(year, month, current_day)
                    jobs_on_date = self.get_jobs_for_date(day_date)
                    
                    week_cells.append(
                        self._build_day_cell(day_date, jobs_on_date)
                    )
                    current_day += 1
            
            calendar_rows.append(
                ft.Row(week_cells, spacing=0, expand=True)
            )
            
            if current_day > num_days:
                break
        
        return ft.Container(
            content=ft.Column(
                [header_row] + calendar_rows,
                spacing=0,
                expand=True
            ),
            expand=True,
            bgcolor=Colors.WHITE
        )
    
    def _build_day_cell(self, day_date: date, jobs: List[Job]) -> ft.Container:
        """Build a single day cell for the month view."""
        is_today = day_date == date.today()
        is_weekend = day_date.weekday() >= 5
        
        # Day number
        day_number = ft.Text(
            str(day_date.day),
            size=14,
            weight=ft.FontWeight.BOLD if is_today else ft.FontWeight.NORMAL,
            color=Colors.BLUE_700 if is_today else (Colors.GREY_500 if is_weekend else Colors.GREY_800)
        )
        
        # Job indicators (show up to 3 jobs as colored dots)
        job_indicators = []
        for i, job in enumerate(jobs[:3]):
            if i >= 3:
                break
            bg_color, text_color = self.get_status_color(job.status)
            job_indicators.append(
                ft.Container(
                    content=ft.Text(
                        job.project_name[:15] + "..." if len(job.project_name or "") > 15 else (job.project_name or "Job"),
                        size=10,
                        color=text_color,
                        text_align=ft.TextAlign.LEFT,
                        overflow=ft.TextOverflow.ELLIPSIS
                    ),
                    bgcolor=bg_color,
                    padding=ft.padding.symmetric(horizontal=4, vertical=2),
                    border_radius=3,
                    on_click=lambda e, j=job: self._on_job_card_click(j)
                )
            )
        
        # More indicator if there are additional jobs
        if len(jobs) > 3:
            job_indicators.append(
                ft.Text(
                    f"+{len(jobs) - 3} more",
                    size=9,
                    color=Colors.GREY_500,
                    italic=True
                )
            )
        
        cell_content = ft.Column(
            [day_number] + job_indicators,
            spacing=2,
            tight=True
        )
        
        return ft.Container(
            content=cell_content,
            expand=True,
            padding=6,
            bgcolor=Colors.BLUE_50 if is_today else (Colors.GREY_50 if is_weekend else Colors.WHITE),
            border=ft.border.all(
                2 if is_today else 1,
                Colors.BLUE_500 if is_today else Colors.GREY_200
            ),
            on_click=lambda e, d=day_date: self._on_date_cell_click(d),
            alignment=ft.alignment.top_left
        )
    
    def _build_week_view(self) -> ft.Container:
        """Build the week view with day columns."""
        # Get week start (Monday)
        week_start = self.current_date - timedelta(days=self.current_date.weekday())
        
        # Build day columns
        day_columns = []
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            jobs_on_date = self.get_jobs_for_date(day_date)
            is_today = day_date == date.today()
            
            # Day header
            day_header = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            day_name[i][:3],
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=Colors.BLUE_700 if is_today else Colors.GREY_600
                        ),
                        ft.Text(
                            str(day_date.day),
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=Colors.BLUE_700 if is_today else Colors.GREY_800
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2
                ),
                padding=8,
                bgcolor=Colors.BLUE_50 if is_today else Colors.GREY_50,
                border=ft.border.only(bottom=ft.BorderSide(2, Colors.BLUE_500 if is_today else Colors.GREY_300))
            )
            
            # Job cards for this day
            job_cards = []
            for job in jobs_on_date:
                job_cards.append(self._build_job_card(job))
            
            day_column = ft.Container(
                content=ft.Column(
                    [day_header, ft.Column(job_cards, spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)],
                    spacing=0,
                    expand=True
                ),
                expand=True,
                border=ft.border.all(1, Colors.GREY_200),
                on_click=lambda e, d=day_date: self._on_date_cell_click(d)
            )
            
            day_columns.append(day_column)
        
        return ft.Container(
            content=ft.Row(day_columns, spacing=0, expand=True),
            expand=True,
            bgcolor=Colors.WHITE
        )
    
    def _build_day_view(self) -> ft.Container:
        """Build the detailed day view."""
        jobs_on_date = self.get_jobs_for_date(self.current_date)
        
        if not jobs_on_date:
            # Empty state
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.EVENT_AVAILABLE, size=64, color=Colors.GREY_400),
                        ft.Text(
                            "No jobs scheduled for this day",
                            size=18,
                            color=Colors.GREY_500
                        ),
                        ft.ElevatedButton(
                            "Schedule a Job",
                            icon=ft.Icons.ADD,
                            on_click=lambda e: self._on_date_cell_click(self.current_date)
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=16
                ),
                expand=True,
                bgcolor=Colors.WHITE,
                alignment=ft.alignment.center
            )
        
        # List of job cards
        job_cards = []
        for job in jobs_on_date:
            job_cards.append(self._build_job_card(job, detailed=True))
        
        return ft.Container(
            content=ft.Column(
                job_cards,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                expand=True
            ),
            padding=16,
            expand=True,
            bgcolor=Colors.GREY_50
        )
    
    def _build_job_card(self, job: Job, detailed: bool = False) -> ft.Container:
        """Build a job card for display in the calendar."""
        bg_color, text_color = self.get_status_color(job.status)
        
        # Status badge
        status_badge = ft.Container(
            content=ft.Text(
                job.status_display,
                size=10,
                color=Colors.WHITE,
                weight=ft.FontWeight.BOLD
            ),
            bgcolor=text_color,
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            border_radius=4
        )
        
        # Job info
        job_title = ft.Text(
            job.project_name or "Untitled Job",
            size=14 if detailed else 12,
            weight=ft.FontWeight.BOLD,
            color=Colors.GREY_800,
            overflow=ft.TextOverflow.ELLIPSIS
        )
        
        job_details = []
        
        if job.bid_amount:
            job_details.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.ATTACH_MONEY, size=14, color=Colors.GREY_600),
                        ft.Text(f"${job.bid_amount:,.2f}", size=12, color=Colors.GREY_600)
                    ],
                    spacing=4
                )
            )
        
        if job.assigned_crew:
            crew_list = job.crew_list
            if crew_list:
                job_details.append(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.PEOPLE, size=14, color=Colors.GREY_600),
                            ft.Text(", ".join(crew_list[:2]), size=12, color=Colors.GREY_600)
                        ],
                        spacing=4
                    )
                )
        
        card_content = ft.Column(
            [
                ft.Row([job_title, status_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ] + (job_details if detailed else []),
            spacing=4,
            tight=True
        )
        
        return ft.Container(
            content=card_content,
            padding=8 if detailed else 6,
            bgcolor=bg_color,
            border=ft.border.all(1, text_color),
            border_radius=6,
            on_click=lambda e, j=job: self._on_job_card_click(j),
            ink=True
        )
    
    # Event Handlers
    def _on_prev_period(self, e):
        """Navigate to previous period."""
        if self.view_mode == "month":
            # Go to previous month
            if self.current_date.month == 1:
                self.current_date = date(self.current_date.year - 1, 12, 1)
            else:
                self.current_date = date(self.current_date.year, self.current_date.month - 1, 1)
        elif self.view_mode == "week":
            self.current_date = self.current_date - timedelta(days=7)
        else:  # day
            self.current_date = self.current_date - timedelta(days=1)
        
        self.refresh()
    
    def _on_next_period(self, e):
        """Navigate to next period."""
        if self.view_mode == "month":
            # Go to next month
            if self.current_date.month == 12:
                self.current_date = date(self.current_date.year + 1, 1, 1)
            else:
                self.current_date = date(self.current_date.year, self.current_date.month + 1, 1)
        elif self.view_mode == "week":
            self.current_date = self.current_date + timedelta(days=7)
        else:  # day
            self.current_date = self.current_date + timedelta(days=1)
        
        self.refresh()
    
    def _on_today_click(self, e):
        """Jump to today."""
        self.current_date = date.today()
        self.refresh()
    
    def _on_view_mode_change(self, e):
        """Handle view mode change."""
        selected = list(e.control.selected)
        if selected:
            self.view_mode = selected[0]
            self.refresh()
    
    def _on_date_cell_click(self, day_date: date):
        """Handle date cell click."""
        if self.on_date_click:
            self.on_date_click(day_date)
    
    def _on_job_card_click(self, job: Job):
        """Handle job card click."""
        if self.on_job_click:
            self.on_job_click(job)
    
    def _on_status_filter_change(self, e):
        """Handle status filter change."""
        self.filter_status = e.control.value if e.control.value else None
        self.refresh()
    
    def _on_crew_filter_change(self, e):
        """Handle crew filter change."""
        self.filter_crew = e.control.value if e.control.value else None
        self.refresh()
    
    def _on_clear_filters(self, e):
        """Clear all filters."""
        self.filter_status = None
        self.filter_crew = None
        self.refresh()
    
    def refresh(self):
        """Refresh the calendar display."""
        if self.calendar_container and self.calendar_container.page:
            # Rebuild the entire calendar
            new_content = self.build().content
            self.calendar_container.content = new_content
            self.calendar_container.update()
