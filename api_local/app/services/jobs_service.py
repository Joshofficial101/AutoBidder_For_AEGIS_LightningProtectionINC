from datetime import datetime
from typing import Any, Dict, List, Optional

from src.database.db_connector import DBConnector
from src.database.job_repository import JobRepository
from src.models.job import Job

BOARD_STATUSES = (
    "awaiting_approval",
    "scheduled",
    "in_progress",
    "inspection",
    "completed",
    "invoiced",
)
NEXT_STATUS = {
    "scheduled": "in_progress",
    "in_progress": "inspection",
    "inspection": "completed",
    "completed": "invoiced",
}


def _job_to_item(job: Job) -> Dict[str, Any]:
    return {
        "job_id": int(job.job_id or 0),
        "project_name": job.project_name or f"Job #{job.job_id or 0}",
        "status": job.status,
        "status_display": job.status_display,
        "bid_amount": float(job.bid_amount or 0.0),
        "scheduled_date": job.scheduled_date,
        "start_date": job.start_date,
        "completion_date": job.completion_date,
        "invoice_number": job.invoice_number,
        "invoice_date": job.invoice_date,
        "assigned_crew": job.crew_list,
    }


def _normalize_note(note: Optional[str]) -> Optional[str]:
    if note is None:
        return None
    normalized = note.strip()
    return normalized or None


def _require_note(note: Optional[str], transition_label: str) -> str:
    normalized = _normalize_note(note)
    if not normalized:
        raise ValueError(f"note is required for {transition_label}.")
    return normalized


