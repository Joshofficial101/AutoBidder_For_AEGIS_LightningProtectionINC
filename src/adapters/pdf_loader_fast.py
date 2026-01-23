"""
FAST PDF Parser - Optimized for Speed

This parser trades some accuracy for speed, extracting only essential data
from CAD building plans in 1-5 seconds instead of minutes.

Strategy:
- Only scan first 3 pages (most dimension info is there)
- Use regex patterns instead of OCR
- Skip computer vision
- Extract dimensions from text only
"""

from pathlib import Path
import pdfplumber
import re
from typing import Dict, Optional, Any
import math


def extract_dimensions_fast(text: str) -> Dict[str, Optional[float]]:
    """Fast dimension extraction using regex patterns only."""
    dims = {
        "height": None,
        "area": None,
        "perimeter": None,
        "width": None,
        "length": None
    }
    
    # Pattern: Look for length x width (common in CAD title blocks)
    # Examples: "100' x 200'", "100x200", "100 ft x 200 ft"
    lxw_patterns = [
        r'(\d+)[\'"\s-]*[xX×][\s-]*(\d+)[\'"\s]*',
        r'building[:\s]+(\d+)[\'"\s-]*[xX×][\s-]*(\d+)',
    ]
    
    for pattern in lxw_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                val1, val2 = float(match[0]), float(match[1])
                # Filter: Reasonable building dimensions (10-1000 ft)
                if 10 <= val1 <= 1000 and 10 <= val2 <= 1000:
                    dims["length"] = max(val1, val2)
                    dims["width"] = min(val1, val2)
                    dims["area"] = val1 * val2
                    dims["perimeter"] = 2 * (val1 + val2)
                    break
            except (ValueError, IndexError):
                continue
        if dims["length"]:
            break
    
    # Pattern: Building height
    height_patterns = [
        r'height[:\s]+(\d+(?:\.\d+)?)[\'"\s]*',
        r'(\d+)[\'"\s]*(?:ft|feet)\s+(?:high|tall)',
        r'(\d+)\s*(?:story|stories|floor)',
        r'building[:\s]+(\d+)[\'"\s]*(?:ft|feet)?[\'"\s]*(?:high|tall|height)',
    ]
    
    for pattern in height_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
                # Convert stories to feet
                if "stor" in pattern or "floor" in pattern:
                    if value < 20:
                        value = value * 12 + 2
                # Validate
                if 8 <= value <= 200:
                    dims["height"] = value
                    break
            except (ValueError, IndexError):
                continue
    
    # Default height if not found but have area
    if not dims["height"] and dims.get("area"):
        dims["height"] = 20.0  # Assume single-story
    
    return dims


def parse_cad_fast(pdf_path: Path) -> Dict[str, Any]:
    """
    FAST CAD building plan parser.
    
    Optimized to complete in 1-5 seconds by:
    - Only scanning first 3 pages
    - No OCR or computer vision
    - Text-based regex patterns only
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dictionary with extracted data
    """
    print(f"\n=== FAST CAD Parser: {pdf_path.name} ===")
    print("  Optimized for speed (text extraction only)")
    
    result = {
        "project_name": None,
        "location": None,
        "building_height_ft": None,
        "roof_area_sqft": None,
        "perimeter_ft": None,
        "width_ft": None,
        "length_ft": None,
        "num_corners": 4,
        "pdf_type": "cad_building_plan_fast",
        "extraction_method": "fast_text_only"
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Only scan first 3 pages for speed
            pages_to_scan = min(3, len(pdf.pages))
            all_text = ""
            
            print(f"  Scanning {pages_to_scan} pages...")
            for i in range(pages_to_scan):
                text = pdf.pages[i].extract_text() or ""
                all_text += text + "\n"
            
            # Extract dimensions
            dims = extract_dimensions_fast(all_text)
            
            result["length_ft"] = dims.get("length")
            result["width_ft"] = dims.get("width")
            result["building_height_ft"] = dims.get("height")
            result["roof_area_sqft"] = dims.get("area")
            result["perimeter_ft"] = dims.get("perimeter")
            
            # Extract project name (simple heuristic)
            lines = all_text.split('\n')
            for line in lines[:20]:  # Check first 20 lines
                line = line.strip()
                if 10 < len(line) < 80:
                    project_keywords = ["building", "center", "facility", "complex", "project"]
                    if any(kw in line.lower() for kw in project_keywords):
                        result["project_name"] = line
                        break
            
            if not result["project_name"]:
                result["project_name"] = pdf_path.stem  # Use filename as fallback
            
            print(f"  ✓ Extraction complete")
            if dims.get("length") and dims.get("width"):
                print(f"    Found: {dims['length']}' x {dims['width']}' ({dims['area']} sq ft)")
            else:
                print(f"    WARNING: No dimensions found in first {pages_to_scan} pages")
    
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    return result
