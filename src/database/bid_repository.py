from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from src.database.db_connector import DBConnector
from src.models.bid import Bid, BidLineItem, BidSection
from src.models.items import PriceItem


class BidRepository:
    """
    Repository layer for bid persistence.
    
    NOTE: This repository is designed to be swapped with a SaaS API later.
    The GUI should call these methods instead of writing SQL directly.
    """
    
    def __init__(self, db: DBConnector):
        self.db = db
    
    def list_customers(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT customer_id, name FROM Customers WHERE user_id = ? ORDER BY name;",
            (user_id,)
        )
        return [{"customer_id": r[0], "name": r[1]} for r in rows]
    
    def get_or_create_customer(self, user_id: int, name: str) -> int:
        name = (name or "Default Customer").strip()
        row = self.db.fetchone(
            "SELECT customer_id FROM Customers WHERE user_id = ? AND name = ?;",
            (user_id, name)
        )
        if row:
            return row[0]
        
        timestamp = datetime.utcnow().isoformat()
        cur = self.db.execute(
            "INSERT INTO Customers (user_id, name, created_at) VALUES (?, ?, ?);",
            (user_id, name, timestamp)
        )
        return cur.lastrowid
    
    def list_projects(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT project_id, name FROM Projects WHERE user_id = ? ORDER BY name;",
            (user_id,)
        )
        return [{"project_id": r[0], "name": r[1]} for r in rows]
    
    def get_or_create_project(self, user_id: int, project_name: str, project_data: Dict[str, Any]) -> int:
        project_name = (project_name or "Untitled Project").strip()
        row = self.db.fetchone(
            "SELECT project_id FROM Projects WHERE user_id = ? AND name = ?;",
            (user_id, project_name)
        )
        timestamp = datetime.utcnow().isoformat()
        if row:
            project_id = row[0]
            self.db.execute(
                """
                UPDATE Projects
                SET building_height_ft = ?, roof_area_sqft = ?, perimeter_ft = ?, num_corners = ?,
                    has_metal_roof = ?, preferred_material = ?, updated_at = ?
                WHERE project_id = ?;
                """,
                (
                    project_data.get("building_height_ft"),
                    project_data.get("roof_area_sqft"),
                    project_data.get("perimeter_ft"),
                    project_data.get("num_corners"),
                    1 if project_data.get("has_metal_roof") else 0,
                    project_data.get("preferred_material"),
                    timestamp,
                    project_id,
                )
            )
            return project_id
        
        cur = self.db.execute(
            """
            INSERT INTO Projects (
                user_id, name, building_height_ft, roof_area_sqft, perimeter_ft,
                num_corners, has_metal_roof, preferred_material, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                user_id,
                project_name,
                project_data.get("building_height_ft"),
                project_data.get("roof_area_sqft"),
                project_data.get("perimeter_ft"),
                project_data.get("num_corners"),
                1 if project_data.get("has_metal_roof") else 0,
                project_data.get("preferred_material"),
                timestamp,
                timestamp,
            )
        )
        return cur.lastrowid
    
    def create_bid(
        self,
        user_id: int,
        project_id: int,
        bid: Bid,
        workers: List[Dict[str, Any]],
        compliance_code: str = "DUAL",
    ) -> int:
        timestamp = datetime.utcnow().isoformat()
        cur = self.db.execute(
            """
            INSERT INTO Bids (
                user_id, project_id, created_at, compliance_code, subtotal,
                total_with_markup, final_amount, material_total, labor_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                user_id,
                project_id,
                timestamp,
                compliance_code,
                bid.subtotal,
                bid.total_with_markup,
                bid.adjusted_final_bid_amount,
                bid.subtotal_material,
                bid.subtotal_labor,
            )
        )
        bid_id = cur.lastrowid
        
        # Settings
        self.db.execute(
            """
            INSERT INTO BidSettings (
                bid_id, labor_markup_pct, overhead_pct, profit_pct, commission_amount,
                tools_rental_amount, tools_rental_type, shipping_amount, use_tax_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                bid_id,
                bid.labor_markup_pct,
                bid.overhead_pct,
                bid.profit_pct,
                bid.commission_amount,
                bid.tools_rental_amount,
                bid.tools_rental_type,
                bid.shipping_amount,
                bid.use_tax_pct,
            )
        )
        
        # Workers
        for worker in workers:
            wage = worker.get("wage_per_hour", 0)
            hours = worker.get("hours", 0)
            total_cost = wage * hours
            self.db.execute(
                """
                INSERT INTO BidWorkers (bid_id, name, wage_per_hour, hours, total_cost)
                VALUES (?, ?, ?, ?, ?);
                """,
                (bid_id, worker.get("name", "Worker"), wage, hours, total_cost)
            )
        
        # Sections + line items
        for section in bid.sections:
            section_cur = self.db.execute(
                """
                INSERT INTO BidSections (bid_id, name, material_total, labor_total)
                VALUES (?, ?, ?, ?);
                """,
                (bid_id, section.name, section.total_material, section.total_labor)
            )
            section_id = section_cur.lastrowid
            for item in section.line_items:
                self.db.execute(
                    """
                    INSERT INTO BidLineItems (
                        section_id, item_code, description, material_type, unit, unit_price,
                        quantity, material_cost, labor_cost, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        section_id,
                        item.price_item.code,
                        item.price_item.name,
                        item.price_item.material_type,
                        item.price_item.unit,
                        item.price_item.unit_price,
                        item.quantity,
                        item.material_cost,
                        item.labor_cost or 0.0,
                        item.reason,
                    )
                )
        
        return bid_id
    
    def list_bids(self, user_id: int, project_id: int) -> List[Dict[str, Any]]:
        rows = self.db.fetchall(
            """
            SELECT bid_id, created_at, final_amount
            FROM Bids
            WHERE user_id = ? AND project_id = ?
            ORDER BY created_at DESC;
            """,
            (user_id, project_id)
        )
        return [
            {"bid_id": r[0], "created_at": r[1], "final_amount": r[2]}
            for r in rows
        ]
    
    def list_recent_bids(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.db.fetchall(
            """
            SELECT b.bid_id, b.created_at, b.final_amount, p.name
            FROM Bids b
            JOIN Projects p ON p.project_id = b.project_id
            WHERE b.user_id = ?
            ORDER BY b.created_at DESC
            LIMIT ?;
            """,
            (user_id, limit)
        )
        return [
            {
                "bid_id": r[0],
                "created_at": r[1],
                "final_amount": r[2],
                "project_name": r[3],
            }
            for r in rows
        ]
    
    def load_bid(self, bid_id: int) -> Optional[Dict[str, Any]]:
        bid_row = self.db.fetchone(
            "SELECT project_id, compliance_code, subtotal, total_with_markup, final_amount FROM Bids WHERE bid_id = ?;",
            (bid_id,)
        )
        if not bid_row:
            return None
        
        project_id = bid_row[0]
        project_row = self.db.fetchone(
            """
            SELECT name, building_height_ft, roof_area_sqft, perimeter_ft, num_corners,
                   has_metal_roof, preferred_material
            FROM Projects WHERE project_id = ?;
            """,
            (project_id,)
        )
        project_data = {
            "project_name": project_row[0],
            "building_height_ft": project_row[1],
            "roof_area_sqft": project_row[2],
            "perimeter_ft": project_row[3],
            "num_corners": project_row[4],
            "has_metal_roof": bool(project_row[5]),
            "preferred_material": project_row[6],
        }
        
        settings_row = self.db.fetchone(
            """
            SELECT labor_markup_pct, overhead_pct, profit_pct, commission_amount,
                   tools_rental_amount, tools_rental_type, shipping_amount, use_tax_pct
            FROM BidSettings WHERE bid_id = ?;
            """,
            (bid_id,)
        )
        settings = {
            "labor_markup_pct": settings_row[0],
            "overhead_pct": settings_row[1],
            "profit_pct": settings_row[2],
            "commission_amount": settings_row[3],
            "tools_rental_amount": settings_row[4],
            "tools_rental_type": settings_row[5],
            "shipping_amount": settings_row[6],
            "use_tax_pct": settings_row[7],
        }
        
        workers_rows = self.db.fetchall(
            "SELECT name, wage_per_hour, hours FROM BidWorkers WHERE bid_id = ?;",
            (bid_id,)
        )
        workers = [
            {"name": r[0], "wage_per_hour": r[1], "hours": r[2]}
            for r in workers_rows
        ]
        
        # Sections and line items
        sections_rows = self.db.fetchall(
            "SELECT section_id, name FROM BidSections WHERE bid_id = ?;",
            (bid_id,)
        )
        
        bid_obj = Bid(
            project_name=project_data.get("project_name", "Lightning Protection Bid"),
            labor_markup_pct=settings["labor_markup_pct"],
            overhead_pct=settings["overhead_pct"],
            profit_pct=settings["profit_pct"],
            commission_amount=settings["commission_amount"],
            tools_rental_amount=settings["tools_rental_amount"],
            tools_rental_type=settings["tools_rental_type"],
            shipping_amount=settings["shipping_amount"],
            use_tax_pct=settings["use_tax_pct"],
        )
        
        for section_id, section_name in sections_rows:
            section = BidSection(name=section_name)
            line_rows = self.db.fetchall(
                """
                SELECT item_code, description, material_type, unit, unit_price,
                       quantity, material_cost, labor_cost, reason
                FROM BidLineItems WHERE section_id = ?;
                """,
                (section_id,)
            )
            for row in line_rows:
                price_item = PriceItem(
                    code=row[0] or "",
                    name=row[1] or "",
                    material_type=row[2],
                    unit=row[3],
                    unit_price=row[4] or 0.0,
                    labor_rate=None
                )
                line_item = BidLineItem(
                    price_item=price_item,
                    quantity=row[5] or 0.0,
                    material_cost=row[6] or 0.0,
                    labor_cost=row[7] or 0.0,
                    reason=row[8]
                )
                section.line_items.append(line_item)
            bid_obj.sections.append(section)
        
        return {
            "project_data": project_data,
            "settings": settings,
            "workers": workers,
            "compliance_code": bid_row[1],
            "bid": bid_obj,
        }
    
    def save_export(self, bid_id: int, export_type: str, file_path: str):
        timestamp = datetime.utcnow().isoformat()
        cur = self.db.execute(
            "INSERT INTO Exports (bid_id, export_type, file_path, created_at) VALUES (?, ?, ?, ?);",
            (bid_id, export_type, file_path, timestamp)
        )
        return int(cur.lastrowid)

    def list_exports(self, bid_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self.db.fetchall(
            """
            SELECT export_id, bid_id, export_type, file_path, created_at
            FROM Exports
            WHERE bid_id = ?
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (bid_id, limit),
        )
        payload: List[Dict[str, Any]] = []
        for row in rows:
            file_path = str(row[3] or "")
            payload.append(
                {
                    "export_id": int(row[0]),
                    "bid_id": int(row[1]),
                    "export_type": str(row[2] or ""),
                    "file_path": file_path,
                    "file_name": Path(file_path).name if file_path else "",
                    "created_at": str(row[4] or ""),
                }
            )
        return payload

    def get_export(self, export_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.fetchone(
            """
            SELECT export_id, bid_id, export_type, file_path, created_at
            FROM Exports
            WHERE export_id = ?;
            """,
            (export_id,),
        )
        if not row:
            return None
        file_path = str(row[3] or "")
        return {
            "export_id": int(row[0]),
            "bid_id": int(row[1]),
            "export_type": str(row[2] or ""),
            "file_path": file_path,
            "file_name": Path(file_path).name if file_path else "",
            "created_at": str(row[4] or ""),
        }

    def delete_exports_by_ids(self, export_ids: List[int]) -> int:
        normalized_ids = sorted({int(export_id) for export_id in export_ids if int(export_id) > 0})
        if not normalized_ids:
            return 0
        placeholders = ", ".join(["?"] * len(normalized_ids))
        sql = f"DELETE FROM Exports WHERE export_id IN ({placeholders});"
        cur = self.db.execute(sql, tuple(normalized_ids))
        return int(cur.rowcount or 0)
    
    def save_autosave(self, user_id: int, payload: Dict[str, Any]):
        timestamp = datetime.utcnow().isoformat()
        existing = self.db.fetchone("SELECT autosave_id FROM Autosaves WHERE user_id = ?;", (user_id,))
        payload_json = json.dumps(payload)
        if existing:
            self.db.execute(
                "UPDATE Autosaves SET payload_json = ?, updated_at = ? WHERE user_id = ?;",
                (payload_json, timestamp, user_id)
            )
        else:
            self.db.execute(
                "INSERT INTO Autosaves (user_id, payload_json, updated_at) VALUES (?, ?, ?);",
                (user_id, payload_json, timestamp)
            )
    
    def load_autosave(self, user_id: int) -> Optional[Dict[str, Any]]:
        record = self.load_autosave_record(user_id)
        if not record:
            return None
        return record.get("payload")

    def load_autosave_record(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.fetchone(
            "SELECT payload_json, updated_at FROM Autosaves WHERE user_id = ?;",
            (user_id,)
        )
        if not row:
            return None
        try:
            return {
                "payload": json.loads(row[0]),
                "updated_at": str(row[1] or ""),
            }
        except json.JSONDecodeError:
            return None
    
    def clear_autosave(self, user_id: int):
        self.db.execute("DELETE FROM Autosaves WHERE user_id = ?;", (user_id,))
    
    # ========================================================================
    # BID STATUS TRACKING (Phase 1: Job Management)
    # ========================================================================
    
    def update_bid_status(
        self,
        bid_id: int,
        status: str,
        date_sent: Optional[str] = None,
        date_responded: Optional[str] = None,
        follow_up_date: Optional[str] = None
    ) -> bool:
        """
        Update the status of a bid.
        
        Args:
            bid_id: ID of the bid
            status: New status (draft, sent, accepted, rejected, expired)
            date_sent: Optional date the bid was sent
            date_responded: Optional date the customer responded
            follow_up_date: Optional date for follow-up
            
        Returns:
            True if successful
        """
        sql = "UPDATE Bids SET status = ?"
        params = [status]
        
        if date_sent is not None:
            sql += ", date_sent = ?"
            params.append(date_sent)
        
        if date_responded is not None:
            sql += ", date_responded = ?"
            params.append(date_responded)
        
        if follow_up_date is not None:
            sql += ", follow_up_date = ?"
            params.append(follow_up_date)
        
        sql += " WHERE bid_id = ?;"
        params.append(bid_id)
        
        self.db.execute(sql, tuple(params))
        return True
    
    def get_bids_by_status(
        self,
        user_id: int,
        status: str
    ) -> List[Dict[str, Any]]:
        """
        Get all bids with a specific status.
        
        Args:
            user_id: ID of the user
            status: Status to filter by
            
        Returns:
            List of bid dictionaries
        """
        rows = self.db.fetchall(
            """
            SELECT b.bid_id, b.created_at, b.final_amount, b.status, 
                   b.date_sent, b.date_responded, b.follow_up_date,
                   p.name as project_name
            FROM Bids b
            JOIN Projects p ON p.project_id = b.project_id
            WHERE b.user_id = ? AND b.status = ?
            ORDER BY b.created_at DESC;
            """,
            (user_id, status)
        )
        return [
            {
                "bid_id": r[0],
                "created_at": r[1],
                "final_amount": r[2],
                "status": r[3],
                "date_sent": r[4],
                "date_responded": r[5],
                "follow_up_date": r[6],
                "project_name": r[7]
            }
            for r in rows
        ]
    
    def get_pending_bids(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all bids that have been sent but not yet responded to.
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of pending bid dictionaries
        """
        return self.get_bids_by_status(user_id, "sent")

