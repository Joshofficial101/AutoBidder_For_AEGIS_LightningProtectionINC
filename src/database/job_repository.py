"""
Job Repository - Data access layer for job management.

Provides CRUD operations for Jobs, JobDocuments, JobActivity, and JobFinancials.
This abstraction layer makes the system SaaS-ready by separating data access
from business logic.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from src.database.db_connector import DBConnector
from src.models.job import Job, JobDocument, JobActivity, JobFinancials


class JobRepository:
    """
    Repository for managing job-related data operations.
    
    NOTE: This currently uses SQLite (local DB), but the interface
    is designed to be swappable with a REST API client for SaaS deployment.
    """
    
    def __init__(self, db: DBConnector):
        """Initialize with database connector."""
        self.db = db
    
    # ========================================================================
    # JOB CRUD OPERATIONS
    # ========================================================================
    
    def create_job_from_bid(
        self,
        bid_id: int,
        user_id: int,
        scheduled_date: Optional[str] = None,
        assigned_crew: Optional[List[str]] = None
    ) -> int:
        """
        Create a new job from an accepted bid.
        
        Args:
            bid_id: ID of the accepted bid
            user_id: ID of the user creating the job
            scheduled_date: Optional scheduled date (ISO format)
            assigned_crew: Optional list of worker names
            
        Returns:
            job_id of the created job
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        crew_json = json.dumps(assigned_crew) if assigned_crew else None
        
        sql = """
        INSERT INTO Jobs (
            bid_id, user_id, status, scheduled_date, assigned_crew,
            created_at, updated_at
        ) VALUES (?, ?, 'awaiting_approval', ?, ?, ?, ?);
        """
        
        self.db.execute(sql, (bid_id, user_id, scheduled_date, crew_json, now, now))
        job_id = self.db._cursor.lastrowid
        
        # Log activity
        self._log_activity(job_id, user_id, "job_created", "Job created from bid")
        
        return job_id
    
    def get_job(self, job_id: int) -> Optional[Job]:
        """
        Retrieve a job by ID with all related data.
        
        Args:
            job_id: ID of the job
            
        Returns:
            Job object or None if not found
        """
        sql = """
        SELECT 
            j.job_id, j.bid_id, j.user_id, j.status,
            j.scheduled_date, j.start_date, j.completion_date,
            j.assigned_crew, j.notes, j.created_at, j.updated_at,
            p.name as project_name, b.final_amount as bid_amount
        FROM Jobs j
        JOIN Bids b ON j.bid_id = b.bid_id
        JOIN Projects p ON b.project_id = p.project_id
        WHERE j.job_id = ?;
        """
        
        row = self.db.fetchone(sql, (job_id,))
        if not row:
            return None
        
        # Convert to Job object
        job = Job(
            job_id=row[0],
            bid_id=row[1],
            user_id=row[2],
            status=row[3],
            scheduled_date=row[4],
            start_date=row[5],
            completion_date=row[6],
            assigned_crew=row[7],
            notes=row[8],
            created_at=row[9],
            updated_at=row[10],
            project_name=row[11],
            bid_amount=row[12]
        )
        
        # Load related data
        job.documents = self.get_job_documents(job_id)
        job.activities = self.get_job_activities(job_id)
        job.financials = self.get_job_financials(job_id)
        
        return job
    
    def get_active_jobs(self, user_id: int) -> List[Job]:
        """
        Get all active jobs for a user (scheduled, in_progress, inspection).
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of Job objects
        """
        sql = """
        SELECT 
            j.job_id, j.bid_id, j.user_id, j.status,
            j.scheduled_date, j.start_date, j.completion_date,
            j.assigned_crew, j.notes, j.created_at, j.updated_at,
            p.name as project_name, b.final_amount as bid_amount
        FROM Jobs j
        JOIN Bids b ON j.bid_id = b.bid_id
        JOIN Projects p ON b.project_id = p.project_id
        WHERE j.user_id = ? 
        AND j.status IN ('awaiting_approval', 'scheduled', 'in_progress', 'inspection')
        ORDER BY j.scheduled_date ASC, j.created_at DESC;
        """
        
        rows = self.db.fetchall(sql, (user_id,))
        return [self._row_to_job(row) for row in rows]
    
    def get_jobs_by_status(self, user_id: int, status: str) -> List[Job]:
        """
        Get all jobs for a user with a specific status.
        
        Args:
            user_id: ID of the user
            status: Job status to filter by
            
        Returns:
            List of Job objects
        """
        sql = """
        SELECT 
            j.job_id, j.bid_id, j.user_id, j.status,
            j.scheduled_date, j.start_date, j.completion_date,
            j.assigned_crew, j.notes, j.created_at, j.updated_at,
            p.name as project_name, b.final_amount as bid_amount
        FROM Jobs j
        JOIN Bids b ON j.bid_id = b.bid_id
        JOIN Projects p ON b.project_id = p.project_id
        WHERE j.user_id = ? AND j.status = ?
        ORDER BY j.scheduled_date ASC, j.created_at DESC;
        """
        
        rows = self.db.fetchall(sql, (user_id, status))
        return [self._row_to_job(row) for row in rows]
    
    def get_jobs_by_date_range(
        self,
        user_id: int,
        start_date: str,
        end_date: str
    ) -> List[Job]:
        """
        Get jobs scheduled within a date range.
        
        Args:
            user_id: ID of the user
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            
        Returns:
            List of Job objects
        """
        sql = """
        SELECT 
            j.job_id, j.bid_id, j.user_id, j.status,
            j.scheduled_date, j.start_date, j.completion_date,
            j.assigned_crew, j.notes, j.created_at, j.updated_at,
            p.name as project_name, b.final_amount as bid_amount
        FROM Jobs j
        JOIN Bids b ON j.bid_id = b.bid_id
        JOIN Projects p ON b.project_id = p.project_id
        WHERE j.user_id = ? 
        AND j.scheduled_date BETWEEN ? AND ?
        ORDER BY j.scheduled_date ASC;
        """
        
        rows = self.db.fetchall(sql, (user_id, start_date, end_date))
        return [self._row_to_job(row) for row in rows]
    
    def get_jobs_by_date(self, user_id: int, date: str) -> List[Job]:
        """
        Get all jobs scheduled for a specific date.
        
        Args:
            user_id: ID of the user
            date: Date to query (ISO format, e.g., '2024-01-15')
            
        Returns:
            List of Job objects
        """
        sql = """
        SELECT 
            j.job_id, j.bid_id, j.user_id, j.status,
            j.scheduled_date, j.start_date, j.completion_date,
            j.assigned_crew, j.notes, j.created_at, j.updated_at,
            p.name as project_name, b.final_amount as bid_amount
        FROM Jobs j
        JOIN Bids b ON j.bid_id = b.bid_id
        JOIN Projects p ON b.project_id = p.project_id
        WHERE j.user_id = ? 
        AND DATE(j.scheduled_date) = DATE(?)
        ORDER BY j.scheduled_date ASC;
        """
        
        rows = self.db.fetchall(sql, (user_id, date))
        return [self._row_to_job(row) for row in rows]
    
    def get_crew_schedule(
        self,
        user_id: int,
        crew_name: str,
        start_date: str,
        end_date: str
    ) -> List[Job]:
        """
        Get jobs assigned to a specific crew member in a date range.
        
        Args:
            user_id: ID of the user
            crew_name: Name of the crew member
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            
        Returns:
            List of Job objects assigned to this crew member
        """
        sql = """
        SELECT 
            j.job_id, j.bid_id, j.user_id, j.status,
            j.scheduled_date, j.start_date, j.completion_date,
            j.assigned_crew, j.notes, j.created_at, j.updated_at,
            p.name as project_name, b.final_amount as bid_amount
        FROM Jobs j
        JOIN Bids b ON j.bid_id = b.bid_id
        JOIN Projects p ON b.project_id = p.project_id
        WHERE j.user_id = ? 
        AND j.scheduled_date BETWEEN ? AND ?
        AND j.assigned_crew LIKE ?
        ORDER BY j.scheduled_date ASC;
        """
        
        # Use LIKE to search within JSON array string
        crew_pattern = f"%{crew_name}%"
        rows = self.db.fetchall(sql, (user_id, start_date, end_date, crew_pattern))
        return [self._row_to_job(row) for row in rows]
    
    def update_job_dates(
        self,
        job_id: int,
        scheduled_date: Optional[str] = None,
        start_date: Optional[str] = None,
        completion_date: Optional[str] = None
    ) -> bool:
        """
        Update job timeline dates.
        
        Args:
            job_id: ID of the job
            scheduled_date: New scheduled date (ISO format)
            start_date: New start date (ISO format)
            completion_date: New completion date (ISO format)
            
        Returns:
            True if successful
        """
        updates = {}
        if scheduled_date is not None:
            updates['scheduled_date'] = scheduled_date
        if start_date is not None:
            updates['start_date'] = start_date
        if completion_date is not None:
            updates['completion_date'] = completion_date
        
        return self.update_job(job_id, updates)
    
    def check_crew_availability(
        self,
        user_id: int,
        crew_name: str,
        date: str
    ) -> bool:
        """
        Check if a crew member is available on a specific date.
        
        Args:
            user_id: ID of the user
            crew_name: Name of the crew member
            date: Date to check (ISO format)
            
        Returns:
            True if available (no jobs), False if already assigned
        """
        sql = """
        SELECT COUNT(*) as job_count
        FROM Jobs
        WHERE user_id = ? 
        AND DATE(scheduled_date) = DATE(?)
        AND assigned_crew LIKE ?
        AND status IN ('scheduled', 'in_progress');
        """
        
        crew_pattern = f"%{crew_name}%"
        row = self.db.fetchone(sql, (user_id, date, crew_pattern))
        
        # Available if no jobs found
        return row[0] == 0 if row else True
    
    def update_job_status(
        self,
        job_id: int,
        user_id: int,
        new_status: str,
        note: Optional[str] = None
    ) -> bool:
        """
        Update a job's status and log the activity.
        
        Args:
            job_id: ID of the job
            user_id: ID of the user making the change
            new_status: New status value
            note: Optional note about the status change
            
        Returns:
            True if successful
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update status
        sql = "UPDATE Jobs SET status = ?, updated_at = ? WHERE job_id = ?;"
        self.db.execute(sql, (new_status, now, job_id))
        
        # Update date fields based on status
        if new_status == "in_progress":
            self.db.execute(
                "UPDATE Jobs SET start_date = ? WHERE job_id = ? AND start_date IS NULL;",
                (now, job_id)
            )
        elif new_status in ["completed", "invoiced"]:
            self.db.execute(
                "UPDATE Jobs SET completion_date = ? WHERE job_id = ? AND completion_date IS NULL;",
                (now, job_id)
            )
        
        # Log activity
        description = note if note else f"Status changed to {new_status}"
        self._log_activity(job_id, user_id, "status_change", description)
        
        return True
    
    def assign_crew(
        self,
        job_id: int,
        user_id: int,
        crew_members: List[str]
    ) -> bool:
        """
        Assign crew members to a job.
        
        Args:
            job_id: ID of the job
            user_id: ID of the user making the assignment
            crew_members: List of worker names
            
        Returns:
            True if successful
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        crew_json = json.dumps(crew_members)
        
        sql = "UPDATE Jobs SET assigned_crew = ?, updated_at = ? WHERE job_id = ?;"
        self.db.execute(sql, (crew_json, now, job_id))
        
        # Log activity
        crew_str = ", ".join(crew_members)
        self._log_activity(job_id, user_id, "crew_assigned", f"Crew assigned: {crew_str}")
        
        return True
    
    def update_job(self, job_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update job fields.
        
        Args:
            job_id: ID of the job
            updates: Dictionary of field names and new values
            
        Returns:
            True if successful
        """
        if not updates:
            return True
        
        updates['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        sql = f"UPDATE Jobs SET {set_clause} WHERE job_id = ?;"
        
        values = list(updates.values()) + [job_id]
        self.db.execute(sql, tuple(values))
        
        return True
    
    # ========================================================================
    # JOB DOCUMENTS
    # ========================================================================
    
    def add_document(
        self,
        job_id: int,
        user_id: int,
        document_type: str,
        file_path: str,
        tag: Optional[str] = None
    ) -> int:
        """
        Add a document or photo to a job.
        
        Args:
            job_id: ID of the job
            user_id: ID of the user uploading
            document_type: Type of document (photo, document, inspection_report)
            file_path: Path to the file
            tag: Optional tag (before, during, after, etc.)
            
        Returns:
            document_id of the created document
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        sql = """
        INSERT INTO JobDocuments (job_id, document_type, file_path, tag, uploaded_at)
        VALUES (?, ?, ?, ?, ?);
        """
        
        self.db.execute(sql, (job_id, document_type, file_path, tag, now))
        document_id = self.db._cursor.lastrowid
        
        # Log activity
        self._log_activity(job_id, user_id, "photo_uploaded", f"Uploaded {document_type}: {tag or 'untagged'}")
        
        return document_id
    
    def get_job_documents(self, job_id: int) -> List[JobDocument]:
        """Get all documents for a job."""
        sql = """
        SELECT document_id, job_id, document_type, file_path, tag, uploaded_at
        FROM JobDocuments
        WHERE job_id = ?
        ORDER BY uploaded_at DESC;
        """
        
        rows = self.db.fetchall(sql, (job_id,))
        return [JobDocument(
            document_id=row[0],
            job_id=row[1],
            document_type=row[2],
            file_path=row[3],
            tag=row[4],
            uploaded_at=row[5]
        ) for row in rows]
    
    # ========================================================================
    # JOB ACTIVITY LOG
    # ========================================================================
    
    def _log_activity(
        self,
        job_id: int,
        user_id: int,
        activity_type: str,
        description: str
    ) -> int:
        """Internal method to log job activity."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        sql = """
        INSERT INTO JobActivity (job_id, user_id, activity_type, description, created_at)
        VALUES (?, ?, ?, ?, ?);
        """
        
        self.db.execute(sql, (job_id, user_id, activity_type, description, now))
        return self.db._cursor.lastrowid
    
    def add_note(self, job_id: int, user_id: int, note: str) -> int:
        """Add a note to a job."""
        return self._log_activity(job_id, user_id, "note_added", note)
    
    def get_job_activities(self, job_id: int) -> List[JobActivity]:
        """Get all activities for a job."""
        sql = """
        SELECT activity_id, job_id, user_id, activity_type, description, created_at
        FROM JobActivity
        WHERE job_id = ?
        ORDER BY created_at DESC;
        """
        
        rows = self.db.fetchall(sql, (job_id,))
        return [JobActivity(
            activity_id=row[0],
            job_id=row[1],
            user_id=row[2],
            activity_type=row[3],
            description=row[4],
            created_at=row[5]
        ) for row in rows]
    
    # ========================================================================
    # JOB FINANCIALS
    # ========================================================================
    
    def create_job_financials(
        self,
        job_id: int,
        bid_amount: float,
        estimated_materials: float,
        estimated_labor_hours: float,
        estimated_labor_cost: float
    ) -> int:
        """
        Create financial tracking record for a job.
        
        This is typically called when a job is completed and actual costs
        need to be tracked against the bid estimates.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        sql = """
        INSERT INTO JobFinancials (
            job_id, bid_amount, estimated_materials, estimated_labor_hours,
            estimated_labor_cost, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        
        self.db.execute(sql, (
            job_id, bid_amount, estimated_materials, estimated_labor_hours,
            estimated_labor_cost, now, now
        ))
        
        return self.db._cursor.lastrowid
    
    def update_job_financials(
        self,
        job_id: int,
        actual_costs: Dict[str, float]
    ) -> bool:
        """
        Update actual costs for a job and calculate profit metrics.
        
        Args:
            job_id: ID of the job
            actual_costs: Dictionary of actual cost fields
        """
        # Calculate totals
        total_costs = sum([
            actual_costs.get('actual_materials_cost', 0),
            actual_costs.get('actual_labor_cost', 0),
            actual_costs.get('overhead_cost', 0),
            actual_costs.get('tools_rental_cost', 0),
            actual_costs.get('shipping_cost', 0),
            actual_costs.get('tax_amount', 0),
            actual_costs.get('commission_amount', 0),
            actual_costs.get('other_costs', 0)
        ])
        
        # Get bid amount
        bid_row = self.db.fetchone(
            "SELECT bid_amount FROM JobFinancials WHERE job_id = ?;",
            (job_id,)
        )
        
        if bid_row:
            bid_amount = bid_row[0]
            net_profit = bid_amount - total_costs
            profit_margin = (net_profit / bid_amount * 100) if bid_amount > 0 else 0
            
            actual_costs['total_costs'] = total_costs
            actual_costs['net_profit'] = net_profit
            actual_costs['profit_margin_pct'] = profit_margin
        
        actual_costs['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build UPDATE query
        set_clause = ", ".join([f"{key} = ?" for key in actual_costs.keys()])
        sql = f"UPDATE JobFinancials SET {set_clause} WHERE job_id = ?;"
        
        values = list(actual_costs.values()) + [job_id]
        self.db.execute(sql, tuple(values))
        
        return True
    
    def get_job_financials(self, job_id: int) -> Optional[JobFinancials]:
        """Get financial data for a job."""
        sql = """
        SELECT 
            financial_id, job_id, bid_amount, estimated_materials,
            estimated_labor_hours, estimated_labor_cost, actual_materials_cost,
            actual_labor_hours, actual_labor_cost, overhead_cost, tools_rental_cost,
            shipping_cost, tax_amount, commission_amount, other_costs,
            payment_status, amount_paid, payment_date, total_costs, net_profit,
            profit_margin_pct, created_at, updated_at
        FROM JobFinancials
        WHERE job_id = ?;
        """
        
        row = self.db.fetchone(sql, (job_id,))
        if not row:
            return None
        
        return JobFinancials(
            financial_id=row[0],
            job_id=row[1],
            bid_amount=row[2],
            estimated_materials=row[3],
            estimated_labor_hours=row[4],
            estimated_labor_cost=row[5],
            actual_materials_cost=row[6],
            actual_labor_hours=row[7],
            actual_labor_cost=row[8],
            overhead_cost=row[9],
            tools_rental_cost=row[10],
            shipping_cost=row[11],
            tax_amount=row[12],
            commission_amount=row[13],
            other_costs=row[14],
            payment_status=row[15],
            amount_paid=row[16],
            payment_date=row[17],
            total_costs=row[18],
            net_profit=row[19],
            profit_margin_pct=row[20],
            created_at=row[21],
            updated_at=row[22]
        )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _row_to_job(self, row) -> Job:
        """Convert database row to Job object (without related data)."""
        return Job(
            job_id=row[0],
            bid_id=row[1],
            user_id=row[2],
            status=row[3],
            scheduled_date=row[4],
            start_date=row[5],
            completion_date=row[6],
            assigned_crew=row[7],
            notes=row[8],
            created_at=row[9],
            updated_at=row[10],
            project_name=row[11],
            bid_amount=row[12]
        )
