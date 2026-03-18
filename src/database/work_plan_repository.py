from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from src.database.bid_repository import BidRepository
from src.database.db_connector import DBConnector


class WorkPlanRepository:
    def __init__(self, db: DBConnector):
        self.db = db
        self.bid_repo = BidRepository(db)

    def save_project_work_plan(
        self,
        user_id: int,
        project_name: str,
        project_data: Dict[str, Any],
        plan_payload: Dict[str, Any],
        compliance_code: str,
    ) -> Dict[str, Any]:
        normalized_project_name = (project_name or "").strip()
        if not normalized_project_name:
            raise ValueError("project_name is required to save a work plan.")

        project_id = self.bid_repo.get_or_create_project(
            user_id=user_id,
            project_name=normalized_project_name,
            project_data=project_data,
        )

        timestamp = datetime.utcnow().isoformat()
        serialized_payload = json.dumps(plan_payload)
        source_file_name = str(plan_payload.get("source_file_name") or "") or None
        existing = self.db.fetchone(
            "SELECT work_plan_id FROM ProjectWorkPlans WHERE project_id = ? AND user_id = ?;",
            (project_id, user_id),
        )

        if existing:
            self.db.execute(
                """
                UPDATE ProjectWorkPlans
                SET source_file_name = ?, compliance_code = ?, canvas_width = ?, canvas_height = ?,
                    plan_payload_json = ?, updated_at = ?
                WHERE work_plan_id = ?;
                """,
                (
                    source_file_name,
                    compliance_code,
                    float(plan_payload.get("canvas_width") or 0.0),
                    float(plan_payload.get("canvas_height") or 0.0),
                    serialized_payload,
                    timestamp,
                    int(existing[0]),
                ),
            )
        else:
            self.db.execute(
                """
                INSERT INTO ProjectWorkPlans (
                    project_id, user_id, source_file_name, compliance_code, canvas_width, canvas_height,
                    plan_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    project_id,
                    user_id,
                    source_file_name,
                    compliance_code,
                    float(plan_payload.get("canvas_width") or 0.0),
                    float(plan_payload.get("canvas_height") or 0.0),
                    serialized_payload,
                    timestamp,
                    timestamp,
                ),
            )

        return {
            "user_id": user_id,
            "project_id": int(project_id),
            "project_name": normalized_project_name,
            "updated_at": timestamp,
        }

    def load_project_work_plan(self, user_id: int, project_name: str) -> Optional[Dict[str, Any]]:
        normalized_project_name = (project_name or "").strip()
        if not normalized_project_name:
            raise ValueError("project_name is required to load a work plan.")

        row = self.db.fetchone(
            """
            SELECT p.project_id, wp.plan_payload_json
            FROM Projects p
            JOIN ProjectWorkPlans wp ON wp.project_id = p.project_id
            WHERE p.user_id = ? AND p.name = ? AND wp.user_id = ?;
            """,
            (user_id, normalized_project_name, user_id),
        )
        if not row:
            return None
        payload = json.loads(str(row[1] or "{}"))
        return payload if isinstance(payload, dict) else None
