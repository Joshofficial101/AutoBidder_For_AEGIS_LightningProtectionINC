from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    
    def create_bid(self, user_id: int, project_id: int, bid: Bid, workers: List[Dict[str, Any]]) -> int:
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
                "DUAL",
                bid.subtotal,
                bid.total_with_markup,
                bid.final_bid_amount,
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
            "SELECT project_id, subtotal, total_with_markup, final_amount FROM Bids WHERE bid_id = ?;",
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
            "bid": bid_obj,
        }
    
    def save_export(self, bid_id: int, export_type: str, file_path: str):
        timestamp = datetime.utcnow().isoformat()
        self.db.execute(
            "INSERT INTO Exports (bid_id, export_type, file_path, created_at) VALUES (?, ?, ?, ?);",
            (bid_id, export_type, file_path, timestamp)
        )
    
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
        row = self.db.fetchone(
            "SELECT payload_json FROM Autosaves WHERE user_id = ?;",
            (user_id,)
        )
        if not row:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None
    
    def clear_autosave(self, user_id: int):
        self.db.execute("DELETE FROM Autosaves WHERE user_id = ?;", (user_id,))

