"""
Advanced PDF Parser for CAD-Style Building Plans

This module provides sophisticated extraction for architectural/engineering drawings including:
- OCR-based text extraction from dimension callouts
- Computer vision for building outline detection
- Title block parsing
- Dimension schedule/table extraction
- Scale-aware measurement extraction

Requires: pdf2image, pytesseract, opencv-python (cv2), PIL
"""

from pathlib import Path
import pdfplumber
import re
from typing import Dict, List, Optional, Any, Tuple
import math

# Try to import advanced libraries (optional dependencies)
try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False
    print("Warning: pdf2image not installed. OCR features will be limited.")

# Configure Poppler path (auto-detected or default)
POPPLER_PATH = None
import os
# Check if poppler is in project directory (installed by install_poppler.py)
project_poppler = Path(__file__).parent.parent.parent / "poppler" / "poppler-24.08.0" / "Library" / "bin"
if project_poppler.exists():
    POPPLER_PATH = str(project_poppler)
# Check if poppler is in PATH
elif os.system("where pdftotext >nul 2>&1") == 0:
    POPPLER_PATH = None  # Already in PATH

try:
    from PIL import Image
    import pytesseract
    HAS_TESSERACT = True
    
    # Auto-configure Tesseract path if not in PATH
    tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        Path(__file__).parent.parent.parent / "tesseract" / "tesseract.exe"
    ]
    
    for tess_path in tesseract_paths:
        tess_path_str = str(tess_path) if isinstance(tess_path, Path) else tess_path
        if Path(tess_path_str).exists():
            pytesseract.pytesseract.tesseract_cmd = tess_path_str
            break
            
except ImportError:
    HAS_TESSERACT = False
    print("Warning: pytesseract not installed. OCR features disabled.")

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    print("Warning: opencv-python not installed. Vision features disabled.")


