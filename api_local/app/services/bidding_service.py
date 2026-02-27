from pathlib import Path
import math
import sys
from typing import Any, Dict, List

# Ensure existing src package can be imported
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.excel_loader import load_pricing_from_excel
from src.calculator.bid_calc import BidCalculator
from src.exporters.excel_export import ExcelBidExporter
from src.exporters.pdf_export import PDFSubmittalExporter
from app.file_limits import assert_excel_file_within_limit


def _apply_worker_labor_costs(bid, workers: List[Dict[str, Any]]) -> None:
    if not workers:
        return

    total_project_labor_cost = sum((w.get("hours", 0) * w.get("wage_per_hour", 0)) for w in workers)

    if bid.subtotal_material > 0:
        for section in bid.sections:
            section_ratio = section.total_material / bid.subtotal_material
            section_labor = total_project_labor_cost * section_ratio
            if section.line_items:
                labor_per_item = section_labor / len(section.line_items)
                for line_item in section.line_items:
                    line_item.labor_cost = labor_per_item
    else:
        total_items = sum(len(s.line_items) for s in bid.sections)
        if total_items > 0:
            labor_per_item = total_project_labor_cost / total_items
            for section in bid.sections:
                for line_item in section.line_items:
                    line_item.labor_cost = labor_per_item


def _build_calculation_breakdown(
    bid,
    custom_adjustment_entries: List[Dict[str, Any]],
    custom_adjustments_total: float,
    final_amount_before_floor_rounding: float,
    minimum_bid_amount: float,
    rounding_mode: str,
    rounding_increment: float,
    minimum_floor_adjustment: float,
    rounding_adjustment: float,
    final_bid_amount: float,
) -> Dict[str, Any]:
    material_markup_amount = bid.subtotal_material * (bid.material_markup_pct / 100.0)
    labor_markup_amount = bid.subtotal_labor * (bid.labor_markup_pct / 100.0)
    overhead_amount = bid.subtotal * (bid.overhead_pct / 100.0)
    profit_amount = bid.subtotal * (bid.profit_pct / 100.0)

    line_items = [
        {"key": "material_subtotal", "label": "Material Subtotal", "amount": round(bid.subtotal_material, 2)},
        {"key": "shipping", "label": "Shipping", "amount": round(bid.shipping_amount, 2)},
        {"key": "material_tax", "label": "Use Tax", "amount": round(bid.material_tax, 2)},
        {"key": "labor_subtotal", "label": "Labor Subtotal", "amount": round(bid.subtotal_labor, 2)},
        {"key": "subtotal", "label": "Subtotal", "amount": round(bid.subtotal, 2)},
        {"key": "material_markup", "label": "Material Markup", "amount": round(material_markup_amount, 2)},
        {"key": "labor_markup", "label": "Labor Markup", "amount": round(labor_markup_amount, 2)},
        {"key": "total_with_markup", "label": "Total With Markup", "amount": round(bid.total_with_markup, 2)},
        {"key": "overhead", "label": "Overhead", "amount": round(overhead_amount, 2)},
        {"key": "profit", "label": "Profit", "amount": round(profit_amount, 2)},
        {"key": "commission", "label": "Commission", "amount": round(bid.commission_amount, 2)},
        {"key": "tools_rental", "label": "Tools & Rental", "amount": round(bid.tools_rental_cost, 2)},
    ]

    for index, entry in enumerate(custom_adjustment_entries):
        line_items.append(
            {
                "key": f"custom_adjustment_{index + 1}",
                "label": f"Custom: {entry['name']}",
                "amount": round(float(entry["applied_amount"]), 2),
            }
        )

    if minimum_floor_adjustment > 0:
        line_items.append(
            {
                "key": "minimum_floor_adjustment",
                "label": "Minimum Bid Floor Adjustment",
                "amount": round(minimum_floor_adjustment, 2),
            }
        )
    if rounding_adjustment != 0:
        line_items.append(
            {
                "key": "rounding_adjustment",
                "label": "Rounding Adjustment",
                "amount": round(rounding_adjustment, 2),
            }
        )

    return {
        "currency": "USD",
        "line_items": line_items,
        "custom_adjustments": custom_adjustment_entries,
        "inputs": {
            "material_markup_pct": round(bid.material_markup_pct, 4),
            "labor_markup_pct": round(bid.labor_markup_pct, 4),
            "overhead_pct": round(bid.overhead_pct, 4),
            "profit_pct": round(bid.profit_pct, 4),
            "commission_amount": round(bid.commission_amount, 2),
            "tools_rental_amount": round(bid.tools_rental_amount, 4),
            "tools_rental_type": bid.tools_rental_type,
            "shipping_amount": round(bid.shipping_amount, 2),
            "use_tax_pct": round(bid.use_tax_pct, 4),
            "minimum_bid_amount": round(minimum_bid_amount, 2),
            "rounding_mode": rounding_mode,
            "rounding_increment": round(rounding_increment, 2),
        },
        "totals": {
            "subtotal": round(bid.subtotal, 2),
            "total_with_markup": round(bid.total_with_markup, 2),
            "base_final_before_custom": round(bid.final_bid_amount, 2),
            "custom_adjustments_total": round(custom_adjustments_total, 2),
            "final_before_floor_rounding": round(final_amount_before_floor_rounding, 2),
            "minimum_floor_adjustment": round(minimum_floor_adjustment, 2),
            "rounding_adjustment": round(rounding_adjustment, 2),
            "final_bid_amount": round(final_bid_amount, 2),
        },
    }


