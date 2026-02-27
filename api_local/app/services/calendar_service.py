from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from src.database.db_connector import DBConnector
from src.database.job_repository import JobRepository
from src.models.job import Job

VALID_STATUSES = {
    "awaiting_approval",
    "scheduled",
    "in_progress",
    "inspection",
    "completed",
    "invoiced",
}


def _parse_query_date(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format.") from exc


def _parse_job_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None

    value = value.strip()
    if not value:
        return None

    candidates = [value]
    if len(value) >= 10:
        candidates.insert(0, value[:10])

    formats = (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y/%m/%d",
    )

    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue

    return None


def _parse_sort_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


def _job_dates(job: Job) -> Set[date]:
    values = (job.scheduled_date, job.start_date, job.completion_date)
    parsed = {_parse_job_date(v) for v in values}
    return {p for p in parsed if p is not None}


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
        "assigned_crew": job.crew_list,
    }


def _collect_crews(jobs: List[Job]) -> List[str]:
    crew_set = set()
    for job in jobs:
        for member in job.crew_list:
            normalized = member.strip()
            if normalized:
                crew_set.add(normalized)
    return sorted(crew_set)


def _status_matches(job: Job, status: Optional[str]) -> bool:
    return not status or job.status == status


def _crew_matches(job: Job, crew: Optional[str]) -> bool:
    if not crew:
        return True

    needle = crew.strip().lower()
    if not needle:
        return True

    return any(needle in member.lower() for member in job.crew_list)


def get_calendar_jobs(
    start_date: str,
    end_date: str,
    user_id: int,
    status: Optional[str] = None,
    crew: Optional[str] = None,
) -> Dict[str, Any]:
    start = _parse_query_date(start_date, "start_date")
    end = _parse_query_date(end_date, "end_date")
    if start > end:
        raise ValueError("start_date must be less than or equal to end_date.")

    normalized_status = status.strip() if status else None
    if normalized_status == "all":
        normalized_status = None
    if normalized_status and normalized_status not in VALID_STATUSES:
        raise ValueError(f"Unsupported status filter: {normalized_status}")

    db = DBConnector()
    repo = JobRepository(db)
    all_jobs = repo.get_all_jobs(user_id)

    matched: List[Tuple[date, Job]] = []
    for job in all_jobs:
        if not _status_matches(job, normalized_status):
            continue
        if not _crew_matches(job, crew):
            continue

        matching_dates = [d for d in _job_dates(job) if start <= d <= end]
        if not matching_dates:
            continue

        matched.append((min(matching_dates), job))

    matched.sort(
        key=lambda pair: (
            pair[0],
            _parse_sort_datetime(pair[1].updated_at or pair[1].created_at),
        )
    )

    filtered_jobs = [item[1] for item in matched]

    return {
        "user_id": user_id,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "jobs": [_job_to_item(job) for job in filtered_jobs],
        "available_crews": _collect_crews(all_jobs),
    }


def get_calendar_day(
    target_date: str,
    user_id: int,
    status: Optional[str] = None,
    crew: Optional[str] = None,
) -> Dict[str, Any]:
    parsed = _parse_query_date(target_date, "date")
    range_payload = get_calendar_jobs(
        start_date=parsed.strftime("%Y-%m-%d"),
        end_date=parsed.strftime("%Y-%m-%d"),
        user_id=user_id,
        status=status,
        crew=crew,
    )
    return {
        "user_id": range_payload["user_id"],
        "date": parsed.strftime("%Y-%m-%d"),
        "jobs": range_payload["jobs"],
    }
