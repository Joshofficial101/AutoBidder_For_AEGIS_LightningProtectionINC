"""
Pydantic models for Job Management system.

These models represent jobs created from accepted bids, tracking their
lifecycle from scheduling through completion and payment.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class JobDocument(BaseModel):
    """
    Represents a document or photo associated with a job.
    """
    document_id: Optional[int] = None
    job_id: int
    document_type: str  # photo | document | inspection_report
    file_path: str
    tag: Optional[str] = None  # before | during | after | inspection | issue
    uploaded_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class JobActivity(BaseModel):
    """
    Represents an activity or event in a job's timeline.
    """
    activity_id: Optional[int] = None
    job_id: int
    user_id: int
    activity_type: str  # status_change | note_added | photo_uploaded | crew_assigned
    description: Optional[str] = None
    created_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class JobFinancials(BaseModel):
    """
    Financial tracking for a completed job.
    Compares estimated costs from bid vs actual costs.
    """
    financial_id: Optional[int] = None
    job_id: int
    
    # Bid estimates
    bid_amount: float
    estimated_materials: float
    estimated_labor_hours: float
    estimated_labor_cost: float
    
    # Actual costs (filled in upon job completion)
    actual_materials_cost: Optional[float] = None
    actual_labor_hours: Optional[float] = None
    actual_labor_cost: Optional[float] = None
    overhead_cost: Optional[float] = None
    tools_rental_cost: Optional[float] = None
    shipping_cost: Optional[float] = None
    tax_amount: Optional[float] = None
    commission_amount: Optional[float] = None
    other_costs: Optional[float] = None
    
    # Payment tracking
    payment_status: str = "unpaid"  # unpaid | partial | paid
    amount_paid: float = 0.0
    payment_date: Optional[str] = None
    
    # Calculated fields
    total_costs: Optional[float] = None
    net_profit: Optional[float] = None
    profit_margin_pct: Optional[float] = None
    
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    @property
    def calculated_total_costs(self) -> float:
        """Calculate total costs from all actual cost fields."""
        return (
            (self.actual_materials_cost or 0) +
            (self.actual_labor_cost or 0) +
            (self.overhead_cost or 0) +
            (self.tools_rental_cost or 0) +
            (self.shipping_cost or 0) +
            (self.tax_amount or 0) +
            (self.commission_amount or 0) +
            (self.other_costs or 0)
        )
    
    @property
    def calculated_net_profit(self) -> float:
        """Calculate net profit: bid amount minus all costs."""
        return self.bid_amount - self.calculated_total_costs
    
    @property
    def calculated_profit_margin(self) -> float:
        """Calculate profit margin percentage."""
        if self.bid_amount == 0:
            return 0.0
        return (self.calculated_net_profit / self.bid_amount) * 100
    
    class Config:
        from_attributes = True


class Job(BaseModel):
    """
    Represents a job created from an accepted bid.
    Tracks the job lifecycle from scheduling through completion.
    """
    job_id: Optional[int] = None
    bid_id: int
    user_id: int
    
    # Status workflow: awaiting_approval -> scheduled -> in_progress -> inspection -> completed -> invoiced
    status: str = "awaiting_approval"
    
    # Timeline
    scheduled_date: Optional[str] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    
    # Crew assignment (JSON array of worker names/IDs)
    assigned_crew: Optional[str] = None  # Stored as JSON string in DB
    
    # Notes and communication
    notes: Optional[str] = None
    
    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    # Related data (not stored in Jobs table, loaded from joins)
    documents: List[JobDocument] = Field(default_factory=list)
    activities: List[JobActivity] = Field(default_factory=list)
    financials: Optional[JobFinancials] = None
    
    # Denormalized fields from related tables (for display)
    project_name: Optional[str] = None
    bid_amount: Optional[float] = None
    
    class Config:
        from_attributes = True
    
    @property
    def crew_list(self) -> List[str]:
        """Parse assigned_crew JSON string to list."""
        if not self.assigned_crew:
            return []
        import json
        try:
            return json.loads(self.assigned_crew)
        except:
            return []
    
    @property
    def status_display(self) -> str:
        """Human-readable status."""
        status_map = {
            "awaiting_approval": "Awaiting Approval",
            "scheduled": "Scheduled",
            "in_progress": "In Progress",
            "inspection": "Awaiting Inspection",
            "completed": "Completed",
            "invoiced": "Invoiced"
        }
        return status_map.get(self.status, self.status)
    
    @property
    def is_active(self) -> bool:
        """Check if job is currently active."""
        return self.status in ["awaiting_approval", "scheduled", "in_progress", "inspection"]
    
    @property
    def is_complete(self) -> bool:
        """Check if job is complete."""
        return self.status in ["completed", "invoiced"]