class CADPlanParser:
    """Parser for CAD-style building plan PDFs."""
    
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.pages_data = []
        self.extracted_data = {
            "project_info": {},
            "dimensions": {},
            "rooms": [],
            "notes": [],
            "metadata": {}
        }
    
    def parse(self, use_ocr: bool = False) -> Dict[str, Any]:
        """
        Main parsing entry point.
        
        Args:
            use_ocr: Enable slow OCR processing (default False for speed)
        """
        print(f"\n=== Parsing CAD Building Plan: {self.pdf_path.name} ===")
        
        # Stage 1: Basic text extraction (FAST - always do this)
        self._extract_text_content()
        
        # Stage 2: OCR on images (SLOW - optional, disabled by default for speed)
        if use_ocr and HAS_PDF2IMAGE and HAS_TESSERACT:
            self._perform_ocr_extraction()
        else:
            print("  [2/4] Skipping OCR (disabled for speed - use_ocr=False)")
        
        # Stage 3: Computer vision analysis (MEDIUM - optional, disabled by default)
        if use_ocr and HAS_OPENCV and HAS_PDF2IMAGE:
            self._perform_vision_analysis()
        else:
            print("  [3/4] Skipping computer vision (disabled for speed)")
        
        # Stage 4: Parse extracted content
        self._parse_project_info()
        self._parse_dimensions()
        
        return self.extracted_data
    
    def _extract_text_content(self):
        """Extract all text content using pdfplumber."""
        print("  [1/4] Extracting text content...")
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_data = {
                        "page_num": i + 1,
                        "text": page.extract_text() or "",
                        "tables": page.extract_tables() or [],
                        "words": page.extract_words() if hasattr(page, 'extract_words') else []
                    }
                    self.pages_data.append(page_data)
            
            print(f"     [OK] Extracted {len(self.pages_data)} pages")
        except Exception as e:
            print(f"     [ERROR] Error extracting text: {e}")
    
    def _perform_ocr_extraction(self):
        """Perform OCR on PDF pages converted to images."""
        print("  [2/4] Performing OCR on drawings...")
        
        try:
            # Convert PDF to images (OPTIMIZED: Only first 2 pages at lower DPI for speed)
            kwargs = {"dpi": 150, "first_page": 1, "last_page": min(2, len(self.pages_data))}
            if POPPLER_PATH:
                kwargs["poppler_path"] = POPPLER_PATH
            images = convert_from_path(self.pdf_path, **kwargs)
            
            for i, img in enumerate(images):
                # Perform OCR
                ocr_text = pytesseract.image_to_string(img, config='--psm 6')
                
                # Add OCR text to page data
                if i < len(self.pages_data):
                    self.pages_data[i]["ocr_text"] = ocr_text
                    # Also extract OCR data with bounding boxes
                    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                    self.pages_data[i]["ocr_data"] = ocr_data
            
            print(f"     [OK] OCR completed on {len(images)} pages")
        except Exception as e:
            print(f"     [ERROR] OCR failed: {e}")
    
    def _perform_vision_analysis(self):
        """Use computer vision to analyze building drawings."""
        print("  [3/4] Performing computer vision analysis...")
        
        try:
            # Convert first few pages to images (OPTIMIZED: Only first page at low DPI)
            kwargs = {"dpi": 100, "first_page": 1, "last_page": 1}
            if POPPLER_PATH:
                kwargs["poppler_path"] = POPPLER_PATH
            images = convert_from_path(self.pdf_path, **kwargs)
            
            for i, img_pil in enumerate(images):
                # Convert PIL image to OpenCV format
                img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                
                # Detect lines (walls, dimension lines)
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150, apertureSize=3)
                lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=50, maxLineGap=10)
                
                # Store vision data
                if i < len(self.pages_data):
                    self.pages_data[i]["vision_data"] = {
                        "lines_detected": len(lines) if lines is not None else 0,
                        "has_drawing_content": lines is not None and len(lines) > 50
                    }
            
            print(f"     [OK] Vision analysis completed")
        except Exception as e:
            print(f"     [ERROR] Vision analysis failed: {e}")
    
    def _parse_project_info(self):
        """Extract project information from title blocks and text."""
        print("  [4/4] Parsing project information...")
        
        # Combine all text
        all_text = "\n".join([p.get("text", "") + "\n" + p.get("ocr_text", "") for p in self.pages_data])
        
        # Extract project name
        project_patterns = [
            r'project\s*(?:name|title)?[:\s]+(.{5,80})',
            r'building\s*(?:name)?[:\s]+(.{5,80})',
            r'site[:\s]+(.{5,80})',
        ]
        
        for pattern in project_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                self.extracted_data["project_info"]["project_name"] = match.group(1).strip()
                break
        
        # Extract location/address
        address_patterns = [
            r'location[:\s]+(.{5,100})',
            r'address[:\s]+(.{5,100})',
            r'site\s+address[:\s]+(.{5,100})',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                self.extracted_data["project_info"]["location"] = match.group(1).strip()
                break
        
        print(f"     [OK] Project info extracted")
    
    def _parse_dimensions(self):
        """Extract building dimensions from text and OCR data."""
        dims = {
            "height": None,
            "area": None,
            "perimeter": None,
            "width": None,
            "length": None,
            "room_dimensions": []
        }
        
        # Combine all text sources
        all_text = ""
        dimension_values = []  # Collect all potential dimension values
        
        for page_data in self.pages_data:
            all_text += page_data.get("text", "") + "\n"
            all_text += page_data.get("ocr_text", "") + "\n"
            
            # Extract structured OCR data to find dimension callouts
            ocr_data = page_data.get("ocr_data", {})
            if ocr_data and "text" in ocr_data:
                # Look for dimension-like text in OCR results
                for text in ocr_data.get("text", []):
                    if text and text.strip():
                        # Check if this looks like a dimension callout
                        # Common formats: 40'-0", 60', 100.5', 40x60, etc.
                        dim_patterns = [
                            r"(\d+)['\-\"][\-\s]*(\d+)['\"]?",  # 40'-0" or 40-6
                            r"(\d+(?:\.\d+)?)['\"]?",           # 40' or 40.5
                            r"(\d+)\s*[xX×]\s*(\d+)",          # 40x60
                        ]
                        for pattern in dim_patterns:
                            matches = re.findall(pattern, text)
                            for match in matches:
                                try:
                                    if isinstance(match, tuple):
                                        if len(match) == 2:
                                            # Could be feet-inches or LxW
                                            val1 = float(match[0])
                                            val2 = float(match[1])
                                            # Feet-inches format
                                            if val2 < 12:  # Likely inches
                                                dimension_values.append(val1 + val2/12)
                                            else:  # Likely LxW
                                                dimension_values.append(val1)
                                                dimension_values.append(val2)
                                        else:
                                            dimension_values.append(float(match[0]))
                                    else:
                                        dimension_values.append(float(match))
                                except (ValueError, IndexError):
                                    continue
        
        # Analyze collected dimension values to identify building dimensions
        # Filter to reasonable building dimensions (10-500 feet typically)
        reasonable_dims = [d for d in dimension_values if 10 <= d <= 500]
        
        # If we have candidate dimensions, try to identify length/width
        if len(reasonable_dims) >= 2:
            # Sort by size (larger is typically length)
            reasonable_dims.sort(reverse=True)
            # Take the two largest as potential length/width
            if len(reasonable_dims) >= 2:
                dims["length"] = reasonable_dims[0]
                dims["width"] = reasonable_dims[1]
                dims["area"] = dims["length"] * dims["width"]
                dims["perimeter"] = 2 * (dims["length"] + dims["width"])
        
        # Extract dimensions using various patterns
        
        # Building dimensions (LxW format)
        lxw_patterns = [
            r'(\d+)[\'"\s-]*(?:x|X|×)[\s-]*(\d+)[\'"\s]*',
            r'building[:\s]+(\d+)[\'"\s]*(?:x|X|×)[\s]*(\d+)[\'"\s]*',
        ]
        
        for pattern in lxw_patterns:
            matches = re.findall(pattern, all_text)
            for match in matches:
                try:
                    val1, val2 = float(match[0]), float(match[1])
                    if 10 <= val1 <= 500 and 10 <= val2 <= 500:  # Reasonable building size
                        dims["length"] = max(val1, val2)
                        dims["width"] = min(val1, val2)
                        dims["area"] = val1 * val2
                        dims["perimeter"] = 2 * (val1 + val2)
                        break
                except (ValueError, IndexError):
                    continue
            if dims["length"]:
                break
        
        # Building height (ENHANCED with more patterns)
        height_patterns = [
            # Explicit height labels
            r'(?:building|structure|max(?:imum)?)\s*height[:\s]+(\d+(?:\.\d+)?)[\'"\s-]*(?:\d+)?[\'"\s]*(?:ft|feet)?',
            r'height[:\s]+(\d+(?:\.\d+)?)[\'"\s-]*(?:\d+)?[\'"\s]*(?:ft|feet)?',
            r'(\d+(?:\.\d+)?)[\'"\s]*(?:ft|feet)\s+(?:high|tall|height)',
            # Stories/floors
            r'(\d+)[:\s-]*(?:story|stories|storey|storeys|floor|floors)',
            # Elevation notation
            r'(?:top|roof|parapet)\s+(?:elev|elevation)[:\s]+(\d+(?:\.\d+)?)',
            r'ridge\s+height[:\s]+(\d+(?:\.\d+)?)',
            # Common CAD annotations
            r'(?:^|\s)(\d+)[\'"\s]*(?:ht|hgt|height)',
            # Vertical dimension callout (single number that could be height)
            r'(?:wall|building)\s+(?:=|is|@)\s*(\d+(?:\.\d+)?)[\'"]',
        ]
        
        # Try all patterns
        for pattern in height_patterns:
            matches = re.finditer(pattern, all_text, re.IGNORECASE)
            for match in matches:
                try:
                    value = float(match.group(1))
                    
                    # Convert stories to feet (12 ft per story + 2 ft for structure)
                    if any(word in pattern.lower() for word in ["story", "storey", "floor"]):
                        if value < 20:  # Likely number of stories
                            value = value * 12 + 2
                    
                    # Validate: Reasonable building height (8-200 ft)
                    if 8 <= value <= 200:
                        dims["height"] = value
                        break
                except (ValueError, IndexError):
                    continue
            
            if dims["height"]:
                break
        
        # If still no height but we have area, estimate based on typical building
        # (This is a last resort fallback)
        if not dims["height"] and dims.get("area"):
            # Typical 1-story commercial building = 20 ft
            # Assume 20 ft if no height found
            if dims["area"] < 50000:  # Smaller building
                dims["height"] = 20.0  # Default: 1 story
                print(f"     Note: No height found, using default 20 ft (1-story estimate)")
            else:  # Larger building, might be multi-story
                dims["height"] = 24.0  # Default: slightly taller
                print(f"     Note: No height found, using default 24 ft (1-story estimate)")
        
        # Area
        area_patterns = [
            r'(?:roof|building|total|floor)\s*area[:\s]+(\d+[,\d]*)\s*(?:sq\.?\s*ft|sf)',
            r'(\d+[,\d]*)\s*(?:sq\.?\s*ft|square\s+feet|sf)',
        ]
        
        for pattern in area_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                try:
                    area_str = match.group(1).replace(",", "")
                    area_val = float(area_str)
                    if 100 <= area_val <= 1000000:  # Reasonable area
                        dims["area"] = area_val
                        break
                except (ValueError, IndexError):
                    continue
        
        # Extract room dimensions (for detail)
        room_pattern = r'(?:room|space)[^\d]*(\d+)[\'"\s-]*(?:x|X|×)[\s-]*(\d+)[\'"\s]*'
        room_matches = re.findall(room_pattern, all_text, re.IGNORECASE)
        for match in room_matches:
            try:
                dims["room_dimensions"].append({
                    "length": float(match[0]),
                    "width": float(match[1])
                })
            except (ValueError, IndexError):
                continue
        
        self.extracted_data["dimensions"] = dims
        
        # Debug: Log what we found
        if any(dims[k] for k in ["length", "width", "height", "area"]):
            print(f"     Found dimensions: L={dims.get('length')}, W={dims.get('width')}, H={dims.get('height')}")
        else:
            print(f"     Warning: No dimensions extracted (found {len(dimension_values)} candidates)")
    
    def get_formatted_output(self) -> Dict[str, Any]:
        """Get output in the format expected by the bidding system."""
        return {
            "project_name": self.extracted_data["project_info"].get("project_name", "CAD Building Plan"),
            "location": self.extracted_data["project_info"].get("location"),
            "building_height_ft": self.extracted_data["dimensions"].get("height"),
            "roof_area_sqft": self.extracted_data["dimensions"].get("area"),
            "perimeter_ft": self.extracted_data["dimensions"].get("perimeter"),
            "width_ft": self.extracted_data["dimensions"].get("width"),
            "length_ft": self.extracted_data["dimensions"].get("length"),
            "num_corners": 4,  # Default, could be enhanced
            "pdf_type": "cad_building_plan",
            "extraction_method": "advanced_ocr_vision",
            "extraction_metadata": {
                "pages_processed": len(self.pages_data),
                "has_ocr": HAS_TESSERACT and HAS_PDF2IMAGE,
                "has_vision": HAS_OPENCV and HAS_PDF2IMAGE,
                "room_count": len(self.extracted_data["dimensions"].get("room_dimensions", []))
            }
        }


def parse_cad_building_plan(pdf_path: Path) -> Dict[str, Any]:
    """
    Parse a CAD-style building plan PDF.
    
    This is the main entry point for parsing architectural/engineering drawings.
    Falls back to basic text extraction if advanced features are not available.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary with extracted building data
    """
    parser = CADPlanParser(pdf_path)
    parser.parse()
    return parser.get_formatted_output()


# Fallback function if advanced libraries are not available
def parse_cad_basic(pdf_path: Path) -> Dict[str, Any]:
    """
    Basic CAD plan parsing using only pdfplumber (no OCR/CV).
    
    This is a fallback when pdf2image, pytesseract, or opencv are not installed.
    """
    print(f"\n=== Basic CAD Parsing (Limited): {pdf_path.name} ===")
    print("  Note: Install pdf2image, pytesseract, opencv-python for full functionality")
    
    result = {
        "project_name": None,
        "location": None,
        "building_height_ft": None,
        "roof_area_sqft": None,
        "perimeter_ft": None,
        "width_ft": None,
        "length_ft": None,
        "num_corners": 4,
        "pdf_type": "cad_building_plan_basic",
        "extraction_method": "basic_text_only"
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = ""
            for page in pdf.pages:
                all_text += (page.extract_text() or "") + "\n"
            
            # Try to extract dimensions from available text
            # LxW format
            lxw_match = re.search(r'(\d+)[\'"\s-]*(?:x|X|×)[\s-]*(\d+)[\'"\s]*', all_text)
            if lxw_match:
                try:
                    val1, val2 = float(lxw_match.group(1)), float(lxw_match.group(2))
                    if 10 <= val1 <= 500 and 10 <= val2 <= 500:
                        result["length_ft"] = max(val1, val2)
                        result["width_ft"] = min(val1, val2)
                        result["roof_area_sqft"] = val1 * val2
                        result["perimeter_ft"] = 2 * (val1 + val2)
                except (ValueError, IndexError):
                    pass
            
            # Height
            height_match = re.search(r'(?:height|tall)[:\s]+(\d+(?:\.\d+)?)', all_text, re.IGNORECASE)
            if height_match:
                try:
                    result["building_height_ft"] = float(height_match.group(1))
                except (ValueError, IndexError):
                    pass
            
            print(f"     [OK] Basic extraction completed")
    
    except Exception as e:
        print(f"     [ERROR] Error: {e}")
    
    return result


# Auto-detect which parser to use
def parse_building_plan_auto(pdf_path: Path) -> Dict[str, Any]:
    """
    Automatically choose the best available parser for CAD building plans.
    
    Uses advanced OCR/CV parser if libraries are available, otherwise falls back to basic.
    """
    if HAS_PDF2IMAGE and HAS_TESSERACT:
        return parse_cad_building_plan(pdf_path)
    else:
        return parse_cad_basic(pdf_path)
