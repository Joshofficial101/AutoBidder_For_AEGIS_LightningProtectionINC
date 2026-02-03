"""
Crew Schedule View Component

Displays crew member availability and job assignments across a date range.
"""

import flet as ft
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from calendar import monthrange, month_name
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
    GREY_900 = "#111827"
    BLUE_500 = "#3B82F6"
    BLUE_700 = "#1D4ED8"
    ORANGE_500 = "#F97316"
    GREEN_500 = "#22C55E"
    GREEN_700 = "#15803D"
    RED_500 = "#EF4444"
    YELLOW_500 = "#EAB308"


class CrewScheduleView:
    """
    Displays crew member schedules and availability.
    """
    
    def __init__(
        self,
        crew_members: List[str],
        jobs_data: List[Job],
        current_date: Optional[date] = None
    ):
        """
        Initialize crew schedule view.
        
        Args:
            crew_members: List of crew member names
            jobs_data: List of all jobs
            current_date: Starting date (defaults to today)
        """
        self.crew_members = crew_members
        self.jobs_data = jobs_data
        self.current_date = current_date or date.today()
        self.view_days = 14  # Show 2 weeks by default
    
    def get_crew_jobs(self, crew_name: str, start_date: date, end_date: date) -> List[Job]:
        """Get jobs assigned to a crew member in date range."""
        crew_jobs = []
        
        for job in self.jobs_data:
            # Check if crew member is assigned
            if crew_name in (job.assigned_crew or ""):
                # Check if job falls in date range
                if job.scheduled_date:
                    try:
                        job_date = datetime.fromisoformat(job.scheduled_date).date()
                        if start_date <= job_date <= end_date:
                            crew_jobs.append((job_date, job))
                    except:
                        pass
        
        return crew_jobs
    
    def get_availability_status(self, crew_name: str, check_date: date) -> tuple[str, Optional[Job]]:
        """
        Get availability status for a crew member on a specific date.
        
        Returns:
            Tuple of (status, job) where status is:
            - "available": No jobs assigned
            - "scheduled": Job scheduled
            - "in_progress": Job in progress
            - "partial": Some availability (future use)
        """
        for job in self.jobs_data:
            if crew_name in (job.assigned_crew or ""):
                if job.scheduled_date:
                    try:
                        job_date = datetime.fromisoformat(job.scheduled_date).date()
                        if job_date == check_date:
                            if job.status == "in_progress":
                                return ("in_progress", job)
                            elif job.status == "scheduled":
                                return ("scheduled", job)
                    except:
                        pass
        
        return ("available", None)
    
    def build(self) -> ft.Container:
        """Build and return the crew schedule view."""
        if not self.crew_members:
            return ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.PEOPLE_OUTLINE, size=64, color=Colors.GREY_400),
                    ft.Text("No crew members configured", size=16, color=Colors.GREY_500),
                    ft.Text("Add workers in Bid Settings to see their schedules", size=12, color=Colors.GREY_400)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                padding=40,
                alignment=ft.alignment.center,
                expand=True
            )
        
        # Header with date range
        start_date = self.current_date
        end_date = start_date + timedelta(days=self.view_days - 1)
        
        header = ft.Container(
            content=ft.Row([
                ft.Text(
                    f"Crew Schedule: {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}",
                    size=20,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_LEFT,
                    tooltip="Previous",
                    on_click=lambda e: self._shift_dates(-7)
                ),
                ft.TextButton("Today", on_click=lambda e: self._reset_to_today()),
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_RIGHT,
                    tooltip="Next",
                    on_click=lambda e: self._shift_dates(7)
                )
            ]),
            padding=16,
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.GREY_300))
        )
        
        # Build crew schedule grid
        crew_rows = []
        
        for crew_name in self.crew_members:
            # Crew member name cell
            name_cell = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.PERSON, size=16, color=Colors.GREY_600),
                    ft.Text(crew_name, size=13, weight=ft.FontWeight.BOLD, color=Colors.GREY_800)
                ], spacing=8),
                padding=12,
                width=180,
                bgcolor=Colors.GREY_50,
                border=ft.border.all(1, Colors.GREY_300)
            )
            
            # Schedule cells for each day
            day_cells = []
            current = start_date
            
            for day_offset in range(self.view_days):
                check_date = start_date + timedelta(days=day_offset)
                status, job = self.get_availability_status(crew_name, check_date)
                
                # Determine cell color and content
                if status == "in_progress":
                    bgcolor = Colors.RED_500
                    text_color = Colors.WHITE
                    icon = ft.Icons.WORK
                    label = "Busy"
                elif status == "scheduled":
                    bgcolor = Colors.BLUE_500
                    text_color = Colors.WHITE
                    icon = ft.Icons.EVENT
                    label = "Scheduled"
                else:
                    bgcolor = Colors.GREEN_500
                    text_color = Colors.WHITE
                    icon = ft.Icons.CHECK_CIRCLE
                    label = "Available"
                
                # Build cell content
                cell_content = ft.Column([
                    ft.Text(
                        check_date.strftime("%d"),
                        size=10,
                        color=text_color,
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Icon(icon, size=14, color=text_color),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
                
                if job:
                    cell_content = ft.Column([
                        ft.Text(
                            check_date.strftime("%d"),
                            size=10,
                            color=text_color,
                            weight=ft.FontWeight.BOLD
                        ),
                        ft.Icon(icon, size=14, color=text_color),
                        ft.Text(
                            (job.project_name or "Job")[:8],
                            size=9,
                            color=text_color,
                            text_align=ft.TextAlign.CENTER,
                            overflow=ft.TextOverflow.ELLIPSIS
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True)
                
                day_cell = ft.Container(
                    content=cell_content,
                    padding=8,
                    width=70,
                    height=80,
                    bgcolor=bgcolor,
                    border=ft.border.all(1, Colors.GREY_300),
                    alignment=ft.alignment.center,
                    tooltip=f"{crew_name} - {check_date.strftime('%b %d')}: {label}" + (f"\n{job.project_name}" if job else "")
                )
                
                day_cells.append(day_cell)
            
            # Combine name and schedule cells
            crew_row = ft.Row([name_cell] + day_cells, spacing=0)
            crew_rows.append(crew_row)
        
        # Legend
        legend = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Container(width=16, height=16, bgcolor=Colors.GREEN_500, border_radius=2),
                    ft.Text("Available", size=11, color=Colors.GREY_700)
                ], spacing=6),
                ft.Row([
                    ft.Container(width=16, height=16, bgcolor=Colors.BLUE_500, border_radius=2),
                    ft.Text("Scheduled", size=11, color=Colors.GREY_700)
                ], spacing=6),
                ft.Row([
                    ft.Container(width=16, height=16, bgcolor=Colors.RED_500, border_radius=2),
                    ft.Text("Busy", size=11, color=Colors.GREY_700)
                ], spacing=6),
            ], spacing=20),
            padding=16,
            border=ft.border.only(top=ft.BorderSide(1, Colors.GREY_300))
        )
        
        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(
                    content=ft.Column(crew_rows, spacing=4, scroll=ft.ScrollMode.AUTO),
                    expand=True,
                    padding=16
                ),
                legend
            ], spacing=0, expand=True),
            expand=True,
            bgcolor=Colors.WHITE
        )
    
    def _shift_dates(self, days: int):
        """Shift the view by a number of days."""
        self.current_date = self.current_date + timedelta(days=days)
        # Trigger refresh (would need to be implemented with page update)
    
    def _reset_to_today(self):
        """Reset view to today."""
        self.current_date = date.today()
        # Trigger refresh (would need to be implemented with page update)
