"""
Enhanced PDF Parser for Lightning Protection Project Specifications

This module extracts structured data from PDF specification documents including:
- Building dimensions (height, area, perimeter)
- Project name and location
- Material preferences
- Special requirements
- Compliance standards

Supports multiple PDF types:
- Simple text-based specification PDFs
- Building plan PDFs with drawings and tables
- Architectural drawings with scale information
- Scanned documents (via OCR if available)
"""

from pathlib import Path
import pdfplumber
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Keywords for different types of information
KEY_SECTIONS = ["PART 1", "PART 2", "PART 3", "SUBMITTALS", "INSTALLATION", 
                "GROUNDING", "AIR TERMINALS", "CONDUCTORS", "BONDING"]

COMPLIANCE_STANDARDS = ["UL 96A", "NFPA 780", "UL96A", "NFPA780"]

MATERIAL_KEYWORDS = {
    "copper": ["copper", "cu", "copper clad"],
    "aluminum": ["aluminum", "al", "aluminium"],
    "bimetal": ["bimetal", "bi-metal", "bimetallic"]
}

# Architectural dimension patterns (handles formats like 50'-0", 50'6", 50 FT, etc.)
ARCH_DIMENSION_PATTERNS = [
    # Feet and inches: 50'-6", 50' 6", 50'-0"
    r"(\d+)['\u2019\u0027]\s*[-]?\s*(\d+)[\"″\u0022]?",
    # Feet only: 50', 50 FT, 50 FEET
    r"(\d+\.?\d*)\s*(?:['\u2019\u0027]|FT\.?|FEET|ft\.?|feet)",
    # Decimal feet: 50.5'
    r"(\d+\.\d+)\s*['\u2019\u0027]",
    # Generic number with unit
    r"(\d+\.?\d*)\s*(?:LF|L\.?F\.?|linear\s*feet|LINEAR\s*FEET)",
]

# Square footage patterns
AREA_PATTERNS = [
    r"(\d+[,\d]*\.?\d*)\s*(?:SF|S\.?F\.?|sq\.?\s*ft\.?|SQ\.?\s*FT\.?|square\s*feet|SQUARE\s*FEET)",
    r"(\d+[,\d]*\.?\d*)\s*(?:sqft|SQFT)",
    r"area[:\s]+(\d+[,\d]*\.?\d*)",
    r"(\d+[,\d]*\.?\d*)\s*(?:sq\.?\s*m|m²|m2)",  # Metric support
]


def _convert_arch_to_feet(feet_str: str, inches_str: str = "0") -> float:
    """Convert architectural notation (feet-inches) to decimal feet."""
    feet = float(feet_str) if feet_str else 0
    inches = float(inches_str) if inches_str else 0
    return feet + (inches / 12.0)


