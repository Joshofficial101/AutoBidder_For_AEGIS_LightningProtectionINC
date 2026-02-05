"""
Optimized PDF Parser for CAD Building Plans

This parser is designed for SPEED - targeting 1-2 minute extraction for 16+ page CAD PDFs.

Key optimizations:
1. Uses PyMuPDF (fitz) instead of pdfplumber - 10x faster text extraction
2. Compiled regex patterns for dimension matching
3. Smart page selection - prioritizes title pages and dimension sheets
4. Progress callbacks for UI updates
5. Selective OCR - only when text extraction fails, and only on key pages
6. Early termination when all required data is found

Target metrics:
- 16-page CAD PDF: < 2 minutes (vs 4-12 minutes with previous parsers)
- Text-based PDFs: < 10 seconds
"""

from pathlib import Path
import re
from typing import Dict, Optional, Any, Callable, List, Tuple
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

# Try to import PyMuPDF (faster) first, fall back to pdfplumber
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("Warning: PyMuPDF not installed. Install with: pip install PyMuPDF")

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# OCR support (optional, for CAD drawings with no extractable text)
try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
    
    # Auto-configure Tesseract path
    import os
    tesseract_paths = [
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    ]
    for tess_path in tesseract_paths:
        if Path(tess_path).exists():
            pytesseract.pytesseract.tesseract_cmd = tess_path
            break
except ImportError:
    HAS_OCR = False


@dataclass
class ExtractionResult:
    """Result of PDF extraction with timing info."""
    project_name: Optional[str] = None
    building_height_ft: Optional[float] = None
    roof_area_sqft: Optional[float] = None
    perimeter_ft: Optional[float] = None
    width_ft: Optional[float] = None
    length_ft: Optional[float] = None
    location: Optional[str] = None
    num_corners: int = 4
    extraction_time_seconds: float = 0.0
    pages_processed: int = 0
    extraction_method: str = "optimized"


