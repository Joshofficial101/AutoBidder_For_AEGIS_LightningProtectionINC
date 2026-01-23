"""
Enhanced PDF Parser for Lightning Protection Project Specifications

This module extracts structured data from various PDF document types including:
- Text-based specification documents
- Building plan PDFs with drawings (CAD-style)
- Scanned documents (with OCR support)
- Tabular data and forms

Supports extraction of:
- Building dimensions (height, area, perimeter)
- Project name and location
- Material preferences
- Special requirements
- Compliance standards

For CAD-style building plans with minimal text, use the advanced parser
which includes OCR and computer vision capabilities.
"""

from pathlib import Path
import pdfplumber
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import math


# Keywords for different types of information
KEY_SECTIONS = ["PART 1", "PART 2", "PART 3", "SUBMITTALS", "INSTALLATION", 
                "GROUNDING", "AIR TERMINALS", "CONDUCTORS", "BONDING"]

COMPLIANCE_STANDARDS = ["UL 96A", "NFPA 780", "UL96A", "NFPA780"]

MATERIAL_KEYWORDS = {
    "copper": ["copper", "cu", "copper clad"],
    "aluminum": ["aluminum", "al", "aluminium"],
    "bimetal": ["bimetal", "bi-metal", "bimetallic"]
}


def _extract_number(text: str, unit: str = None) -> Optional[float]:
    """
    Extract a number from text, handling various formats.
    
    Examples: "35 feet", "35'", "35 ft", "35.5", "35,000 sq ft"
    """
    if not text:
        return None
    
    # Remove commas and common words
    text = text.replace(",", "").replace("'", " ").replace('"', " ")
    
    # Pattern for numbers with optional decimals
    patterns = [
        r'(\d+\.?\d*)\s*' + (unit or r'ft|feet|sq\s*ft|sqft|square\s*feet|inches?|in'),
        r'(\d+\.?\d*)',  # Just a number
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    
    return None


def _parse_dimension_value(text: str) -> Optional[float]:
    """
    Parse a dimension value from various formats.
    
    Handles:
    - "35 feet" or "35ft" or "35'"
    - "35'-6"" (feet and inches)
    - "35.5"
    - "35,000"
    """
    if not text:
        return None
    
    text = text.strip()
    
    # Handle feet and inches format: 35'-6" or 35' 6"
    feet_inches_match = re.search(r"(\d+)['\s-]+(\d+(?:\.\d+)?)[\"″]?", text)
    if feet_inches_match:
        try:
            feet = float(feet_inches_match.group(1))
            inches = float(feet_inches_match.group(2))
            return feet + (inches / 12.0)
        except (ValueError, IndexError):
            pass
    
    # Handle simple number with optional unit
    # Remove commas from numbers
    text_clean = text.replace(",", "")
    number_match = re.search(r"(\d+(?:\.\d+)?)", text_clean)
    if number_match:
        try:
            return float(number_match.group(1))
        except ValueError:
            pass
    
    return None


def _extract_dimensions_from_lxw(text: str) -> Dict[str, Optional[float]]:
    """
    Extract dimensions from length x width format common in building plans.
    
    Examples:
    - "40' x 60'" 
    - "40x60"
    - "40 ft x 60 ft"
    - "40'-0" x 60'-0""
    - "Building: 100' x 200'"
    """
    dims = {"length": None, "width": None, "area": None, "perimeter": None}
    
    # Various patterns for LxW format
    lxw_patterns = [
        # 40' x 60' or 40ft x 60ft
        r"(\d+(?:['\-]\d+)?(?:\.\d+)?)['\s]*(?:ft|feet)?[\s]*[xX×][\s]*(\d+(?:['\-]\d+)?(?:\.\d+)?)['\s]*(?:ft|feet)?",
        # Building dimensions often in format: "Building Size: 40 x 60"
        r"(?:building|structure|footprint|size)[:\s]+(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)",
    ]
    
    for pattern in lxw_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                val1 = _parse_dimension_value(match[0])
                val2 = _parse_dimension_value(match[1])
                if val1 and val2:
                    # Assign larger value as length, smaller as width (convention)
                    dims["length"] = max(val1, val2)
                    dims["width"] = min(val1, val2)
                    dims["area"] = dims["length"] * dims["width"]
                    dims["perimeter"] = 2 * (dims["length"] + dims["width"])
                    return dims
            except (ValueError, IndexError):
                continue
    
    return dims


def _extract_dimensions_from_scale(text: str) -> Dict[str, Optional[float]]:
    """
    Extract dimensions from scale notations in building plans.
    
    Examples:
    - "Scale: 1" = 20'"
    - "1/4" = 1'-0""
    """
    # For now, return empty - this would require image processing for actual drawing measurement
    return {"length": None, "width": None, "area": None, "perimeter": None}


def _extract_dimensions_from_tables(tables: List[List]) -> Dict[str, Optional[float]]:
    """
    Extract dimensions from PDF tables.
    
    Tables often contain dimension data in formats like:
    | Dimension | Value |
    | Height    | 35 ft |
    | Area      | 5000 sq ft |
    """
    dims = {
        "height": None,
        "area": None,
        "perimeter": None,
        "width": None,
        "length": None
    }
    
    dimension_keywords = {
        "height": ["height", "tall", "elevation", "story", "stories", "floors"],
        "area": ["area", "square feet", "sq ft", "sqft", "sf", "footage"],
        "perimeter": ["perimeter", "linear feet", "lf", "boundary"],
        "width": ["width", "wide"],
        "length": ["length", "long", "depth"]
    }
    
    for table in tables:
        if not table:
            continue
        
        for row in table:
            if not row or len(row) < 2:
                continue
            
            # Check each cell for dimension keywords
            row_text = " ".join(str(cell).lower() for cell in row if cell)
            
            for dim_type, keywords in dimension_keywords.items():
                if dims[dim_type] is not None:
                    continue
                    
                for keyword in keywords:
                    if keyword in row_text:
                        # Try to extract number from this row
                        for cell in row:
                            if cell:
                                value = _parse_dimension_value(str(cell))
                                if value and value > 0:
                                    dims[dim_type] = value
                                    break
                        break
    
    return dims


def _extract_dimensions(text: str, tables: List[List] = None) -> Dict[str, Optional[float]]:
    """
    Extract building dimensions from text and tables using multiple strategies.
    """
    dims = {
        "height": None,
        "area": None,
        "perimeter": None,
        "width": None,
        "length": None
    }
    
    text_lower = text.lower()
    
    # Strategy 1: Try to extract from LxW format (common in building plans)
    lxw_dims = _extract_dimensions_from_lxw(text)
    for key, value in lxw_dims.items():
        if value is not None:
            dims[key] = value
    
    # Strategy 2: Try to extract from tables
    if tables:
        table_dims = _extract_dimensions_from_tables(tables)
        for key, value in table_dims.items():
            if dims[key] is None and value is not None:
                dims[key] = value
    
    # Strategy 3: Regex patterns for explicit dimension mentions
    
    # Height patterns - expanded for building plans
    height_patterns = [
        r'(?:building\s+)?height[:\s]+(\d+\.?\d*)\s*(?:ft|feet|\')',
        r'(\d+\.?\d*)\s*(?:ft|feet|\')\s*(?:tall|high|height)',
        r'(?:eave|ridge|roof)\s+height[:\s]+(\d+\.?\d*)',
        r'(\d+)\s*(?:story|stories|floors?)\s*(?:building)?',  # Convert stories to height
        r'(?:total\s+)?height[:\s]+(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*(?:ft|feet|\')\s+(?:above|from)\s+grade',
        r'max(?:imum)?\s+height[:\s]+(\d+\.?\d*)',
    ]
    
    if dims["height"] is None:
        for pattern in height_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    value = float(match.group(1))
                    # Check if this is stories (typically < 20) and convert
                    if "stor" in pattern or "floor" in pattern:
                        if value < 20:  # Likely stories
                            value = value * 12  # Assume 12 ft per story
                    dims["height"] = value
                    break
                except (ValueError, IndexError):
                    continue
    
    # Area patterns - expanded
    area_patterns = [
        r'(?:roof|building|total|floor)[:\s]*area[:\s]+(\d+[,\d]*\.?\d*)\s*(?:sq\s*ft|sqft|square\s*feet|sf)',
        r'(\d+[,\d]*\.?\d*)\s*(?:sq\s*ft|sqft|square\s*feet|sf)',
        r'(?:area|size)[:\s]+(\d+[,\d]*\.?\d*)',
        r'(\d+[,\d]*\.?\d*)\s*square\s*(?:feet|foot)',
        r'footprint[:\s]+(\d+[,\d]*\.?\d*)',
    ]
    
    if dims["area"] is None:
        for pattern in area_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    area_str = match.group(1).replace(",", "")
                    dims["area"] = float(area_str)
                    break
                except (ValueError, IndexError):
                    continue
    
    # Perimeter patterns - expanded for various formats
    perimeter_patterns = [
        r'perimeter[:\s]+(?:length[:\s]+)?(\d+[,\d]*\.?\d*)\s*(?:linear\s+)?(?:ft|feet|\'|lf)',
        r'(\d+[,\d]*\.?\d*)\s*(?:linear\s+)?(?:ft|feet|\'|lf)\s*(?:perimeter|linear)',
        r'perimeter[:\s]+(\d+[,\d]*\.?\d*)',
        r'(\d+[,\d]*\.?\d*)\s*(?:ft|feet|\')\s*perimeter',
        r'boundary[:\s]+(\d+[,\d]*\.?\d*)',
        r'roof\s+edge[:\s]+(\d+[,\d]*\.?\d*)',
    ]
    
    if dims["perimeter"] is None:
        for pattern in perimeter_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    num_str = match.group(1).replace(',', '')
                    dims["perimeter"] = float(num_str)
                    break
                except (ValueError, IndexError):
                    continue
    
    # Width patterns
    width_patterns = [
        r'width[:\s]+(\d+\.?\d*)\s*(?:ft|feet|\')',
        r'(\d+\.?\d*)\s*(?:ft|feet|\')\s*wide',
        r'(?:building\s+)?width[:\s]+(\d+\.?\d*)',
    ]
    
    if dims["width"] is None:
        for pattern in width_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    dims["width"] = float(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
    
    # Length patterns (avoid matching "linear feet" for perimeter)
    length_patterns = [
        r'(?:building\s+)?length[:\s]+(\d+\.?\d*)\s*(?:ft|feet|\')',
        r'(\d+\.?\d*)\s*(?:ft|feet|\')\s+long(?!\s*(?:itud|er))',  # "long" but not "longer" or "longitude"
        r'depth[:\s]+(\d+\.?\d*)\s*(?:ft|feet|\')',
    ]
    
    if dims["length"] is None:
        for pattern in length_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    value = float(match.group(1))
                    # Don't use perimeter-like values as length
                    if dims["perimeter"] and abs(value - dims["perimeter"]) < 1:
                        continue  # Skip, this is likely the perimeter
                    dims["length"] = value
                    break
                except (ValueError, IndexError):
                    continue
    
    # Strategy 4: Calculate missing values from available data
    
    # Calculate perimeter from width/length if available
    if dims["perimeter"] is None and dims["width"] and dims["length"]:
        dims["perimeter"] = 2 * (dims["width"] + dims["length"])
    
    # Calculate area from width/length if available
    if dims["area"] is None and dims["width"] and dims["length"]:
        dims["area"] = dims["width"] * dims["length"]
    
    # Estimate width/length from area if we have area but not dimensions
    # Assume square-ish building
    if dims["area"] and not dims["width"] and not dims["length"]:
        estimated_side = math.sqrt(dims["area"])
        dims["width"] = estimated_side
        dims["length"] = estimated_side
        if dims["perimeter"] is None:
            dims["perimeter"] = 4 * estimated_side
    
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
    
    # Try to find explicit project/facility name patterns first
    explicit_patterns = [
        r'(?:for|at|project[:\s]*)\s+([A-Z][A-Za-z\s]+(?:Center|Plaza|Tower|Complex|Building|Facility|Campus|Park|Place))',
        r'(?:facility|building)\s+(?:name|is)[:\s]+(.+?)(?:\n|$)',
        r'project\s+(?:name|title)[:\s]+(.+?)(?:\n|$)',
    ]
    
    for pattern in explicit_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name) > 5 and len(name) < 100:
                info["project_name"] = name
                break
    
    # If no explicit pattern found, look for likely project name lines
    if not info["project_name"]:
        lines = text.split('\n')
        for line in lines[:30]:  # Check first 30 lines
            line = line.strip()
            
            # Skip bullet points and list items
            if line.startswith(('•', '-', '*', '1.', '2.', '3.')):
                continue
            
            if len(line) > 10 and len(line) < 100:
                # Common project name endings
                project_name_endings = [
                    "center", "plaza", "tower", "complex", "warehouse", 
                    "building", "facility", "campus", "park", "place"
                ]
                
                line_lower = line.lower()
                
                # Check if line ends with a project name indicator
                if any(line_lower.endswith(ending) for ending in project_name_endings):
                    info["project_name"] = line
                    break
                # Or if it contains specific patterns that look like facility names
                elif any(f" {ending}" in line_lower for ending in project_name_endings):
                    # Extract the name portion
                    for ending in project_name_endings:
                        if f" {ending}" in line_lower:
                            idx = line_lower.find(f" {ending}")
                            # Get words before and including the ending
                            potential_name = line[:idx + len(ending) + 1].strip()
                            # Clean up - remove leading text before actual name
                            words = potential_name.split()
                            # Find where the name likely starts (capital letter)
                            for i, word in enumerate(words):
                                if word[0].isupper() and word.lower() not in ['the', 'a', 'an', 'for', 'at']:
                                    info["project_name"] = ' '.join(words[i:])
                                    break
                            if info["project_name"]:
                                break
                    if info["project_name"]:
                        break
                # All caps titles
                elif line.isupper() and len(line.split()) <= 10:
                    info["project_name"] = line.title()
                    break
    
    # Location/Address patterns - expanded
    address_patterns = [
        r'location[:\s]+(.+?)(?:\n|$)',
        r'address[:\s]+(.+?)(?:\n|$)',
        r'project\s+location[:\s]+(.+?)(?:\n|$)',
        r'site\s+address[:\s]+(.+?)(?:\n|$)',
        r'job\s+site[:\s]+(.+?)(?:\n|$)',
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
        "has_metal_roof": False,
        "roof_type": None
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
    
    # Check for roof types
    roof_types = {
        "metal": ["metal roof", "standing seam", "corrugated metal", "steel roof", "aluminum roof"],
        "flat": ["flat roof", "flat membrane", "built-up roof", "bur", "tpo", "epdm"],
        "shingle": ["shingle", "asphalt roof", "composition roof"],
        "tile": ["tile roof", "clay tile", "concrete tile"],
        "slate": ["slate roof", "natural slate"],
    }
    
    for roof_type, patterns in roof_types.items():
        for pattern in patterns:
            if pattern in text_lower:
                preferences["roof_type"] = roof_type
                if roof_type == "metal":
                    preferences["has_metal_roof"] = True
                break
        if preferences["roof_type"]:
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
        "deviations",
        "specifications",
        "requirements"
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


def _extract_from_drawing_annotations(pdf_page) -> Dict[str, Any]:
    """
    Extract text and annotations from PDF drawing pages.
    
    Building plans often have dimension callouts as annotations or text boxes.
    """
    extracted = {
        "dimension_texts": [],
        "annotations": [],
        "text_boxes": []
    }
    
    try:
        # Extract text objects with positions
        if hasattr(pdf_page, 'chars'):
            chars = pdf_page.chars
            # Group nearby characters into dimension callouts
            # Dimension text often stands alone near drawing elements
            
        # Extract annotations if present
        if hasattr(pdf_page, 'annots') and pdf_page.annots:
            for annot in pdf_page.annots:
                if isinstance(annot, dict):
                    content = annot.get('contents', '')
                    if content:
                        extracted["annotations"].append(content)
    except Exception:
        pass
    
    return extracted


def _is_drawing_page(page_text: str, page) -> bool:
    """
    Detect if a PDF page is likely a building drawing/plan.
    
    Drawing pages typically have:
    - Very little text (usually just labels and dimensions)
    - Scale notations
    - Drawing title blocks
    - CAD/drawing software markers
    """
    text_length = len(page_text or "")
    text_lower = (page_text or "").lower()
    
    # Check for explicit drawing indicators first
    drawing_indicators = [
        "scale:", "scale =", "1\"=", "1'=", "1/4\"", "1/8\"",
        "plan view", "elevation", "section view", "floor plan",
        "north arrow", "dwg", "autocad", "revit", "cad"
    ]
    
    if any(indicator in text_lower for indicator in drawing_indicators):
        return True
    
    # Text-based documents have substantial text content
    # Very little text (< 200 chars) strongly suggests a drawing page
    if text_length < 200:
        return True
    
    # Documents with normal paragraphs are specification documents
    # Drawing pages have sparse, label-like text
    # Check for sentence structure indicators
    sentence_indicators = [". ", "! ", "? ", ":\n", "dear ", "please ", "sincerely"]
    has_sentences = any(ind in text_lower for ind in sentence_indicators)
    
    if has_sentences and text_length > 300:
        return False
    
    return False


def _extract_from_building_plan(pdf_path: Path) -> Dict[str, Any]:
    """
    Special extraction logic for building plan PDFs.
    
    Building plans require different parsing strategies:
    - Look for dimension annotations
    - Parse title blocks for project info
    - Handle scale drawings
    """
    plan_data = {
        "dimensions": {},
        "scale": None,
        "sheets": [],
        "title_block_info": {}
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                
                # Check for scale
                scale_match = re.search(r'scale[:\s]*(\d+)["\']?\s*=\s*(\d+)[\'"\s-]*(?:\d+)?', text, re.IGNORECASE)
                if scale_match and not plan_data["scale"]:
                    plan_data["scale"] = f'{scale_match.group(1)}" = {scale_match.group(2)}\''
                
                # Try to extract dimensions from this page
                page_dims = _extract_dimensions(text, page.extract_tables())
                
                for key, value in page_dims.items():
                    if value and not plan_data["dimensions"].get(key):
                        plan_data["dimensions"][key] = value
                
                # Store sheet info
                sheet_info = {
                    "page": i + 1,
                    "is_drawing": _is_drawing_page(text, page),
                    "text_length": len(text)
                }
                plan_data["sheets"].append(sheet_info)
                
    except Exception:
        pass
    
    return plan_data


def extract_spec_terms(path: Path) -> Dict[str, List[str]]:
    """
    Legacy function for backward compatibility.
    Extracts keyword hits from PDF.
    """
    hits: Dict[str, List[str]] = {k: [] for k in KEY_SECTIONS + COMPLIANCE_STANDARDS}
    
    try:
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
    except Exception:
        pass
    
    return {k: v for k, v in hits.items() if v}


def extract_project_data(path: Path) -> Dict[str, Any]:
    """
    Extract structured project data from PDF specification.
    
    Handles multiple PDF types:
    - Text-based specification documents
    - Building plan PDFs with drawings
    - Mixed documents
    
    Returns a dictionary with:
    - building_dimensions: {height, area, perimeter, width, length}
    - project_info: {project_name, location, address, city, state}
    - material_preferences: {preferred_material, has_metal_roof, material_requirements, roof_type}
    - compliance_standard: "UL 96A" or "NFPA 780" or None
    - special_requirements: List of requirement strings
    - spec_terms: Dictionary of keyword hits (for backward compatibility)
    - num_corners: Estimated number of corners (default 4)
    - soil_type: Extracted soil type if mentioned
    - pdf_type: Detected PDF type (specification, building_plan, mixed)
    """
    
    # Combine all text from PDF
    full_text = ""
    page_texts = []
    all_tables = []
    drawing_pages = 0
    text_pages = 0
    
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text + "\n\n"
                page_texts.append(text)
                
                # Extract tables from each page
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
                
                # Classify page type
                if _is_drawing_page(text, page):
                    drawing_pages += 1
                else:
                    text_pages += 1
    except Exception as e:
        # Return empty result on error
        return {
            "building_dimensions": {"height": None, "area": None, "perimeter": None, "width": None, "length": None},
            "project_info": {"project_name": None, "location": None, "address": None, "city": None, "state": None},
            "material_preferences": {"preferred_material": None, "has_metal_roof": False, "material_requirements": [], "roof_type": None},
            "compliance_standard": None,
            "special_requirements": [],
            "spec_terms": {},
            "num_corners": 4,
            "soil_type": "normal",
            "pdf_type": "unknown",
            "extraction_metadata": {
                "pdf_path": str(path),
                "error": str(e),
                "pages_scanned": 0,
                "total_text_length": 0
            }
        }
    
    # Determine PDF type
    total_pages = len(page_texts)
    if total_pages == 0:
        pdf_type = "empty"
    elif drawing_pages > text_pages:
        pdf_type = "building_plan"
    elif drawing_pages > 0:
        pdf_type = "mixed"
    else:
        pdf_type = "specification"
    
    # Extract different types of information
    dimensions = _extract_dimensions(full_text, all_tables)
    
    # If this looks like a building plan, try additional extraction
    if pdf_type in ["building_plan", "mixed"]:
        plan_data = _extract_from_building_plan(path)
        # Merge plan dimensions with existing dimensions
        for key, value in plan_data.get("dimensions", {}).items():
            if value and dimensions.get(key) is None:
                dimensions[key] = value
    
    project_info = _extract_project_info(full_text)
    material_prefs = _extract_material_preferences(full_text)
    compliance = _extract_compliance_standard(full_text)
    requirements = _extract_special_requirements(full_text)
    spec_terms = extract_spec_terms(path)  # For backward compatibility
    
    # Estimate number of corners (default 4, but could be more for complex shapes)
    num_corners = 4
    corners_match = re.search(r'(\d+)\s*(?:corners?|sides?)', full_text.lower())
    if corners_match:
        try:
            num_corners = int(corners_match.group(1))
        except ValueError:
            pass
    
    # For L-shaped or complex buildings
    if any(shape in full_text.lower() for shape in ["l-shaped", "l shaped", "t-shaped", "t shaped", "u-shaped", "u shaped"]):
        num_corners = 6  # L-shaped buildings typically have 6 corners
    
    # Extract soil type
    soil_type = "normal"
    soil_patterns = {
        "rocky": ["rocky", "rock", "stone", "bedrock"],
        "sandy": ["sandy", "sand", "loose"],
        "clay": ["clay", "clayey"]
    }
    
    for soil, keywords in soil_patterns.items():
        if any(keyword in full_text.lower() for keyword in keywords):
            soil_type = soil
            break
    
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
        "pdf_type": pdf_type,
        "extraction_metadata": {
            "pdf_path": str(path),
            "pages_scanned": len(page_texts),
            "total_text_length": len(full_text),
            "drawing_pages": drawing_pages,
            "text_pages": text_pages,
            "tables_found": len(all_tables)
        }
    }
    
    return result


def parse_pdf_flexible(path: Path) -> Dict[str, Any]:
    """
    Flexible PDF parser that adapts to different document types.
    
    This is the recommended entry point for parsing PDFs as it:
    - Auto-detects PDF type (specification, building plan, mixed)
    - Uses appropriate extraction strategies (basic text or advanced OCR/CV)
    - Returns normalized results
    
    Args:
        path: Path to the PDF file
        
    Returns:
        Dictionary with extracted project data
    """
    # Quick check: Is this a CAD-style drawing with minimal text?
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > 0:
                # Sample first few pages
                total_text_length = 0
                pages_sampled = min(3, len(pdf.pages))
                
                for i in range(pages_sampled):
                    text = pdf.pages[i].extract_text() or ""
                    total_text_length += len(text)
                
                avg_text_per_page = total_text_length / pages_sampled
                
                # If very little text (< 1000 chars/page), likely a CAD drawing
                # Use FAST parser (text-only, no OCR) for speed
                if avg_text_per_page < 1000:
                    try:
                        from .pdf_loader_fast import parse_cad_fast
                        print(f"Detected CAD-style building plan. Using FAST text-only parser...")
                        result = parse_cad_fast(path)
                        
                        # Normalize the result to match expected format
                        normalized = {
                            "building_dimensions": {
                                "height": result.get("building_height_ft"),
                                "area": result.get("roof_area_sqft"),
                                "perimeter": result.get("perimeter_ft"),
                                "width": result.get("width_ft"),
                                "length": result.get("length_ft")
                            },
                            "project_info": {
                                "project_name": result.get("project_name"),
                                "location": result.get("location"),
                                "address": None,
                                "city": None,
                                "state": None
                            },
                            "material_preferences": {
                                "preferred_material": None,
                                "has_metal_roof": False,
                                "material_requirements": [],
                                "roof_type": None
                            },
                            "compliance_standard": None,
                            "special_requirements": [],
                            "spec_terms": {},
                            "num_corners": result.get("num_corners", 4),
                            "soil_type": "normal",
                            "pdf_type": result.get("pdf_type", "cad_building_plan"),
                            "extraction_metadata": result.get("extraction_metadata", {})
                        }
                        return normalized
                    except ImportError:
                        print("Advanced parser not available. Using basic text extraction...")
                        pass  # Fall through to basic parser
    except Exception:
        pass  # Fall through to basic parser
    
    # Use standard text-based parser
    return extract_project_data(path)
