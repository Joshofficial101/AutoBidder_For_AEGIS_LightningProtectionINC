from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.temp_files import safe_unlink
from src.database.db_connector import DBConnector
from src.database.bid_repository import BidRepository
from src.database.job_repository import JobRepository
from src.exporters.excel_export import ExcelBidExporter
from src.exporters.pdf_export import PDFSubmittalExporter
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
EXPORT_HISTORY_ROOT = Path(__file__).resolve().parents[3] / "reports" / "job_exports"


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


def _safe_name(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in {"-", "_"}:
            keep.append(ch)
        elif ch.isspace():
            keep.append("_")
    normalized = "".join(keep).strip("_")
    return normalized[:80] or "lightningbid_job"


def _parse_timestamp(value: str) -> Optional[datetime]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _is_safe_export_path(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(EXPORT_HISTORY_ROOT.resolve())
    except Exception:
        return False


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


def get_job_assets_index(user_id: int) -> Dict[str, Any]:
    db = DBConnector()
    repo = JobRepository(db)
    jobs = repo.get_all_jobs(user_id)
    jobs_sorted = sorted(
        jobs,
        key=lambda item: item.updated_at or item.created_at or "",
        reverse=True,
    )
    items = []
    for job in jobs_sorted:
        financials = repo.get_job_financials(int(job.job_id or 0)) if job.job_id else None
        item = _job_to_item(job)
        item["has_financials"] = financials is not None
        items.append(item)
    return {"user_id": user_id, "jobs": items}


def get_job_asset_detail(user_id: int, job_id: int) -> Dict[str, Any]:
    db = DBConnector()
    repo = JobRepository(db)
    bid_repo = BidRepository(db)

    job = repo.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found.")
    if job.user_id != user_id:
        raise ValueError(f"Job {job_id} does not belong to user {user_id}.")
    if not job.bid_id:
        raise ValueError(f"Job {job_id} is missing bid linkage.")

    loaded = bid_repo.load_bid(int(job.bid_id))
    if not loaded:
        raise ValueError(f"Bid data for job {job_id} was not found.")

    bid = loaded["bid"]
    workers_payload = []
    for worker in loaded.get("workers", []):
        wage = float(worker.get("wage_per_hour") or 0.0)
        hours = float(worker.get("hours") or 0.0)
        workers_payload.append(
            {
                "name": str(worker.get("name") or "Worker"),
                "wage_per_hour": wage,
                "hours": hours,
                "total_cost": round(wage * hours, 2),
            }
        )
    sections_payload = [
        {
            "name": section.name,
            "items": len(section.line_items),
            "material_total": round(section.total_material, 2),
            "labor_total": round(section.total_labor, 2),
            "section_total": round(section.section_total, 2),
        }
        for section in bid.sections
    ]
    cost_summary = {
        "material_total": round(bid.subtotal_material, 2),
        "labor_total": round(bid.subtotal_labor, 2),
        "subtotal": round(bid.subtotal, 2),
        "total_with_markup": round(bid.total_with_markup, 2),
        "final_bid_amount": round(bid.adjusted_final_bid_amount, 2),
        "labor_markup_pct": round(bid.labor_markup_pct, 4),
        "overhead_pct": round(bid.overhead_pct, 4),
        "profit_pct": round(bid.profit_pct, 4),
        "shipping_amount": round(bid.shipping_amount, 2),
        "use_tax_pct": round(bid.use_tax_pct, 4),
        "commission_amount": round(bid.commission_amount, 2),
        "tools_rental_amount": round(bid.tools_rental_amount, 4),
        "tools_rental_type": bid.tools_rental_type,
    }

    financials = job.financials
    financial_summary = None
    if financials:
        financial_summary = {
            "payment_status": financials.payment_status,
            "amount_paid": round(float(financials.amount_paid or 0.0), 2),
            "payment_date": financials.payment_date,
            "total_costs": round(float(financials.total_costs), 2) if financials.total_costs is not None else None,
            "net_profit": round(float(financials.net_profit), 2) if financials.net_profit is not None else None,
            "profit_margin_pct": round(float(financials.profit_margin_pct), 2)
            if financials.profit_margin_pct is not None
            else None,
        }

    documents = [
        {
            "document_id": int(document.document_id or 0),
            "document_type": document.document_type,
            "file_path": document.file_path,
            "tag": document.tag,
            "uploaded_at": document.uploaded_at,
        }
        for document in job.documents
    ]
    export_history = []
    for entry in bid_repo.list_exports(int(job.bid_id), limit=120):
        file_path = Path(str(entry["file_path"]))
        export_history.append(
            {
                "export_id": int(entry["export_id"]),
                "export_type": str(entry["export_type"]),
                "file_name": str(entry["file_name"]),
                "file_path": str(entry["file_path"]),
                "created_at": str(entry["created_at"]),
                "file_exists": file_path.exists(),
            }
        )

    item = _job_to_item(job)
    item["has_financials"] = financials is not None
    return {
        "user_id": user_id,
        "job": item,
        "cost_summary": cost_summary,
        "workers": workers_payload,
        "sections": sections_payload,
        "financial_summary": financial_summary,
        "documents": documents,
        "export_history": export_history,
        "can_export_excel": True,
        "can_export_pdf": True,
    }


def export_job_excel(job_id: int, user_id: int) -> Path:
    db = DBConnector()
    repo = JobRepository(db)
    bid_repo = BidRepository(db)

    job = repo.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found.")
    if job.user_id != user_id:
        raise ValueError(f"Job {job_id} does not belong to user {user_id}.")
    if not job.bid_id:
        raise ValueError(f"Job {job_id} is missing bid linkage.")

    loaded = bid_repo.load_bid(int(job.bid_id))
    if not loaded:
        raise ValueError(f"Bid data for job {job_id} was not found.")
    bid = loaded["bid"]
    workers = loaded.get("workers", [])
    export_dir = EXPORT_HISTORY_ROOT / f"user_{user_id}" / f"job_{job_id}"
    export_dir.mkdir(parents=True, exist_ok=True)
    project_label = _safe_name(job.project_name or f"job_{job_id}")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    output_path = export_dir / f"{project_label}_job_{job_id}_bid_{timestamp}.xlsx"

    exporter = ExcelBidExporter()
    generated_path = exporter.export_bid(bid, output_path, workers=workers)
    bid_repo.save_export(int(job.bid_id), "excel", str(generated_path))
    return generated_path


def export_job_pdf(job_id: int, user_id: int) -> Path:
    db = DBConnector()
    repo = JobRepository(db)
    bid_repo = BidRepository(db)

    job = repo.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found.")
    if job.user_id != user_id:
        raise ValueError(f"Job {job_id} does not belong to user {user_id}.")
    if not job.bid_id:
        raise ValueError(f"Job {job_id} is missing bid linkage.")

    loaded = bid_repo.load_bid(int(job.bid_id))
    if not loaded:
        raise ValueError(f"Bid data for job {job_id} was not found.")
    bid = loaded["bid"]
    compliance_code = str(loaded.get("compliance_code") or "DUAL")
    export_dir = EXPORT_HISTORY_ROOT / f"user_{user_id}" / f"job_{job_id}"
    export_dir.mkdir(parents=True, exist_ok=True)
    project_label = _safe_name(job.project_name or f"job_{job_id}")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    output_path = export_dir / f"{project_label}_job_{job_id}_submittal_{timestamp}.pdf"

    exporter = PDFSubmittalExporter()
    generated_path = exporter.export_submittal(bid, output_path, compliance_code=compliance_code)
    bid_repo.save_export(int(job.bid_id), "pdf", str(generated_path))
    return generated_path


def get_historical_job_export(job_id: int, user_id: int, export_id: int) -> Dict[str, Any]:
    db = DBConnector()
    repo = JobRepository(db)
    bid_repo = BidRepository(db)

    job = repo.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found.")
    if job.user_id != user_id:
        raise ValueError(f"Job {job_id} does not belong to user {user_id}.")
    if not job.bid_id:
        raise ValueError(f"Job {job_id} is missing bid linkage.")

    export_row = bid_repo.get_export(export_id)
    if not export_row:
        raise ValueError(f"Export {export_id} was not found.")
    if int(export_row["bid_id"]) != int(job.bid_id):
        raise ValueError(f"Export {export_id} does not belong to job {job_id}.")

    file_path = Path(str(export_row["file_path"]))
    if not file_path.exists():
        raise ValueError(f"Stored export file does not exist for export {export_id}.")

    return {
        "file_path": str(file_path),
        "file_name": str(export_row["file_name"] or file_path.name),
        "export_type": str(export_row["export_type"]),
    }


def cleanup_job_exports(job_id: int, user_id: int, older_than_days: int) -> Dict[str, Any]:
    if older_than_days < 1:
        raise ValueError("older_than_days must be at least 1.")

    db = DBConnector()
    repo = JobRepository(db)
    bid_repo = BidRepository(db)

    job = repo.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found.")
    if job.user_id != user_id:
        raise ValueError(f"Job {job_id} does not belong to user {user_id}.")
    if not job.bid_id:
        raise ValueError(f"Job {job_id} is missing bid linkage.")

    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    exports = bid_repo.list_exports(int(job.bid_id), limit=5000)
    target_ids: List[int] = []
    deleted_files = 0
    skipped_files = 0

    for entry in exports:
        created = _parse_timestamp(str(entry.get("created_at") or ""))
        if not created or created >= cutoff:
            continue
        target_ids.append(int(entry["export_id"]))
        candidate_path = Path(str(entry.get("file_path") or ""))
        if not candidate_path:
            continue
        if _is_safe_export_path(candidate_path):
            if safe_unlink(candidate_path):
                deleted_files += 1
            else:
                skipped_files += 1
        else:
            skipped_files += 1

    deleted_records = bid_repo.delete_exports_by_ids(target_ids)
    return {
        "user_id": user_id,
        "job_id": job_id,
        "older_than_days": older_than_days,
        "deleted_records": deleted_records,
        "deleted_files": deleted_files,
        "skipped_files": skipped_files,
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
