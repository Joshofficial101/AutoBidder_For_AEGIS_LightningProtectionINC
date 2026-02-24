from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from src.database.db_connector import DBConnector
from src.database.job_repository import JobRepository
from src.models.job import Job

ACTIVE_STATUSES = {"awaiting_approval", "scheduled", "in_progress", "inspection"}
COMPLETED_STATUSES = {"completed", "invoiced"}


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


def _job_to_item(job: Job) -> Dict[str, Any]:
    return {
        "job_id": int(job.job_id or 0),
        "project_name": job.project_name or f"Job #{job.job_id or 0}",
        "status": job.status,
        "status_display": job.status_display,
        "bid_amount": float(job.bid_amount or 0.0),
        "scheduled_date": job.scheduled_date,
        "completion_date": job.completion_date,
    }


def _resolve_user_id(repo: JobRepository, provided_user_id: Optional[int]) -> int:
    if provided_user_id:
        return provided_user_id

    row = repo.db.fetchone(
        "SELECT user_id FROM Jobs ORDER BY updated_at DESC, created_at DESC LIMIT 1;"
    )
    if row and row[0]:
        return int(row[0])

    row = repo.db.fetchone("SELECT user_id FROM Users ORDER BY user_id DESC LIMIT 1;")
    if row and row[0]:
        return int(row[0])

    raise ValueError("No users found in local database.")


def get_dashboard_summary(user_id: Optional[int] = None) -> Dict[str, Any]:
    db = DBConnector()
    repo = JobRepository(db)

    resolved_user_id = _resolve_user_id(repo, user_id)
    all_jobs = repo.get_all_jobs(resolved_user_id)

    active_jobs = [j for j in all_jobs if j.status in ACTIVE_STATUSES]
    completed_jobs = [j for j in all_jobs if j.status in COMPLETED_STATUSES]

    total_revenue = sum(float(j.bid_amount or 0.0) for j in completed_jobs)
    total_profit = 0.0

    for job in completed_jobs:
        if not job.job_id:
            continue
        financials = repo.get_job_financials(job.job_id)
        if not financials:
            continue
        if financials.net_profit is not None:
            total_profit += float(financials.net_profit)
            continue

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
        total_costs = sum(float(c) for c in costs if c is not None)
        total_profit += float(financials.bid_amount) - total_costs

    profit_margin = (total_profit / total_revenue * 100.0) if total_revenue > 0 else 0.0

    today = date.today()
    upcoming_cutoff = today + timedelta(days=7)
    overdue_jobs = []
    todays_jobs = []
    upcoming_jobs = []

    for job in active_jobs:
        scheduled_date = _parse_date(job.scheduled_date)
        completion_date = _parse_date(job.completion_date)

        if scheduled_date == today and job.status in {"scheduled", "in_progress"}:
            todays_jobs.append(job)

        if completion_date and completion_date < today and job.status not in COMPLETED_STATUSES:
            overdue_jobs.append(job)
            continue

        if scheduled_date and today < scheduled_date <= upcoming_cutoff:
            upcoming_jobs.append(job)

    recent_jobs = sorted(
        all_jobs,
        key=lambda j: _parse_datetime(j.updated_at or j.created_at),
        reverse=True,
    )[:8]

    return {
        "user_id": resolved_user_id,
        "metrics": {
            "active_jobs": len(active_jobs),
            "completed_jobs": len(completed_jobs),
            "total_revenue": round(total_revenue, 2),
            "total_profit": round(total_profit, 2),
            "profit_margin_pct": round(profit_margin, 2),
        },
        "overdue_jobs": [_job_to_item(j) for j in overdue_jobs[:5]],
        "todays_jobs": [_job_to_item(j) for j in todays_jobs[:5]],
        "upcoming_jobs": [_job_to_item(j) for j in upcoming_jobs[:5]],
        "recent_jobs": [_job_to_item(j) for j in recent_jobs],
    }
