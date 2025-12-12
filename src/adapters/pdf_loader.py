"""
Enhanced PDF Parser for Lightning Protection Project Specifications

This module extracts structured data from PDF specification documents including:
- Building dimensions (height, area, perimeter)
- Project name and location
- Material preferences
- Special requirements
- Compliance standards
"""

from pathlib import Path
import pdfplumber
import re
from typing import Dict, List, Optional, Any
from datetime import datetime


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


def _extract_dimensions(text: str) -> Dict[str, Optional[float]]:
    """Extract building dimensions from text."""
    dims = {
        "height": None,
        "area": None,
        "perimeter": None,
        "width": None,
        "length": None
    }
    
    text_lower = text.lower()
    
    # Height patterns
    height_patterns = [
        r'height[:\s]+(\d+\.?\d*)\s*(?:ft|feet|\')',
        r'(\d+\.?\d*)\s*(?:ft|feet|\')\s*(?:tall|high|height)',
        r'building[:\s]+(\d+\.?\d*)\s*(?:ft|feet|\')',
        r'(\d+\.?\d*)\s*(?:story|stories|story\s*building)'
    ]
    
    for pattern in height_patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                dims["height"] = float(match.group(1))
                break
            except (ValueError, IndexError):
                continue
    
    # Area patterns
    area_patterns = [
        r'(?:roof|building|total)[:\s]+area[:\s]+(\d+[,\d]*\.?\d*)\s*(?:sq\s*ft|sqft|square\s*feet)',
        r'(\d+[,\d]*\.?\d*)\s*(?:sq\s*ft|sqft|square\s*feet)',
        r'(\d+[,\d]*\.?\d*)\s*(?:sf|sq\.?\s*ft\.?)'
    ]
    
    for pattern in area_patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                area_str = match.group(1).replace(",", "")
                dims["area"] = float(area_str)
                break
            except (ValueError, IndexError):
                continue
    
    # Perimeter patterns - handle various formats including "linear feet"
    perimeter_patterns = [
        r'perimeter[:\s]+(?:length[:\s]+)?(\d+[,\d]*\.?\d*)\s*(?:linear\s+)?(?:ft|feet|\')',
        r'(\d+[,\d]*\.?\d*)\s*(?:linear\s+)?(?:ft|feet|\')\s*(?:perimeter|linear)',
        r'perimeter[:\s]+(\d+[,\d]*\.?\d*)',
        r'(\d+[,\d]*\.?\d*)\s*(?:ft|feet|\')\s*perimeter'
    ]
    
    for pattern in perimeter_patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                # Remove commas from the number before converting to float
                num_str = match.group(1).replace(',', '')
                dims["perimeter"] = float(num_str)
                break
            except (ValueError, IndexError):
                continue
    
    # Width and Length (for calculating perimeter if missing)
    width_match = re.search(r'width[:\s]+(\d+\.?\d*)\s*(?:ft|feet|\')', text_lower)
    length_match = re.search(r'length[:\s]+(\d+\.?\d*)\s*(?:ft|feet|\')', text_lower)
    
    if width_match:
        try:
            dims["width"] = float(width_match.group(1))
        except (ValueError, IndexError):
            pass
    
    if length_match:
        try:
            dims["length"] = float(length_match.group(1))
        except (ValueError, IndexError):
            pass
    
    # Calculate perimeter from width/length if available
    if not dims["perimeter"] and dims["width"] and dims["length"]:
        dims["perimeter"] = 2 * (dims["width"] + dims["length"])
    
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


def extract_project_data(path: Path) -> Dict[str, Any]:
    """
    Extract structured project data from PDF specification.
    
    Returns a dictionary with:
    - building_dimensions: {height, area, perimeter, width, length}
    - project_info: {project_name, location, address, city, state}
    - material_preferences: {preferred_material, has_metal_roof, material_requirements}
    - compliance_standard: "UL 96A" or "NFPA 780" or None
    - special_requirements: List of requirement strings
    - spec_terms: Dictionary of keyword hits (for backward compatibility)
    - num_corners: Estimated number of corners (default 4)
    - soil_type: Extracted soil type if mentioned
    """
    
    # Combine all text from PDF
    full_text = ""
    page_texts = []
    
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n\n"
            page_texts.append(text)
    
    # Extract different types of information
    dimensions = _extract_dimensions(full_text)
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
        "extraction_metadata": {
            "pdf_path": str(path),
            "pages_scanned": len(page_texts),
            "total_text_length": len(full_text)
        }
    }
    
    return result