def _parse_date(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return datetime.strptime(stripped, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format.") from exc


def _validate_crew_list(assigned_crew: Optional[List[str]]) -> Optional[List[str]]:
    if assigned_crew is None:
        return None

    normalized = [member.strip() for member in assigned_crew if member and member.strip()]
    if not normalized:
        raise ValueError("assigned_crew must include at least one crew member.")
    return normalized


def get_jobs_board(user_id: int) -> Dict[str, Any]:
    db = DBConnector()
    repo = JobRepository(db)

    jobs = repo.get_all_jobs(user_id)

    jobs_by_status = {status: [] for status in BOARD_STATUSES}
    for job in jobs:
        if job.status in jobs_by_status:
            jobs_by_status[job.status].append(_job_to_item(job))

    return {
        "user_id": user_id,
        "awaiting_approval": jobs_by_status["awaiting_approval"],
        "scheduled": jobs_by_status["scheduled"],
        "in_progress": jobs_by_status["in_progress"],
        "inspection": jobs_by_status["inspection"],
        "completed": jobs_by_status["completed"],
        "invoiced": jobs_by_status["invoiced"],
    }


def move_job_to_status(
    job_id: int,
    new_status: str,
    user_id: int,
    start_date: Optional[str] = None,
    completion_date: Optional[str] = None,
    invoice_date: Optional[str] = None,
    invoice_number: Optional[str] = None,
    assigned_crew: Optional[List[str]] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    if new_status not in BOARD_STATUSES:
        raise ValueError(f"Unsupported board status: {new_status}")

    db = DBConnector()
    repo = JobRepository(db)

    current = repo.get_job(job_id)
    if not current:
        raise ValueError(f"Job {job_id} not found.")
    if current.user_id != user_id:
        raise ValueError(f"Job {job_id} does not belong to user {user_id}.")

    if current.status == new_status:
        return {"user_id": user_id, "job": _job_to_item(current)}

    if current.status == "awaiting_approval" and new_status == "scheduled":
        raise ValueError("Use the approve endpoint for awaiting_approval -> scheduled transition.")

    expected_next = NEXT_STATUS.get(current.status)
    if expected_next != new_status:
        raise ValueError(
            f"Invalid status transition: {current.status} -> {new_status}."
        )

    normalized_start = _parse_date(start_date, "start_date")
    normalized_completion = _parse_date(completion_date, "completion_date")
    normalized_invoice_date = _parse_date(invoice_date, "invoice_date")
    normalized_invoice_number = (invoice_number or "").strip() or None
    normalized_crew = _validate_crew_list(assigned_crew)
    normalized_note = _normalize_note(note)

    if current.status == "scheduled" and new_status == "in_progress":
        if not normalized_start:
            raise ValueError("start_date is required for scheduled -> in_progress transition.")
        if not normalized_note:
            raise ValueError("note is required for scheduled -> in_progress transition.")
        if not normalized_crew and not current.crew_list:
            raise ValueError(
                "assigned_crew is required for scheduled -> in_progress transition."
            )
        if current.scheduled_date:
            scheduled_dt = _parse_date(current.scheduled_date, "scheduled_date")
            if scheduled_dt and normalized_start < scheduled_dt:
                raise ValueError("start_date cannot be earlier than scheduled_date.")

    elif current.status == "in_progress" and new_status == "inspection":
        if not normalized_note:
            raise ValueError("note is required for in_progress -> inspection transition.")

    elif current.status == "inspection" and new_status == "completed":
        if not normalized_completion:
            raise ValueError("completion_date is required for inspection -> completed transition.")
        if not normalized_note:
            raise ValueError("note is required for inspection -> completed transition.")
        start_dt = _parse_date(current.start_date, "start_date")
        if start_dt and normalized_completion < start_dt:
            raise ValueError("completion_date cannot be earlier than start_date.")

    elif current.status == "completed" and new_status == "invoiced":
        if not normalized_invoice_number:
            raise ValueError("invoice_number is required for completed -> invoiced transition.")
        if not normalized_invoice_date:
            raise ValueError("invoice_date is required for completed -> invoiced transition.")
        if not normalized_note:
            raise ValueError("note is required for completed -> invoiced transition.")
        completion_dt = _parse_date(current.completion_date, "completion_date")
        if completion_dt and normalized_invoice_date < completion_dt:
            raise ValueError("invoice_date cannot be earlier than completion_date.")

    if normalized_crew:
        repo.assign_crew(job_id=job_id, user_id=user_id, crew_members=normalized_crew)

    if normalized_start:
        repo.update_job_dates(job_id=job_id, start_date=normalized_start)
    if normalized_completion:
        repo.update_job_dates(job_id=job_id, completion_date=normalized_completion)
    if normalized_invoice_number or normalized_invoice_date:
        updates: Dict[str, Any] = {}
        if normalized_invoice_number:
            updates["invoice_number"] = normalized_invoice_number
        if normalized_invoice_date:
            updates["invoice_date"] = normalized_invoice_date
        repo.update_job(job_id=job_id, updates=updates)

    transition_note = normalized_note or f"Status changed to {new_status.replace('_', ' ')}"
    repo.update_job_status(
        job_id=job_id,
        user_id=user_id,
        new_status=new_status,
        note=transition_note,
    )

    updated = repo.get_job(job_id)
    if not updated:
        raise RuntimeError(f"Failed to reload job {job_id} after status update.")

    return {"user_id": user_id, "job": _job_to_item(updated)}


def approve_and_schedule_job(
    job_id: int,
    scheduled_date: str,
    user_id: int,
    assigned_crew: Optional[List[str]] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_date = _parse_date(scheduled_date, "scheduled_date")
    if not normalized_date:
        raise ValueError("scheduled_date is required for awaiting_approval -> scheduled transition.")

    normalized_note = _require_note(note, "awaiting_approval -> scheduled transition")
    normalized_crew = _validate_crew_list(assigned_crew)
    if not normalized_crew:
        raise ValueError(
            "assigned_crew is required for awaiting_approval -> scheduled transition."
        )

    db = DBConnector()
    repo = JobRepository(db)

    current = repo.get_job(job_id)
    if not current:
        raise ValueError(f"Job {job_id} not found.")
    if current.user_id != user_id:
        raise ValueError(f"Job {job_id} does not belong to user {user_id}.")
    if current.status != "awaiting_approval":
        raise ValueError(
            f"Job {job_id} must be in awaiting_approval status to be approved."
        )

    repo.update_job_dates(job_id=job_id, scheduled_date=normalized_date)
    repo.assign_crew(job_id=job_id, user_id=user_id, crew_members=normalized_crew)
    repo.update_job_status(
        job_id=job_id,
        user_id=user_id,
        new_status="scheduled",
        note=normalized_note,
    )

    updated = repo.get_job(job_id)
    if not updated:
        raise RuntimeError(f"Failed to reload job {job_id} after approval.")

    return {"user_id": user_id, "job": _job_to_item(updated)}
