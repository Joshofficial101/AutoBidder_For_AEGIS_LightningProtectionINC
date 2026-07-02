from __future__ import annotations

import base64
import io
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.parsing_service import parse_pdf

from src.compliance.dual_compliance import DualCompliance
from src.compliance.nfpa780 import NFPA780Compliance
from src.compliance.ul96a import UL96ACompliance
from src.database.db_connector import DBConnector
from src.database.work_plan_repository import WorkPlanRepository

# Try to import PyMuPDF for PDF image extraction
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

CANVAS_WIDTH = 1000.0
CANVAS_HEIGHT = 700.0
FOOTPRINT_MAX_WIDTH = 640.0
FOOTPRINT_MAX_HEIGHT = 420.0
FOOTPRINT_MARGIN_X = 140.0
FOOTPRINT_MARGIN_Y = 120.0


def _safe_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _safe_int(value: Any) -> Optional[int]:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _extract_dimensions(parsed_payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    dimensions = dict(parsed_payload.get("building_dimensions") or {})
    project_info = dict(parsed_payload.get("project_info") or {})
    page_profiles = list(
        ((parsed_payload.get("extraction_metadata") or {}).get("page_profiles") or [])
    )
    return dimensions, project_info, page_profiles


def _merge_project_data(project_data: Dict[str, Any], parsed_payload: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    merged = dict(project_data or {})
    warnings: List[str] = []

    if not parsed_payload:
        return merged, warnings

    parsed_dimensions, parsed_project_info, page_profiles = _extract_dimensions(parsed_payload)
    field_provenance = ((parsed_payload.get("extraction_metadata") or {}).get("field_provenance") or {})

    if parsed_project_info.get("project_name") and not merged.get("project_name"):
        merged["project_name"] = parsed_project_info["project_name"]

    dimension_field_map = {
        "height": "building_height_ft",
        "area": "roof_area_sqft",
        "perimeter": "perimeter_ft",
        "length": "length_ft",
        "width": "width_ft",
    }
    for parsed_key, project_key in dimension_field_map.items():
        if merged.get(project_key) is None and parsed_dimensions.get(parsed_key) is not None:
            merged[project_key] = parsed_dimensions[parsed_key]

    if merged.get("num_corners") is None and parsed_payload.get("num_corners") is not None:
        merged["num_corners"] = parsed_payload.get("num_corners")

    page_roles = {str(profile.get("page_role") or "") for profile in page_profiles}
    if "plan_sheet" not in page_roles and page_profiles:
        warnings.append("No clear plan sheet was detected. Work plan is based on extracted dimensions.")

    height_provenance = str((field_provenance.get("height") or {}).get("source_text") or "")
    if height_provenance and "air terminal" in height_provenance.lower():
        warnings.append("Parsed building height looks like a lightning note. Review dimensions before trusting layout.")

    return merged, warnings


def _solve_rectangular_footprint(area_sqft: float, perimeter_ft: float) -> Optional[Tuple[float, float]]:
    semiperimeter = perimeter_ft / 2.0
    discriminant = (semiperimeter ** 2) - (4.0 * area_sqft)
    if discriminant < 0:
        return None
    root = math.sqrt(discriminant)
    length_ft = (semiperimeter + root) / 2.0
    width_ft = (semiperimeter - root) / 2.0
    if length_ft <= 0 or width_ft <= 0:
        return None
    return max(length_ft, width_ft), min(length_ft, width_ft)


def _resolve_dimensions(project_data: Dict[str, Any]) -> Dict[str, Any]:
    building_height_ft = _safe_float(project_data.get("building_height_ft"))
    roof_area_sqft = _safe_float(project_data.get("roof_area_sqft"))
    perimeter_ft = _safe_float(project_data.get("perimeter_ft"))
    length_ft = _safe_float(project_data.get("length_ft"))
    width_ft = _safe_float(project_data.get("width_ft"))
    num_corners = max(4, _safe_int(project_data.get("num_corners")) or 4)

    if length_ft and width_ft:
        if roof_area_sqft is None:
            roof_area_sqft = length_ft * width_ft
        if perimeter_ft is None:
            perimeter_ft = 2.0 * (length_ft + width_ft)
    elif roof_area_sqft and perimeter_ft:
        solved = _solve_rectangular_footprint(roof_area_sqft, perimeter_ft)
        if solved:
            length_ft, width_ft = solved
    elif roof_area_sqft:
        side = math.sqrt(max(roof_area_sqft, 1.0))
        length_ft = side
        width_ft = side
        if perimeter_ft is None:
            perimeter_ft = side * 4.0
    elif perimeter_ft:
        side = max(perimeter_ft / 4.0, 1.0)
        length_ft = side
        width_ft = side
        roof_area_sqft = side * side

    if building_height_ft is None:
        building_height_ft = 35.0
    if roof_area_sqft is None or length_ft is None or width_ft is None or perimeter_ft is None:
        raise ValueError(
            "Need roof area and perimeter, or roof length and width, to generate a work plan."
        )

    return {
        "project_name": str(project_data.get("project_name") or "Lightning Protection Work Plan"),
        "building_height_ft": round(building_height_ft, 2),
        "roof_area_sqft": round(roof_area_sqft, 2),
        "perimeter_ft": round(perimeter_ft, 2),
        "length_ft": round(length_ft, 2),
        "width_ft": round(width_ft, 2),
        "num_corners": num_corners,
        "preferred_material": str(project_data.get("preferred_material") or "copper"),
    }


def _fit_footprint(length_ft: float, width_ft: float) -> Dict[str, float]:
    scale = min(FOOTPRINT_MAX_WIDTH / max(length_ft, 1.0), FOOTPRINT_MAX_HEIGHT / max(width_ft, 1.0))
    width = length_ft * scale
    height = width_ft * scale
    x = FOOTPRINT_MARGIN_X + (FOOTPRINT_MAX_WIDTH - width) / 2.0
    y = FOOTPRINT_MARGIN_Y + (FOOTPRINT_MAX_HEIGHT - height) / 2.0
    return {"x": round(x, 2), "y": round(y, 2), "width": round(width, 2), "height": round(height, 2)}


def _perimeter_point(bounds: Dict[str, float], distance: float) -> Tuple[float, float, str]:
    x = bounds["x"]
    y = bounds["y"]
    width = bounds["width"]
    height = bounds["height"]
    perimeter = (width * 2.0) + (height * 2.0)
    if perimeter <= 0:
        return x, y, "top"

    remaining = distance % perimeter
    if remaining <= width:
        return x + remaining, y, "top"
    remaining -= width
    if remaining <= height:
        return x + width, y + remaining, "right"
    remaining -= height
    if remaining <= width:
        return x + width - remaining, y + height, "bottom"
    remaining -= width
    return x, y + height - remaining, "left"


def _rectangle_corners(bounds: Dict[str, float]) -> List[Tuple[float, float]]:
    x = bounds["x"]
    y = bounds["y"]
    width = bounds["width"]
    height = bounds["height"]
    return [
        (x, y),
        (x + width, y),
        (x + width, y + height),
        (x, y + height),
    ]


def _distribute_perimeter_points(bounds: Dict[str, float], count: int, include_corners: bool = False) -> List[Tuple[float, float, str]]:
    if count <= 0:
        return []
    perimeter = (bounds["width"] * 2.0) + (bounds["height"] * 2.0)
    if perimeter <= 0:
        return []

    if include_corners:
        spacing = perimeter / count
        return [_perimeter_point(bounds, spacing * index) for index in range(count)]

    spacing = perimeter / (count + 1)
    return [_perimeter_point(bounds, spacing * (index + 1)) for index in range(count)]


def _layout_field_points(bounds: Dict[str, float], count: int) -> List[Tuple[float, float]]:
    if count <= 0:
        return []
    columns = max(1, math.ceil(math.sqrt(count)))
    rows = max(1, math.ceil(count / columns))
    x_step = bounds["width"] / (columns + 1)
    y_step = bounds["height"] / (rows + 1)
    points: List[Tuple[float, float]] = []
    for row in range(rows):
        for column in range(columns):
            if len(points) >= count:
                return points
            points.append(
                (
                    round(bounds["x"] + ((column + 1) * x_step), 2),
                    round(bounds["y"] + ((row + 1) * y_step), 2),
                )
            )
    return points


def _outside_point(x: float, y: float, edge: str, offset: float = 28.0) -> Tuple[float, float]:
    if edge == "top":
        return x, y - offset
    if edge == "right":
        return x + offset, y
    if edge == "bottom":
        return x, y + offset
    return x - offset, y


def _add_component(components: List[Dict[str, Any]], component_type: str, placement_zone: str, x: float, y: float) -> None:
    index = sum(1 for item in components if item["component_type"] == component_type) + 1
    label_prefix = {
        "air_terminal": "AT",
        "downlead": "DL",
        "ground_rod": "GR",
        "bonding": "B",
    }.get(component_type, "C")
    components.append(
        {
            "component_id": f"{component_type}_{index}",
            "component_type": component_type,
            "label": f"{label_prefix}-{index}",
            "placement_zone": placement_zone,
            "x": round(x, 2),
            "y": round(y, 2),
        }
    )


def _calculate_requirements(project_data: Dict[str, Any], compliance_code: str) -> Dict[str, Any]:
    if compliance_code == "UL 96A":
        return UL96ACompliance.check_compliance(project_data)
    if compliance_code == "NFPA 780":
        return NFPA780Compliance.check_compliance(project_data)
    return DualCompliance.check_combined_compliance(project_data)


def _extract_pdf_page_image(
    pdf_path: str,
    page_index: int = 0,
    target_width: int = 1000,
    target_height: int = 700,
) -> Optional[str]:
    """
    Extract a PDF page as a base64-encoded PNG image.
    
    Args:
        pdf_path: Path to the PDF file
        page_index: Which page to extract (0-indexed)
        target_width: Target width for the image
        target_height: Target height for the image
    
    Returns:
        Base64-encoded PNG string, or None if extraction fails
    """
    if not HAS_PYMUPDF:
        return None
    
    try:
        doc = fitz.open(pdf_path)
        if page_index >= len(doc):
            page_index = 0
        
        page = doc[page_index]
        
        # Calculate scale to fit target dimensions while maintaining aspect ratio
        page_rect = page.rect
        scale_x = target_width / page_rect.width
        scale_y = target_height / page_rect.height
        scale = min(scale_x, scale_y)
        
        # Render page to pixmap
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Convert to PNG bytes
        png_bytes = pix.tobytes("png")
        
        doc.close()
        
        # Encode as base64
        return base64.b64encode(png_bytes).decode("utf-8")
        
    except Exception as e:
        print(f"Error extracting PDF page image: {e}")
        return None


def _find_best_plan_page(pdf_path: str) -> int:
    """
    Find the best page to use as the building plan background.
    
    Looks for pages with:
    - Floor plan indicators
    - More graphical content than text
    - Dimension annotations
    
    Returns the page index (0-indexed), defaults to 0.
    """
    if not HAS_PYMUPDF:
        return 0
    
    try:
        doc = fitz.open(pdf_path)
        best_page = 0
        best_score = -1
        
        for i in range(min(len(doc), 10)):  # Check first 10 pages max
            page = doc[i]
            text = page.get_text("text")
            
            # Score based on plan-related keywords and text density
            score = 0
            text_lower = text.lower()
            
            # Positive indicators (floor plan pages)
            if "floor plan" in text_lower or "flr plan" in text_lower:
                score += 50
            if "roof plan" in text_lower:
                score += 40
            if "site plan" in text_lower:
                score += 30
            if "elevation" in text_lower:
                score += 20
            if "scale:" in text_lower or "scale =" in text_lower:
                score += 15
            
            # Prefer pages with less text (more drawings)
            text_length = len(text)
            if text_length < 500:
                score += 25
            elif text_length < 1000:
                score += 15
            elif text_length < 2000:
                score += 5
            
            # Skip cover pages and title pages
            if "cover" in text_lower or "title sheet" in text_lower:
                score -= 30
            if "table of contents" in text_lower:
                score -= 30
            
            if score > best_score:
                best_score = score
                best_page = i
        
        doc.close()
        return best_page
        
    except Exception:
        return 0


def generate_plan_review(project_data: Dict[str, Any], compliance_code: str = "DUAL", pdf_file_path: Optional[str] = None) -> Dict[str, Any]:
    parsed_payload = parse_pdf(pdf_file_path) if pdf_file_path else None
    merged_project_data, warnings = _merge_project_data(project_data, parsed_payload)
    resolved = _resolve_dimensions(merged_project_data)
    requirements = _calculate_requirements(resolved, compliance_code)
    bounds = _fit_footprint(resolved["length_ft"], resolved["width_ft"])

    components: List[Dict[str, Any]] = []

    air_terminals = dict(requirements.get("air_terminals") or {})
    conductors = dict(requirements.get("conductors") or {})
    grounding = dict(requirements.get("grounding") or {})
    bonding = dict(requirements.get("bonding") or {})

    air_corner_count = min(4, max(0, int(air_terminals.get("corners") or 0)))
    corner_points = _rectangle_corners(bounds)
    for x, y in corner_points[:air_corner_count]:
        _add_component(components, "air_terminal", "corner", x, y)

    extra_corner_count = max(0, int(air_terminals.get("corners") or 0) - air_corner_count)
    for x, y, _edge in _distribute_perimeter_points(bounds, extra_corner_count):
        _add_component(components, "air_terminal", "corner", x, y)

    for x, y, _edge in _distribute_perimeter_points(bounds, int(air_terminals.get("edges") or 0)):
        _add_component(components, "air_terminal", "edge", x, y)

    for x, y in _layout_field_points(bounds, int(air_terminals.get("field") or 0)):
        _add_component(components, "air_terminal", "field", x, y)

    downlead_points = _distribute_perimeter_points(bounds, int(conductors.get("num_downleads") or 0), include_corners=True)
    for x, y, edge in downlead_points:
        _add_component(components, "downlead", edge, x, y)

    total_rods = int(grounding.get("total_rods") or 0)
    if downlead_points:
        for index in range(total_rods):
            dl_x, dl_y, edge = downlead_points[index % len(downlead_points)]
            rod_x, rod_y = _outside_point(dl_x, dl_y, edge, offset=40.0)
            _add_component(components, "ground_rod", edge, rod_x, rod_y)

    bonding_connections = int(bonding.get("total_connections") or 0)
    for x, y in _layout_field_points(bounds, bonding_connections):
        _add_component(components, "bonding", "bonding", x, y)

    footprint_outline = [
        {"x": point_x, "y": point_y}
        for point_x, point_y in (
            corner_points +
            [corner_points[0]]
        )
    ]

    counts = {
        "air_terminals": sum(1 for item in components if item["component_type"] == "air_terminal"),
        "downleads": sum(1 for item in components if item["component_type"] == "downlead"),
        "ground_rods": sum(1 for item in components if item["component_type"] == "ground_rod"),
        "bonding_connections": sum(1 for item in components if item["component_type"] == "bonding"),
    }

    if not pdf_file_path:
        warnings.append("Work plan is based on the current manual dimensions.")

    # Extract PDF page as background image
    background_image_base64 = None
    background_page_index = None
    
    if pdf_file_path and HAS_PYMUPDF:
        try:
            # Find the best plan page to use as background
            background_page_index = _find_best_plan_page(pdf_file_path)
            background_image_base64 = _extract_pdf_page_image(
                pdf_file_path,
                page_index=background_page_index,
                target_width=int(CANVAS_WIDTH),
                target_height=int(CANVAS_HEIGHT),
            )
            if background_image_base64:
                print(f"  Extracted PDF page {background_page_index + 1} as background image")
        except Exception as e:
            print(f"  Warning: Could not extract PDF background image: {e}")
            warnings.append("Could not extract PDF page as background image.")

    return {
        "project_name": resolved["project_name"],
        "compliance_code": compliance_code,
        "source_file_name": Path(pdf_file_path).name if pdf_file_path else None,
        "canvas_width": CANVAS_WIDTH,
        "canvas_height": CANVAS_HEIGHT,
        "dimensions": {
            "building_height_ft": resolved["building_height_ft"],
            "roof_area_sqft": resolved["roof_area_sqft"],
            "perimeter_ft": resolved["perimeter_ft"],
            "length_ft": resolved["length_ft"],
            "width_ft": resolved["width_ft"],
            "num_corners": resolved["num_corners"],
        },
        "footprint_bounds": bounds,
        "footprint_outline": footprint_outline,
        "components": components,
        "counts": counts,
        "warnings": warnings,
        "background_image_base64": background_image_base64,
        "background_page_index": background_page_index,
    }


def save_plan_review(
    *,
    user_id: int,
    project_name: str,
    project_data: Dict[str, Any],
    plan_review: Dict[str, Any],
    compliance_code: str,
) -> Dict[str, Any]:
    db = DBConnector()
    repo = WorkPlanRepository(db)
    return repo.save_project_work_plan(
        user_id=user_id,
        project_name=project_name,
        project_data=project_data,
        plan_payload=plan_review,
        compliance_code=compliance_code,
    )


def load_plan_review(*, user_id: int, project_name: str) -> Dict[str, Any]:
    db = DBConnector()
    repo = WorkPlanRepository(db)
    payload = repo.load_project_work_plan(user_id=user_id, project_name=project_name)
    if not payload:
        raise ValueError(f"No saved work plan found for project '{project_name}'.")
    return payload