# Pre-compiled regex patterns for SPEED
# Dimension patterns (various formats)
DIMENSION_PATTERNS = [
    # LxW format: "100' x 200'", "100x200", "100 ft x 200 ft", "100'-0" x 200'-0""
    re.compile(r"(\d+(?:\.\d+)?)['\s\-]*(?:ft|feet|')?[\s\-]*[xX×][\s\-]*(\d+(?:\.\d+)?)['\s\-]*(?:ft|feet|')?", re.IGNORECASE),
    # Building dimensions with label
    re.compile(r"(?:building|structure|footprint|size)[:\s]+(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
]

# Height patterns
HEIGHT_PATTERNS = [
    re.compile(r"(?:building|structure|max(?:imum)?)\s*height[:\s]+(\d+(?:\.\d+)?)['\"\s]*(?:ft|feet)?", re.IGNORECASE),
    re.compile(r"height[:\s]+(\d+(?:\.\d+)?)['\"\s-]*(?:\d+)?['\"\s]*(?:ft|feet)?", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)['\"\s]*(?:ft|feet)\s+(?:high|tall|height)", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:story|stories|storey|storeys|floor|floors)", re.IGNORECASE),
    re.compile(r"(?:ridge|eave|parapet)\s+(?:height|elev)[:\s]+(\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"ht[:\s=]+(\d+(?:\.\d+)?)['\"]?", re.IGNORECASE),
]

# Area patterns
AREA_PATTERNS = [
    re.compile(r"(?:roof|building|total|floor|gross)\s*area[:\s]+(\d+[,\d]*(?:\.\d+)?)\s*(?:sq\.?\s*ft|sf|sqft)", re.IGNORECASE),
    re.compile(r"(\d+[,\d]*(?:\.\d+)?)\s*(?:sq\.?\s*ft|square\s*feet|sf|sqft)", re.IGNORECASE),
    re.compile(r"area[:\s]+(\d+[,\d]*(?:\.\d+)?)", re.IGNORECASE),
]

# Perimeter patterns
PERIMETER_PATTERNS = [
    re.compile(r"perimeter[:\s]+(\d+[,\d]*(?:\.\d+)?)\s*(?:linear\s*)?(?:ft|feet|lf)?", re.IGNORECASE),
    re.compile(r"(\d+[,\d]*(?:\.\d+)?)\s*(?:linear\s*)?(?:ft|lf)\s*perimeter", re.IGNORECASE),
    re.compile(r"roof\s*(?:edge|perimeter)[:\s]+(\d+[,\d]*(?:\.\d+)?)", re.IGNORECASE),
]

# Project name patterns
PROJECT_PATTERNS = [
    re.compile(r"project[:\s]+(.{5,80}?)(?:\n|$)", re.IGNORECASE),
    re.compile(r"(?:for|at)[:\s]+([A-Z][A-Za-z\s]+(?:Center|Plaza|Tower|Complex|Building|Facility|Campus|Park|Place|Warehouse))", re.IGNORECASE),
    re.compile(r"^([A-Z][A-Za-z\s&]+(?:Center|Plaza|Tower|Complex|Building|Facility|Campus|Park|Place|Warehouse))\s*$", re.MULTILINE | re.IGNORECASE),
]


class OptimizedPDFParser:
    """
    High-performance PDF parser optimized for CAD building plans.
    
    Uses PyMuPDF for fast text extraction and compiled regex for pattern matching.
    Supports progress callbacks for UI integration.
    Falls back to selective OCR for CAD drawings with no extractable text.
    """
    
    def __init__(self, progress_callback: Optional[Callable[[int, int, str], None]] = None):
        """
        Initialize the parser.
        
        Args:
            progress_callback: Optional callback function(current_page, total_pages, status_message)
        """
        self.progress_callback = progress_callback
        self._extracted_dimensions: List[Tuple[float, float]] = []
        self._use_ocr = False  # Will be set to True if text extraction yields no dimensions
        
    def _report_progress(self, current: int, total: int, message: str):
        """Report progress to callback if available."""
        if self.progress_callback:
            try:
                self.progress_callback(current, total, message)
            except Exception:
                pass  # Don't let callback errors break parsing
    
    def parse(self, pdf_path: Path) -> ExtractionResult:
        """
        Parse a PDF file and extract building data.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ExtractionResult with extracted data
        """
        start_time = time.time()
        result = ExtractionResult()
        
        if not pdf_path.exists():
            return result
        
        # Choose extraction method based on available libraries
        if HAS_PYMUPDF:
            result = self._parse_with_pymupdf(pdf_path)
        elif HAS_PDFPLUMBER:
            result = self._parse_with_pdfplumber(pdf_path)
        else:
            print("ERROR: No PDF library available. Install PyMuPDF or pdfplumber.")
            return result
        
        result.extraction_time_seconds = time.time() - start_time
        
        # Log performance
        print(f"  Extraction completed in {result.extraction_time_seconds:.2f} seconds")
        
        return result
    
    def _perform_selective_ocr(self, pdf_path: Path, pages_to_ocr: List[int]) -> str:
        """
        Perform OCR on selected pages of a PDF.
        
        Uses PyMuPDF to render cropped page regions to images, then Tesseract for OCR.
        Optimized for speed with lower DPI, limited page selection, and targeted crops.
        
        Args:
            pdf_path: Path to the PDF
            pages_to_ocr: List of page indices to OCR (0-based)
        
        Returns:
            Combined OCR text from all processed pages
        """
        if not HAS_OCR or not HAS_PYMUPDF:
            return ""
        
        ocr_text = ""
        
        try:
            doc = fitz.open(str(pdf_path))
            
            for i, page_num in enumerate(pages_to_ocr):
                if page_num >= len(doc):
                    continue
                    
                self._report_progress(
                    50 + int((i / len(pages_to_ocr)) * 30), 
                    100, 
                    f"OCR page {page_num + 1}..."
                )
                
                page = doc[page_num]
                ocr_text += self._ocr_page_regions(page)
            
            doc.close()
            
        except Exception as e:
            print(f"  OCR error: {e}")
        
        return ocr_text

    def _ocr_page_regions(self, page) -> str:
        """OCR targeted regions of a page to capture dimension callouts quickly."""
        if not HAS_OCR:
            return ""

        # Render crops at moderate DPI for better dimension capture
        mat = fitz.Matrix(200/72, 200/72)
        rect = page.rect
        w = rect.width
        h = rect.height

        # Define relative crop regions (x0, y0, x1, y1)
        regions = [
            (0.15, 0.15, 0.85, 0.85),  # central drawing area
            (0.80, 0.10, 1.00, 0.90),  # right margin annotations
            (0.60, 0.75, 1.00, 1.00),  # bottom-right (title block / notes)
            (0.00, 0.00, 1.00, 0.15),  # top band (sheet title/notes)
            (0.00, 0.10, 0.20, 0.90),  # left margin
        ]

        # Add 2x2 tiles of the central drawing area for better coverage
        tiles = [
            (0.15, 0.15, 0.50, 0.50),
            (0.50, 0.15, 0.85, 0.50),
            (0.15, 0.50, 0.50, 0.85),
            (0.50, 0.50, 0.85, 0.85),
        ]
        regions.extend(tiles)

        text_parts = []
        for (x0, y0, x1, y1) in regions:
            clip = fitz.Rect(rect.x0 + x0 * w, rect.y0 + y0 * h, rect.x0 + x1 * w, rect.y0 + y1 * h)
            pix = page.get_pixmap(matrix=mat, clip=clip)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Light preprocessing to help with dimension callouts
            gray = img.convert("L")
            bw = gray.point(lambda x: 0 if x < 170 else 255, "1")

            # PSM 11: sparse text; good for drawings with scattered labels
            text = pytesseract.image_to_string(bw, config='--psm 11 --oem 3')
            if text.strip():
                text_parts.append(text)

        return "\n\n".join(text_parts)

    def _should_run_ocr(self, result: ExtractionResult, all_text: str) -> bool:
        """Decide if OCR should run based on text sparsity and missing data."""
        has_any = any([
            result.roof_area_sqft,
            result.length_ft,
            result.perimeter_ft,
            result.building_height_ft,
        ])

        # If nothing found and text is sparse, OCR is likely needed
        if not has_any and len(all_text.strip()) < 5000:
            return True

        # If height is missing and text is sparse, OCR may still help
        if result.building_height_ft is None and len(all_text.strip()) < 8000:
            return True

        return False

    def _has_enough_dimensions(self, result: ExtractionResult) -> bool:
        """Return True if we have enough dimensions to stop OCR."""
        if result.building_height_ft is None:
            return False
        if result.perimeter_ft is not None:
            return True
        if result.roof_area_sqft is not None:
            return True
        if result.length_ft is not None and result.width_ft is not None:
            return True
        return False

    def _rank_pages_for_ocr(self, doc, pages_with_text: List[Tuple[int, str]]) -> List[int]:
        """Rank pages likely to contain drawing dimensions."""
        scores = []
        text_map = {p: t for p, t in pages_with_text}

        for page_num in range(len(doc)):
            page = doc[page_num]
            rect = page.rect
            width_in = rect.width / 72.0
            height_in = rect.height / 72.0
            area_in = max(width_in * height_in, 1.0)

            text = text_map.get(page_num, "")
            text_len = len(text)
            text_density = text_len / area_in  # chars per sq inch

            # Larger sheets (A1/A0) tend to be drawings
            size_score = min(2.0, area_in / (11 * 17))

            # Lower text density -> more likely drawing
            density_score = 2.0 if text_density < 10 else 1.0 if text_density < 25 else 0.0

            # Keyword bonus
            keyword_bonus = 0.0
            if re.search(r"\b(plan|elevation|section|site|roof|details?)\b", text, re.IGNORECASE):
                keyword_bonus = 1.5

            # Vector density bonus (drawings often have many vector objects)
            try:
                drawings = page.get_drawings()
                vector_bonus = 1.5 if drawings and len(drawings) > 50 else 0.5 if drawings and len(drawings) > 10 else 0.0
            except Exception:
                vector_bonus = 0.0

            score = size_score + density_score + keyword_bonus + vector_bonus
            scores.append((score, page_num))

        scores.sort(reverse=True)
        return [p for _, p in scores]
    
    def _parse_with_pymupdf(self, pdf_path: Path) -> ExtractionResult:
        """Parse PDF using PyMuPDF (fastest method)."""
        result = ExtractionResult(extraction_method="pymupdf_optimized")
        
        self._report_progress(0, 100, "Opening PDF...")
        
        try:
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            result.pages_processed = total_pages
            
            print(f"\n{'='*60}")
            print(f"OPTIMIZED PDF PARSER: {pdf_path.name}")
            print(f"Pages: {total_pages} | Using PyMuPDF (fast)")
            print(f"{'='*60}")
            
            all_text = ""
            pages_with_text = []
            
            # Phase 1: Extract text from all pages (fast with PyMuPDF)
            self._report_progress(5, 100, "Extracting text from pages...")
            
            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text("text")
                
                if text.strip():
                    pages_with_text.append((page_num, text))
                    all_text += text + "\n\n"
                
                # Report progress (text extraction phase: 5-40%)
                progress = 5 + int((page_num / total_pages) * 35)
                self._report_progress(progress, 100, f"Reading page {page_num + 1}/{total_pages}")
            
            print(f"  [1/4] Text extraction: {len(pages_with_text)}/{total_pages} pages have text")
            
            # Phase 2: Extract dimensions (40-50%)
            self._report_progress(45, 100, "Analyzing dimensions...")
            self._extract_dimensions_from_text(all_text, result, source="text")
            
            # Check if we found dimensions - if not and OCR is available, use it
            needs_ocr = HAS_OCR and self._should_run_ocr(result, all_text)
            
            if needs_ocr:
                print(f"  [2/4] No dimensions in text - running deeper OCR on all pages...")
                self._report_progress(50, 100, "No dimensions found - running OCR...")

                ocr_start = time.time()
                max_ocr_seconds = 140
                combined_ocr_text = ""

                # OCR every page (no page cutting), but stop early once we have enough data
                for page_num in range(total_pages):
                    if time.time() - ocr_start > max_ocr_seconds:
                        print("  OCR time cap reached; returning best-effort results")
                        break

                    page = doc[page_num]
                    self._report_progress(
                        50 + int((page_num / max(total_pages, 1)) * 30),
                        100,
                        f"OCR page {page_num + 1}/{total_pages}..."
                    )

                    page_text = self._ocr_page_regions(page)
                    if page_text:
                        combined_ocr_text += page_text + "\n\n"
                        self._extract_dimensions_from_text(page_text, result, source="ocr")

                    if self._has_enough_dimensions(result):
                        break

                if combined_ocr_text:
                    all_text += "\n\n=== OCR TEXT ===\n" + combined_ocr_text
                    result.extraction_method = "pymupdf_with_ocr"
                    print(f"       OCR extracted {len(combined_ocr_text)} chars of text")
            
            print(f"  [2/4] Dimension extraction complete")
            
            # Phase 3: Extract project info (60-80%)
            self._report_progress(75, 100, "Extracting project information...")
            self._extract_project_info(all_text, result, pdf_path)
            print(f"  [3/4] Project info extraction complete")
            
            # Phase 4: Calculate derived values (80-100%)
            self._report_progress(90, 100, "Calculating derived values...")
            self._calculate_derived_values(result)
            print(f"  [4/4] Calculations complete")
            
            self._report_progress(100, 100, "Extraction complete!")
            
            # Summary
            print(f"\n  Results:")
            print(f"    Project: {result.project_name or '(not found)'}")
            print(f"    Height:  {result.building_height_ft or '(not found)'} ft")
            print(f"    Area:    {result.roof_area_sqft or '(not found)'} sqft")
            print(f"    Perimeter: {result.perimeter_ft or '(not found)'} ft")
            if result.length_ft and result.width_ft:
                print(f"    Dimensions: {result.length_ft} x {result.width_ft} ft")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"  ERROR in PyMuPDF parsing: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                if "doc" in locals() and doc:
                    doc.close()
            except Exception:
                pass
        
        return result
    
    def _parse_with_pdfplumber(self, pdf_path: Path) -> ExtractionResult:
        """Fallback parser using pdfplumber (slower but more compatible)."""
        result = ExtractionResult(extraction_method="pdfplumber_fallback")
        
        self._report_progress(0, 100, "Opening PDF with pdfplumber...")
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                result.pages_processed = total_pages
                
                print(f"\n{'='*60}")
                print(f"OPTIMIZED PDF PARSER (pdfplumber fallback): {pdf_path.name}")
                print(f"Pages: {total_pages}")
                print(f"{'='*60}")
                
                all_text = ""
                
                # Only process first 5 pages for speed (most info is there)
                pages_to_scan = min(5, total_pages)
                
                for i in range(pages_to_scan):
                    page = pdf.pages[i]
                    text = page.extract_text() or ""
                    all_text += text + "\n\n"
                    
                    progress = int((i / pages_to_scan) * 60)
                    self._report_progress(progress, 100, f"Reading page {i + 1}/{pages_to_scan}")
                
                # Extract data
                self._report_progress(65, 100, "Analyzing dimensions...")
                self._extract_dimensions_from_text(all_text, result, source="text")
                
                self._report_progress(80, 100, "Extracting project info...")
                self._extract_project_info(all_text, result, pdf_path)
                
                self._report_progress(90, 100, "Calculating derived values...")
                self._calculate_derived_values(result)
                
                self._report_progress(100, 100, "Complete!")
                
        except Exception as e:
            print(f"  ERROR in pdfplumber parsing: {e}")
        
        return result
    
    def _extract_dimensions_from_text(self, text: str, result: ExtractionResult, source: str = "text"):
        """Extract all dimension data from text using compiled patterns."""
        
        # Extract LxW dimensions
        for pattern in DIMENSION_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                try:
                    val1, val2 = float(match[0]), float(match[1])
                    # Filter: Reasonable building dimensions (10-1000 ft)
                    if 10 <= val1 <= 1000 and 10 <= val2 <= 1000:
                        self._extracted_dimensions.append((val1, val2))
                except (ValueError, IndexError):
                    continue
        
        # Find the most likely building dimensions (largest reasonable pair)
        if self._extracted_dimensions:
            # Sort by area (likely the building footprint is larger than rooms)
            sorted_dims = sorted(self._extracted_dimensions, key=lambda x: x[0] * x[1], reverse=True)
            best = sorted_dims[0]
            result.length_ft = max(best[0], best[1])
            result.width_ft = min(best[0], best[1])
        
        # Extract height (score candidates, prefer labeled "height" over generic)
        height_candidates: List[Tuple[float, float]] = []
        for pattern in HEIGHT_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    value = float(match.group(1))
                    pattern_text = pattern.pattern.lower()
                    score = 1.0
                    if "height" in pattern_text or "building" in pattern_text:
                        score += 1.5
                    if "stor" in pattern_text or "floor" in pattern_text:
                        score -= 0.25
                        if value < 20:  # Likely number of stories
                            value = value * 12 + 2  # 12 ft per story + 2 ft

                    # Validate: Reasonable building height (8-500 ft)
                    if 8 <= value <= 500:
                        height_candidates.append((score, value))
                except (ValueError, IndexError):
                    continue

        if height_candidates:
            # Prefer higher score; if tie, prefer larger height
            height_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            result.building_height_ft = height_candidates[0][1]
        
        # Extract area (score candidates; in OCR, prefer labeled area)
        area_candidates: List[Tuple[float, float]] = []
        for pattern in AREA_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    area_str = match.group(1).replace(",", "")
                    area = float(area_str)
                    pattern_text = pattern.pattern.lower()
                    score = 1.0
                    if "roof" in pattern_text or "building" in pattern_text or "floor" in pattern_text or "gross" in pattern_text or "total" in pattern_text:
                        score += 1.5

                    # In OCR, be stricter: down-rank generic area with no label
                    if source == "ocr" and score <= 1.0:
                        score -= 0.5

                    # Validate: Reasonable building area (100 - 10,000,000 sqft)
                    if 100 <= area <= 10000000:
                        area_candidates.append((score, area))
                except (ValueError, IndexError):
                    continue

        if area_candidates:
            area_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            result.roof_area_sqft = area_candidates[0][1]
        
        # Extract perimeter (score candidates)
        perimeter_candidates: List[Tuple[float, float]] = []
        for pattern in PERIMETER_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    perim_str = match.group(1).replace(",", "")
                    perim = float(perim_str)
                    pattern_text = pattern.pattern.lower()
                    score = 1.0
                    if "perimeter" in pattern_text or "roof" in pattern_text:
                        score += 1.0

                    # Validate: Reasonable perimeter (40 - 50,000 ft)
                    if 40 <= perim <= 50000:
                        perimeter_candidates.append((score, perim))
                except (ValueError, IndexError):
                    continue

        if perimeter_candidates:
            perimeter_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            result.perimeter_ft = perimeter_candidates[0][1]
    
    def _extract_project_info(self, text: str, result: ExtractionResult, pdf_path: Path):
        """Extract project name and location from text."""
        
        # Try explicit project patterns first
        for pattern in PROJECT_PATTERNS:
            match = pattern.search(text)
            if match:
                name = match.group(1).strip()
                # Clean up the name
                name = re.sub(r'\s+', ' ', name)  # Normalize whitespace
                name = name.strip('.:- ')
                if 5 < len(name) < 100:
                    result.project_name = name
                    break
        
        # Fallback: Look for facility/building name in first 30 lines
        if not result.project_name:
            lines = text.split('\n')[:30]
            facility_keywords = [
                "center", "plaza", "tower", "complex", "building", "facility",
                "campus", "park", "place", "warehouse", "school", "hospital",
                "church", "office", "industrial", "commercial", "retail"
            ]
            
            for line in lines:
                line = line.strip()
                if 10 < len(line) < 80:
                    line_lower = line.lower()
                    if any(kw in line_lower for kw in facility_keywords):
                        # Clean and use this as project name
                        result.project_name = line
                        break
        
        # Final fallback: use filename
        if not result.project_name:
            result.project_name = pdf_path.stem.replace("_", " ").replace("-", " ")
        
        # Extract location/address
        location_patterns = [
            re.compile(r"(?:location|address|site)[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
            re.compile(r"(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct))", re.IGNORECASE),
        ]
        
        for pattern in location_patterns:
            match = pattern.search(text)
            if match:
                location = match.group(1).strip()
                if 5 < len(location) < 150:
                    result.location = location
                    break
    
    def _calculate_derived_values(self, result: ExtractionResult):
        """Calculate missing values from available data."""
        
        # Calculate area from length x width
        if result.roof_area_sqft is None and result.length_ft and result.width_ft:
            result.roof_area_sqft = result.length_ft * result.width_ft
        
        # Calculate perimeter from length x width
        if result.perimeter_ft is None and result.length_ft and result.width_ft:
            result.perimeter_ft = 2 * (result.length_ft + result.width_ft)
        
        # Estimate length/width from area (assume square-ish if not found)
        if result.roof_area_sqft and not result.length_ft and not result.width_ft:
            import math
            side = math.sqrt(result.roof_area_sqft)
            result.length_ft = side
            result.width_ft = side
            if result.perimeter_ft is None:
                result.perimeter_ft = 4 * side
        
        # Default height if not found
        if result.building_height_ft is None and result.roof_area_sqft:
            # Estimate: 20 ft for small buildings, 24 ft for larger ones
            if result.roof_area_sqft < 50000:
                result.building_height_ft = 20.0
            else:
                result.building_height_ft = 24.0
            print(f"    Note: Height not found, using estimate: {result.building_height_ft} ft")
    
    def get_formatted_output(self, result: ExtractionResult) -> Dict[str, Any]:
        """Convert ExtractionResult to dictionary format expected by the bidding system."""
        return {
            "project_name": result.project_name,
            "location": result.location,
            "building_height_ft": result.building_height_ft,
            "roof_area_sqft": result.roof_area_sqft,
            "perimeter_ft": result.perimeter_ft,
            "width_ft": result.width_ft,
            "length_ft": result.length_ft,
            "num_corners": result.num_corners,
            "pdf_type": "cad_building_plan",
            "extraction_method": result.extraction_method,
            "extraction_metadata": {
                "pages_processed": result.pages_processed,
                "extraction_time_seconds": result.extraction_time_seconds,
                "has_pymupdf": HAS_PYMUPDF,
            }
        }


def parse_pdf_optimized(
    pdf_path: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    Main entry point for optimized PDF parsing.
    
    Args:
        pdf_path: Path to the PDF file
        progress_callback: Optional callback for progress updates
            Function signature: callback(current_step, total_steps, message)
    
    Returns:
        Dictionary with extracted building data
    """
    parser = OptimizedPDFParser(progress_callback=progress_callback)
    result = parser.parse(pdf_path)
    return parser.get_formatted_output(result)


# For testing from command line
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_path = Path(sys.argv[1])
    else:
        # Default test file
        test_path = Path(__file__).parent.parent.parent / "data" / "inputs" / "BC23-001053 Electrical Building Plans (General Building) - APPROVED.pdf"
    
    if test_path.exists():
        print(f"\nTesting optimized parser on: {test_path.name}")
        print("-" * 60)
        
        # Define a simple progress callback
        def progress_callback(current, total, message):
            bar_width = 30
            filled = int(bar_width * current / total)
            bar = "█" * filled + "░" * (bar_width - filled)
            print(f"\r  [{bar}] {current}% - {message}", end="", flush=True)
            if current >= 100:
                print()  # Newline when complete
        
        result = parse_pdf_optimized(test_path, progress_callback=progress_callback)
        
        print("\nExtracted Data:")
        for key, value in result.items():
            if key != "extraction_metadata":
                print(f"  {key}: {value}")
    else:
        print(f"File not found: {test_path}")