def _build_bid_from_payload(payload: Dict[str, Any]):
    pricing_file_path = payload.get("pricing_file_path")
    pricing_sheet = payload.get("pricing_sheet")
    compliance_code = payload.get("compliance_code") or "DUAL"
    project_data = dict(payload.get("project_data") or {})
    workers = [dict(w) for w in payload.get("workers") or []]

    if not pricing_file_path:
        raise ValueError("pricing_file_path is required")

    path_obj = Path(pricing_file_path)
    if not path_obj.exists():
        raise ValueError("pricing_file_path does not exist")
    assert_excel_file_within_limit(path_obj)

    if not project_data.get("project_name"):
        project_data["project_name"] = "Lightning Protection Project"
    if not project_data.get("building_height_ft"):
        project_data["building_height_ft"] = 35.0
    if not project_data.get("roof_area_sqft"):
        project_data["roof_area_sqft"] = 5000.0
    if not project_data.get("perimeter_ft"):
        import math
        side_length = math.sqrt(project_data["roof_area_sqft"])
        project_data["perimeter_ft"] = side_length * 4

    try:
        price_catalog = load_pricing_from_excel(path_obj, sheet_name=pricing_sheet)
    except Exception as exc:
        raise ValueError(f"pricing_sheet invalid or unreadable: {exc}")

    calculator = BidCalculator(price_catalog, compliance_code=compliance_code)
    bid = calculator.calculate_bid(project_data)
    _apply_worker_labor_costs(bid, workers)
    return bid, workers, compliance_code


def preview_bid(payload: Dict[str, Any]) -> Dict[str, Any]:
    bid, _workers, _compliance_code = _build_bid_from_payload(payload)

    custom_adjustment_entries = [
        {
            "name": str(item.get("name") or ""),
            "mode": str(item.get("mode") or "$"),
            "value": round(float(item.get("value") or 0.0), 4),
            "applied_amount": round(float(item.get("applied_amount") or 0.0), 2),
        }
        for item in bid.custom_pricing_adjustment_entries
    ]
    custom_adjustments_total = round(float(bid.custom_pricing_adjustments_total), 2)
    final_before_floor_rounding = round(float(bid.final_before_floor_rounding), 2)
    minimum_bid_amount = round(max(0.0, float(bid.minimum_bid_amount or 0.0)), 2)
    rounding_mode = bid.normalized_rounding_mode
    rounding_increment = round(max(0.0, float(bid.rounding_increment or 0.0)), 2)
    minimum_floor_adjustment = round(float(bid.minimum_floor_adjustment), 2)
    rounding_adjustment = round(float(bid.rounding_adjustment), 2)
    final_bid_amount = round(float(bid.adjusted_final_bid_amount), 2)
    calculation_breakdown = _build_calculation_breakdown(
        bid=bid,
        custom_adjustment_entries=custom_adjustment_entries,
        custom_adjustments_total=custom_adjustments_total,
        final_amount_before_floor_rounding=final_before_floor_rounding,
        minimum_bid_amount=minimum_bid_amount,
        rounding_mode=rounding_mode,
        rounding_increment=rounding_increment,
        minimum_floor_adjustment=minimum_floor_adjustment,
        rounding_adjustment=rounding_adjustment,
        final_bid_amount=final_bid_amount,
    )

    return {
        "project_name": bid.project_name,
        "subtotal": bid.subtotal,
        "total_with_markup": bid.total_with_markup,
        "final_bid_amount": final_bid_amount,
        "material_total": bid.subtotal_material,
        "labor_total": bid.subtotal_labor,
        "calculation_breakdown": calculation_breakdown,
        "sections": [
            {
                "name": s.name,
                "items": len(s.line_items),
                "material_total": s.total_material,
                "labor_total": s.total_labor,
                "section_total": s.section_total,
            }
            for s in bid.sections
        ],
    }


def export_bid_excel(payload: Dict[str, Any], output_path: Path) -> Path:
    bid, workers, _compliance_code = _build_bid_from_payload(payload)
    exporter = ExcelBidExporter()
    return exporter.export_bid(bid, output_path, workers=workers)


def export_bid_pdf(payload: Dict[str, Any], output_path: Path) -> Path:
    bid, _workers, compliance_code = _build_bid_from_payload(payload)
    exporter = PDFSubmittalExporter()
    return exporter.export_submittal(bid, output_path, compliance_code=compliance_code)