def _extract_number(text: str, unit: str = None) -> Optional[float]:
    """
    Extract a number from text, handling various formats.
    
    Examples: "35 feet", "35'", "35 ft", "35.5", "35,000 sq ft", "35'-6\""
    """
    if not text:
        return None
    
    text_clean = text.strip()
    
    # Try architectural feet-inches format first: 35'-6" or 35' 6"
    arch_match = re.search(r"(\d+)['\u2019\u0027]\s*[-]?\s*(\d+)[\"″\u0022]", text_clean)
    if arch_match:
        return _convert_arch_to_feet(arch_match.group(1), arch_match.group(2))
    
    # Try feet-only architectural: 35'
    feet_only = re.search(r"(\d+\.?\d*)\s*['\u2019\u0027](?!\s*\d)", text_clean)
    if feet_only:
        return float(feet_only.group(1))
    
    # Remove commas for large numbers
    text_clean = text_clean.replace(",", "")
    
    # Pattern for numbers with optional decimals
    patterns = [
        r'(\d+\.?\d*)\s*' + (unit or r'ft\.?|feet|sq\s*ft|sqft|square\s*feet|inches?|in|LF|L\.?F\.?|linear\s*feet'),
        r'(\d+\.?\d*)',  # Just a number
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    
    return None


def _extract_dimension_from_text(text: str, dimension_type: str) -> Optional[float]:
    """
    Extract a specific dimension type from text using multiple strategies.
    
    Args:
        text: The text to search
        dimension_type: One of 'height', 'area', 'perimeter', 'width', 'length'
    
    Returns:
        The extracted dimension value in feet (or sq ft for area), or None
    """
    text_lower = text.lower()
    
    if dimension_type == "height":
        patterns = [
            # Explicit height mentions
            r'(?:roof\s+)?height[:\s=]+(\d+[\'\".\d\s-]*(?:ft|feet|[\'"]|\s*$))',
            r'(?:building|structure|eave|ridge)\s+height[:\s=]+(\d+[\'\".\d\s-]*)',
            r'(\d+[\'\".\d\s-]*(?:ft|feet|[\'"]))?\s*(?:tall|high)',
            r'height\s*(?:of|=|:)\s*(\d+[\'\".\d\s-]*)',
            # Story-based (assume 12 ft per story)
            r'(\d+)\s*(?:story|stories|storey|storeys)',
            # Elevation differences
            r'(?:top|peak|ridge)\s+(?:elev|elevation)[:\s=]+(\d+\.?\d*)',
            r'(?:base|ground|grade)\s+(?:elev|elevation)[:\s=]+(\d+\.?\d*)',
        ]
    elif dimension_type == "area":
        patterns = AREA_PATTERNS + [
            r'(?:roof|building|total|gross|floor)\s+area[:\s=]+(\d+[,\d]*\.?\d*)',
            r'(\d+[,\d]*\.?\d*)\s*(?:sf|SF)\s*(?:roof|building|total)?',
        ]
    elif dimension_type == "perimeter":
        patterns = [
            r'perimeter[:\s=]+(\d+[\'\".\d\s,-]*(?:ft|feet|[\'"]|LF|L\.?F\.?|\s*$))',
            r'(\d+[\'\".\d\s,-]*(?:LF|L\.?F\.?|linear\s*feet))',
            r'(?:total\s+)?(?:linear|perimeter)\s*(?:footage|feet)[:\s=]+(\d+[,\d]*\.?\d*)',
            r'perimeter\s*(?:length)?[:\s=]+(\d+[,\d]*\.?\d*)',
        ]
    elif dimension_type == "width":
        patterns = [
            r'width[:\s=]+(\d+[\'\".\d\s-]*(?:ft|feet|[\'"]|\s*$))',
            r'(\d+[\'\".\d\s-]*)\s*(?:wide|w\s*[x×])',
            r'w[:\s=]+(\d+[\'\".\d\s-]*)',
        ]
    elif dimension_type == "length":
        patterns = [
            r'length[:\s=]+(\d+[\'\".\d\s-]*(?:ft|feet|[\'"]|\s*$))',
            r'(\d+[\'\".\d\s-]*)\s*(?:long|l\s*[x×])',
            r'l[:\s=]+(\d+[\'\".\d\s-]*)',
        ]
    else:
        return None
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            value_str = match.group(1)
            if value_str:
                # Handle story-based height conversion
                if dimension_type == "height" and "stor" in pattern:
                    try:
                        stories = int(value_str)
                        return stories * 12.0  # Assume 12 ft per story
                    except ValueError:
                        continue
                
                value = _extract_number(value_str)
                if value and value > 0:
                    return value
    
    return None


def _extract_dimensions_from_tables(tables: List[List[List[str]]]) -> Dict[str, Optional[float]]:
    """
    Extract building dimensions from PDF tables.
    
    Tables in building plans often contain dimension schedules, room schedules,
    or summary data with measurements.
    """
    dims = {
        "height": None,
        "area": None,
        "perimeter": None,
        "width": None,
        "length": None
    }
    
    dimension_keywords = {
        "height": ["height", "ht", "tall", "elevation", "eave", "ridge"],
        "area": ["area", "sf", "sqft", "sq ft", "square feet", "roof area"],
        "perimeter": ["perimeter", "perim", "linear", "lf", "l.f."],
        "width": ["width", "w", "wide"],
        "length": ["length", "l", "long", "len"]
    }
    
    for table in tables:
        if not table:
            continue
            
        for row in table:
            if not row or len(row) < 2:
                continue
            
            # Look for label-value pairs in table cells
            row_text = " ".join(str(cell) if cell else "" for cell in row).lower()
            
            for dim_type, keywords in dimension_keywords.items():
                if dims[dim_type] is not None:
                    continue
                    
                for keyword in keywords:
                    if keyword in row_text:
                        # Try to find a number in adjacent cells
                        for cell in row:
                            if cell:
                                value = _extract_number(str(cell))
                                if value and value > 0:
                                    # Validate reasonable ranges
                                    if dim_type == "height" and 5 <= value <= 1000:
                                        dims["height"] = value
                                    elif dim_type == "area" and value >= 100:
                                        dims["area"] = value
                                    elif dim_type == "perimeter" and value >= 20:
                                        dims["perimeter"] = value
                                    elif dim_type in ["width", "length"] and 5 <= value <= 2000:
                                        dims[dim_type] = value
                                    break
    
    return dims


def _extract_dimensions_from_annotations(page) -> Dict[str, Optional[float]]:
    """
    Extract dimensions from PDF annotations/comments.
    
    Building plans often have dimension annotations added via CAD or PDF tools.
    """
    dims = {
        "height": None,
        "area": None,
        "perimeter": None,
        "width": None,
        "length": None
    }
    
    # pdfplumber doesn't directly support annotations, but we can extract
    # text from specific regions or look for dimension-like patterns
    # in the raw text extraction
    
    return dims


def _extract_scale_factor(text: str) -> Optional[float]:
    """
    Extract drawing scale from text to help interpret dimensions.
    
    Common scales: 1/8" = 1'-0", 1:100, 1/4" = 1'-0", etc.
    """
    # Imperial scale patterns: 1/8" = 1'-0", 3/16" = 1'-0", etc.
    imperial_patterns = [
        r'(\d+)/(\d+)[\"″]\s*=\s*1[\'\u2019]-0[\"″]',  # 1/8" = 1'-0"
        r'scale[:\s]+(\d+)/(\d+)[\"″]\s*=\s*1[\'\u2019]',
        r'(\d+)/(\d+)\s*inch\s*=\s*1\s*foot',
    ]
    
    for pattern in imperial_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                num = float(match.group(1))
                denom = float(match.group(2))
                # Scale factor: how many feet per inch on paper
                return 12.0 / (num / denom)  # Convert to feet per drawing unit
            except (ValueError, ZeroDivisionError):
                continue
    
    # Metric scale patterns: 1:100, 1:50, etc.
    metric_pattern = r'scale[:\s]+1\s*:\s*(\d+)'
    match = re.search(metric_pattern, text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    
    return None


def _find_dimensions_in_drawing_text(chars: List[Dict], page_width: float, page_height: float) -> Dict[str, List[float]]:
    """
    Find dimension values from character-level extraction.
    
    Building plans often have dimensions scattered across the drawing.
    This function tries to identify dimension strings based on their format
    and position on the page.
    """
    found_dims = {
        "horizontal": [],  # Likely widths/lengths
        "vertical": [],    # Likely heights
        "areas": [],
        "linear": []
    }
    
    if not chars:
        return found_dims
    
    # Group characters into text strings by proximity
    text_groups = []
    current_group = []
    last_x = -100
    last_y = -100
    
    for char in sorted(chars, key=lambda c: (round(c.get('top', 0) / 10), c.get('x0', 0))):
        x = char.get('x0', 0)
        y = char.get('top', 0)
        
        # If character is close to previous, add to group
        if abs(x - last_x) < 20 and abs(y - last_y) < 5:
            current_group.append(char)
        else:
            if current_group:
                text_groups.append(current_group)
            current_group = [char]
        
        last_x = x + char.get('width', 5)
        last_y = y
    
    if current_group:
        text_groups.append(current_group)
    
    # Extract dimension-like strings
    for group in text_groups:
        text = ''.join(c.get('text', '') for c in group)
        
        # Look for dimension patterns
        dim_value = _extract_number(text)
        if dim_value and dim_value > 0:
            # Categorize by position and format
            avg_y = sum(c.get('top', 0) for c in group) / len(group)
            
            if 'SF' in text.upper() or 'SQ' in text.upper():
                found_dims["areas"].append(dim_value)
            elif 'LF' in text.upper() or 'LINEAR' in text.upper():
                found_dims["linear"].append(dim_value)
            elif avg_y < page_height * 0.3:
                found_dims["horizontal"].append(dim_value)
            else:
                found_dims["vertical"].append(dim_value)
    
    return found_dims


def _extract_dimensions(text: str, tables: List[List[List[str]]] = None, chars: List[Dict] = None, 
                        page_width: float = 612, page_height: float = 792) -> Dict[str, Optional[float]]:
    """
    Extract building dimensions from text, tables, and drawing annotations.
    
    Uses multiple strategies:
    1. Direct text pattern matching (for spec documents)
    2. Table extraction (for building schedules)
    3. Drawing text extraction (for CAD-based plans)
    """
    dims = {
        "height": None,
        "area": None,
        "perimeter": None,
        "width": None,
        "length": None
    }
    
    # Strategy 1: Extract from tables first (most reliable for building plans)
    if tables:
        table_dims = _extract_dimensions_from_tables(tables)
        for key, value in table_dims.items():
            if value is not None:
                dims[key] = value
    
    # Strategy 2: Direct text extraction with enhanced patterns
    for dim_type in ["height", "area", "perimeter", "width", "length"]:
        if dims[dim_type] is None:
            value = _extract_dimension_from_text(text, dim_type)
            if value:
                dims[dim_type] = value
    
    # Strategy 3: Look for LxW format (common in building plans)
    if dims["width"] is None or dims["length"] is None:
        # Pattern: 100' x 50' or 100 x 50 or 100'×50'
        lxw_patterns = [
            r"(\d+['\u2019.\d]*)\s*[x×X]\s*(\d+['\u2019.\d]*)",
            r"(\d+\.?\d*)\s*(?:ft|feet|FT)?\s*[x×X]\s*(\d+\.?\d*)\s*(?:ft|feet|FT)?",
        ]
        
        for pattern in lxw_patterns:
            match = re.search(pattern, text)
            if match:
                val1 = _extract_number(match.group(1))
                val2 = _extract_number(match.group(2))
                if val1 and val2:
                    # Assign larger to length, smaller to width
                    if dims["length"] is None:
                        dims["length"] = max(val1, val2)
                    if dims["width"] is None:
                        dims["width"] = min(val1, val2)
                    break
    
    # Strategy 4: Character-level extraction for drawings
    if chars:
        drawing_dims = _find_dimensions_in_drawing_text(chars, page_width, page_height)
        
        # Use found dimensions as fallbacks
        if dims["area"] is None and drawing_dims["areas"]:
            # Take the largest area found (likely total roof area)
            dims["area"] = max(drawing_dims["areas"])
        
        if dims["perimeter"] is None and drawing_dims["linear"]:
            # Take the largest linear measurement (likely perimeter)
            dims["perimeter"] = max(drawing_dims["linear"])
    
    # Calculate derived values
    if dims["width"] and dims["length"]:
        if dims["area"] is None:
            dims["area"] = dims["width"] * dims["length"]
        if dims["perimeter"] is None:
            dims["perimeter"] = 2 * (dims["width"] + dims["length"])
    
    # Try to derive perimeter from area (assume square if only area known)
    if dims["perimeter"] is None and dims["area"]:
        # Estimate perimeter assuming roughly square building
        side = (dims["area"] ** 0.5)
        dims["perimeter"] = 4 * side
    
    return dims


def _extract_project_info(text: str) -> Dict[str, Optional[str]]:
    """Extract project name and location from text."""
    info = {
        "project_name": None,
        "location": None,
        "address": None,
        "city": None,
        "state": None
    }
    
    # Project name patterns (usually in title or header)
    # Look for lines that might be project names
    lines = text.split('\n')
    for line in lines[:20]:  # Check first 20 lines
        line = line.strip()
        if len(line) > 10 and len(line) < 100:
            # Common project name indicators
            if any(keyword in line.lower() for keyword in ["project", "building", "facility", "structure"]):
                if not info["project_name"] or len(line) > len(info["project_name"] or ""):
                    info["project_name"] = line
            # Or if it's a capitalized line that looks like a title
            elif line.isupper() and len(line.split()) <= 10:
                if not info["project_name"]:
                    info["project_name"] = line.title()
    
    # Location/Address patterns
    address_patterns = [
        r'location[:\s]+(.+?)(?:\n|$)',
        r'address[:\s]+(.+?)(?:\n|$)',
        r'project\s+location[:\s]+(.+?)(?:\n|$)',
    ]
    
    for pattern in address_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            if len(location) > 5:  # Reasonable address length
                info["location"] = location
                # Try to parse city/state
                city_state_match = re.search(r'([^,]+),\s*([A-Z]{2})\s+(\d{5})?', location)
                if city_state_match:
                    info["city"] = city_state_match.group(1).strip()
                    info["state"] = city_state_match.group(2).strip()
                break
    
    return info


def _extract_material_preferences(text: str) -> Dict[str, Any]:
    """Extract material preferences from text."""
    preferences = {
        "preferred_material": None,
        "material_requirements": [],
        "has_metal_roof": False
    }
    
    text_lower = text.lower()
    
    # Check for material preferences
    for material, keywords in MATERIAL_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                # Check if it's a requirement/preference
                context = text_lower[max(0, text_lower.find(keyword) - 50):
                                    text_lower.find(keyword) + 50]
                if any(word in context for word in ["required", "preferred", "specify", "use", "shall"]):
                    preferences["preferred_material"] = material
                    break
    
    # Check for metal roof
    metal_roof_patterns = [
        r'metal\s+roof',
        r'standing\s+seam',
        r'corrugated\s+metal',
        r'steel\s+roof'
    ]
    
    for pattern in metal_roof_patterns:
        if re.search(pattern, text_lower):
            preferences["has_metal_roof"] = True
            break
    
    return preferences


def _extract_compliance_standard(text: str) -> Optional[str]:
    """Extract which compliance standard is specified."""
    text_upper = text.upper()
    
    for standard in COMPLIANCE_STANDARDS:
        if standard.replace(" ", "") in text_upper.replace(" ", ""):
            # Normalize to standard format
            if "UL" in standard:
                return "UL 96A"
            elif "NFPA" in standard:
                return "NFPA 780"
    
    return None


def _extract_special_requirements(text: str) -> List[str]:
    """Extract special requirements and notes."""
    requirements = []
    
    # Look for common requirement sections
    requirement_keywords = [
        "special requirements",
        "additional requirements",
        "notes",
        "remarks",
        "exceptions",
        "deviations"
    ]
    
    text_lower = text.lower()
    
    for keyword in requirement_keywords:
        pattern = rf'{keyword}[:\s]+(.+?)(?=\n\n|\n[A-Z]{{3,}}|$)'
        matches = re.finditer(pattern, text_lower, re.IGNORECASE | re.DOTALL)
        for match in matches:
            req_text = match.group(1).strip()
            if len(req_text) > 20:  # Meaningful requirement
                requirements.append(req_text[:200])  # Limit length
    
    return requirements


def extract_spec_terms(path: Path) -> Dict[str, List[str]]:
    """
    Legacy function for backward compatibility.
    Extracts keyword hits from PDF.
    """
    hits: Dict[str, List[str]] = {k: [] for k in KEY_SECTIONS + COMPLIANCE_STANDARDS}
    
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            t_low = text.lower()

            # Section hits
            for sec in KEY_SECTIONS:
                if sec.lower() in t_low:
                    hits[sec].append(f"p{i}")

            # Compliance standard hits
            for term in COMPLIANCE_STANDARDS:
                if term.replace(" ", "").lower() in t_low.replace(" ", ""):
                    hits[term].append(f"p{i}")
    
    return {k: v for k, v in hits.items() if v}


def _try_ocr_extraction(page) -> str:
    """
    Attempt OCR extraction for scanned/image-based PDF pages.
    
    Requires pytesseract and PIL to be installed.
    Falls back gracefully if not available.
    """
    try:
        from PIL import Image
        import pytesseract
        
        # Convert page to image
        img = page.to_image(resolution=150)
        pil_image = img.original
        
        # Run OCR
        text = pytesseract.image_to_string(pil_image)
        return text
    except ImportError:
        logger.debug("OCR not available (pytesseract or PIL not installed)")
        return ""
    except Exception as e:
        logger.debug(f"OCR extraction failed: {e}")
        return ""


def _is_page_scanned(page, text: str) -> bool:
    """
    Detect if a page is likely a scanned image rather than native PDF text.
    
    Indicators:
    - Very little extractable text
    - Large image content
    - No selectable text objects
    """
    # If we got very little text but the page has significant size
    text_len = len(text.strip()) if text else 0
    
    # Check if page has images
    images = page.images if hasattr(page, 'images') else []
    
    # Heuristic: if less than 50 chars but page has large images
    if text_len < 50 and len(images) > 0:
        return True
    
    # Check if text density is very low compared to page size
    page_area = page.width * page.height
    if page_area > 0 and text_len / page_area < 0.0001:
        return True
    
    return False


def _extract_title_block_info(text: str, page_width: float = 612) -> Dict[str, Optional[str]]:
    """
    Extract project information from drawing title blocks.
    
    Title blocks typically contain:
    - Project name
    - Address/location
    - Drawing number
    - Scale information
    - Date
    """
    info = {
        "project_name": None,
        "location": None,
        "drawing_number": None,
        "scale": None,
        "date": None
    }
    
    lines = text.split('\n')
    
    # Look for common title block patterns
    for i, line in enumerate(lines):
        line_clean = line.strip()
        line_lower = line_clean.lower()
        
        # Project name indicators
        if any(kw in line_lower for kw in ['project:', 'project name:', 'job:', 'job name:']):
            # Take the rest of this line or next line
            name_match = re.search(r'(?:project|job)\s*(?:name)?[:\s]+(.+)', line, re.IGNORECASE)
            if name_match:
                info["project_name"] = name_match.group(1).strip()
            elif i + 1 < len(lines):
                info["project_name"] = lines[i + 1].strip()
        
        # Address patterns
        if any(kw in line_lower for kw in ['address:', 'location:', 'site:']):
            addr_match = re.search(r'(?:address|location|site)[:\s]+(.+)', line, re.IGNORECASE)
            if addr_match:
                info["location"] = addr_match.group(1).strip()
        
        # Drawing number
        if any(kw in line_lower for kw in ['dwg', 'drawing', 'sheet']):
            dwg_match = re.search(r'(?:dwg|drawing|sheet)\s*(?:no\.?|#|number)?[:\s]*([A-Z0-9-]+)', line, re.IGNORECASE)
            if dwg_match:
                info["drawing_number"] = dwg_match.group(1).strip()
        
        # Scale information
        if 'scale' in line_lower:
            scale_match = re.search(r'scale[:\s]+(.+?)(?:\s{3,}|$)', line, re.IGNORECASE)
            if scale_match:
                info["scale"] = scale_match.group(1).strip()
    
    return info


def extract_project_data(path: Path) -> Dict[str, Any]:
    """
    Extract structured project data from PDF specification or building plan.
    
    Supports multiple PDF types:
    - Text-based specification documents
    - Building plan PDFs with drawings
    - Scanned documents (with OCR if available)
    - CAD-exported PDFs with annotations
    
    Returns a dictionary with:
    - building_dimensions: {height, area, perimeter, width, length}
    - project_info: {project_name, location, address, city, state}
    - material_preferences: {preferred_material, has_metal_roof, material_requirements}
    - compliance_standard: "UL 96A" or "NFPA 780" or None
    - special_requirements: List of requirement strings
    - spec_terms: Dictionary of keyword hits (for backward compatibility)
    - num_corners: Estimated number of corners (default 4)
    - soil_type: Extracted soil type if mentioned
    - extraction_metadata: Information about the extraction process
    """
    
    # Combine all text from PDF using multiple extraction methods
    full_text = ""
    page_texts = []
    all_tables = []
    all_chars = []
    page_dimensions = []
    ocr_used = False
    
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Get page dimensions
            page_width = page.width
            page_height = page.height
            page_dimensions.append((page_width, page_height))
            
            # Primary text extraction
            text = page.extract_text() or ""
            
            # Check if page appears to be scanned/image-based
            if _is_page_scanned(page, text):
                logger.info(f"Page {page_num} appears to be scanned, attempting OCR")
                ocr_text = _try_ocr_extraction(page)
                if ocr_text:
                    text = ocr_text
                    ocr_used = True
            
            full_text += text + "\n\n"
            page_texts.append(text)
            
            # Extract tables from page
            try:
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
            except Exception as e:
                logger.debug(f"Table extraction failed on page {page_num}: {e}")
            
            # Extract character-level data for drawing analysis
            try:
                chars = page.chars
                if chars:
                    all_chars.extend(chars)
            except Exception as e:
                logger.debug(f"Character extraction failed on page {page_num}: {e}")
    
    # Get average page dimensions
    avg_width = sum(d[0] for d in page_dimensions) / len(page_dimensions) if page_dimensions else 612
    avg_height = sum(d[1] for d in page_dimensions) / len(page_dimensions) if page_dimensions else 792
    
    # Extract different types of information using enhanced methods
    dimensions = _extract_dimensions(full_text, all_tables, all_chars, avg_width, avg_height)
    project_info = _extract_project_info(full_text)
    material_prefs = _extract_material_preferences(full_text)
    compliance = _extract_compliance_standard(full_text)
    requirements = _extract_special_requirements(full_text)
    spec_terms = extract_spec_terms(path)  # For backward compatibility
    
    # Try title block extraction for building plans
    title_block_info = _extract_title_block_info(full_text, avg_width)
    
    # Merge title block info if main extraction missed it
    if not project_info["project_name"] and title_block_info["project_name"]:
        project_info["project_name"] = title_block_info["project_name"]
    if not project_info["location"] and title_block_info["location"]:
        project_info["location"] = title_block_info["location"]
    
    # Extract scale for future dimension scaling
    scale_factor = _extract_scale_factor(full_text)
    
    # Estimate number of corners (default 4, but could be more for complex shapes)
    num_corners = 4
    corners_patterns = [
        r'(\d+)\s*(?:corners?|sides?)',
        r'(?:corners?|sides?)[:\s]+(\d+)',
    ]
    for pattern in corners_patterns:
        match = re.search(pattern, full_text.lower())
        if match:
            try:
                num_corners = int(match.group(1))
                break
            except ValueError:
                pass
    
    # Extract soil type
    soil_type = "normal"
    soil_patterns = {
        "rocky": ["rocky", "rock", "stone", "bedrock", "granite", "limestone"],
        "sandy": ["sandy", "sand", "loose", "gravel"],
        "clay": ["clay", "clayey", "expansive"],
        "wet": ["wet", "marshy", "swamp", "high water table"]
    }
    
    for soil, keywords in soil_patterns.items():
        if any(keyword in full_text.lower() for keyword in keywords):
            soil_type = soil
            break
    
    # Determine PDF type for metadata
    pdf_type = "specification"
    if all_tables and len(all_tables) > 3:
        pdf_type = "building_plan_with_tables"
    elif ocr_used:
        pdf_type = "scanned_document"
    elif scale_factor:
        pdf_type = "architectural_drawing"
    elif len(full_text) < 500 and len(all_chars) > 1000:
        pdf_type = "cad_drawing"
    
    # Build result dictionary
    result = {
        "building_dimensions": dimensions,
        "project_info": project_info,
        "material_preferences": material_prefs,
        "compliance_standard": compliance,
        "special_requirements": requirements,
        "spec_terms": spec_terms,
        "num_corners": num_corners,
        "soil_type": soil_type,
        "extraction_metadata": {
            "pdf_path": str(path),
            "pdf_type": pdf_type,
            "pages_scanned": len(page_texts),
            "total_text_length": len(full_text),
            "tables_found": len(all_tables),
            "scale_factor": scale_factor,
            "ocr_used": ocr_used,
            "extraction_confidence": _calculate_extraction_confidence(dimensions, project_info)
        }
    }
    
    return result


def _calculate_extraction_confidence(dimensions: Dict, project_info: Dict) -> str:
    """
    Calculate confidence level of the extraction based on what was found.
    
    Returns: 'high', 'medium', or 'low'
    """
    score = 0
    
    # Dimensions scoring
    if dimensions.get("height"):
        score += 2
    if dimensions.get("area"):
        score += 2
    if dimensions.get("perimeter"):
        score += 2
    if dimensions.get("width") and dimensions.get("length"):
        score += 1
    
    # Project info scoring
    if project_info.get("project_name"):
        score += 1
    if project_info.get("location"):
        score += 1
    
    # Determine confidence
    if score >= 7:
        return "high"
    elif score >= 4:
        return "medium"
    else:
        return "low"
