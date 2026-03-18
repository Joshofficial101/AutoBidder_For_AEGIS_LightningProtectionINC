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
from dataclasses import dataclass, field

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
    metric_candidates: List["MetricCandidate"] = field(default_factory=list)
    field_provenance: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    page_profiles: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MetricCandidate:
    """Traceable candidate extracted for a building metric."""
    field_name: str
    normalized_value: float
    confidence: float
    source: str
    page_number: Optional[int] = None
    raw_value: Optional[float] = None
    unit: Optional[str] = None
    original_text: Optional[str] = None
    context: Optional[str] = None
    derived: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "source": self.source,
            "page_number": self.page_number,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "original_text": self.original_text,
            "context": self.context,
            "derived": self.derived,
        }


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
        self._use_ocr = False  # Will be set to True if text extraction yields no dimensions
        self._best_dimension_score = float("-inf")
        self._best_height_score = float("-inf")
        self._best_area_score = float("-inf")
        self._best_perimeter_score = float("-inf")
        
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
        # Reset per-document state so reused parser instances do not leak scores.
        self._use_ocr = False
        self._best_dimension_score = float("-inf")
        self._best_height_score = float("-inf")
        self._best_area_score = float("-inf")
        self._best_perimeter_score = float("-inf")
        
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

    def _store_candidate(
        self,
        result: ExtractionResult,
        field_name: str,
        normalized_value: float,
        confidence: float,
        source: str,
        page_number: Optional[int] = None,
        raw_value: Optional[float] = None,
        unit: Optional[str] = None,
        original_text: Optional[str] = None,
        context: Optional[str] = None,
        derived: bool = False,
    ) -> MetricCandidate:
        candidate = MetricCandidate(
            field_name=field_name,
            normalized_value=normalized_value,
            confidence=confidence,
            source=source,
            page_number=page_number,
            raw_value=raw_value,
            unit=unit,
            original_text=(original_text or "").strip()[:200] or None,
            context=(context or "").strip()[:240] or None,
            derived=derived,
        )
        result.metric_candidates.append(candidate)
        return candidate

    def _apply_metric_candidate(
        self,
        result: ExtractionResult,
        attr_name: str,
        field_name: str,
        value: float,
        confidence: float,
        source: str,
        page_number: Optional[int] = None,
        raw_value: Optional[float] = None,
        unit: Optional[str] = None,
        original_text: Optional[str] = None,
        context: Optional[str] = None,
        derived: bool = False,
    ):
        setattr(result, attr_name, value)
        candidate = self._store_candidate(
            result=result,
            field_name=field_name,
            normalized_value=value,
            confidence=confidence,
            source=source,
            page_number=page_number,
            raw_value=raw_value,
            unit=unit,
            original_text=original_text,
            context=context,
            derived=derived,
        )
        result.field_provenance[field_name] = candidate.to_dict()
    
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

    def _build_ocr_regions(
        self,
        page,
        page_type: str,
        excluded_regions: Optional[List[Tuple[float, float, float, float]]] = None,
    ) -> List[Tuple[float, float, float, float]]:
        rect = page.rect
        w = rect.width
        h = rect.height
        regions: List[Tuple[float, float, float, float]] = []

        if page_type == "drawing_heavy":
            regions.extend(
                [
                    (0.12, 0.10, 0.88, 0.88),
                    (0.12, 0.10, 0.50, 0.50),
                    (0.50, 0.10, 0.88, 0.50),
                    (0.12, 0.50, 0.50, 0.88),
                    (0.50, 0.50, 0.88, 0.88),
                    (0.00, 0.08, 0.18, 0.90),
                    (0.82, 0.08, 1.00, 0.78),
                ]
            )
        elif page_type == "mixed":
            regions.extend(
                [
                    (0.15, 0.12, 0.85, 0.82),
                    (0.70, 0.10, 1.00, 0.78),
                    (0.00, 0.00, 1.00, 0.14),
                ]
            )
        else:
            regions.extend(
                [
                    (0.05, 0.00, 0.95, 0.18),
                    (0.10, 0.18, 0.90, 0.62),
                ]
            )

        clips: List[Tuple[float, float, float, float]] = []
        for x0, y0, x1, y1 in regions:
            clip = (rect.x0 + x0 * w, rect.y0 + y0 * h, rect.x0 + x1 * w, rect.y0 + y1 * h)
            if excluded_regions and self._intersects_any_region(clip, excluded_regions):
                continue
            clips.append(clip)
        return clips

    def _ocr_page_regions(
        self,
        page,
        page_type: str = "mixed",
        excluded_regions: Optional[List[Tuple[float, float, float, float]]] = None,
    ) -> str:
        """OCR targeted regions of a page to capture dimension callouts quickly."""
        if not HAS_OCR:
            return ""

        # Render crops at moderate DPI for better dimension capture
        mat = fitz.Matrix(200/72, 200/72)
        clip_regions = self._build_ocr_regions(page, page_type, excluded_regions=excluded_regions)

        text_parts = []
        for x0, y0, x1, y1 in clip_regions:
            clip = fitz.Rect(x0, y0, x1, y1)
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

    def _rank_pages_for_ocr(
        self,
        doc,
        pages_with_text: List[Tuple[int, str]],
        page_profiles: Optional[List[Dict[str, Any]]] = None,
    ) -> List[int]:
        """Rank pages likely to contain drawing dimensions."""
        scores = []
        text_map = {p: t for p, t in pages_with_text}
        profile_map = {
            int(profile["page_number"]) - 1: profile
            for profile in (page_profiles or [])
            if profile.get("page_number") is not None
        }

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

            profile = profile_map.get(page_num, {})
            page_type = profile.get("page_type")
            excluded_region_count = int(profile.get("excluded_region_count", 0))
            page_type_bonus = {
                "drawing_heavy": 1.8,
                "mixed": 1.0,
                "light_text": 0.4,
                "text_heavy": -0.4,
            }.get(page_type, 0.0)

            score = size_score + density_score + keyword_bonus + vector_bonus + page_type_bonus - (excluded_region_count * 0.08)
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
            page_profiles = []
            
            # Phase 1: Extract text from all pages (fast with PyMuPDF)
            self._report_progress(5, 100, "Extracting text from pages...")
            
            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text("text")
                word_count = 0
                drawing_count = 0
                try:
                    word_count = len(page.get_text("words"))
                except Exception:
                    pass
                try:
                    drawing_count = len(page.get_drawings())
                except Exception:
                    pass
                
                if text.strip():
                    pages_with_text.append((page_num, text))
                    all_text += text + "\n\n"
                page_type = self._classify_page_type(len(text), word_count, drawing_count)
                page_analysis = self._extract_dimensions_from_page(
                    page=page,
                    text=text,
                    result=result,
                    page_number=page_num + 1,
                    page_type=page_type,
                )

                page_profiles.append(
                    {
                        "page_number": page_num + 1,
                        "text_length": len(text),
                        "word_count": word_count,
                        "drawing_count": drawing_count,
                        "page_type": page_type,
                        "page_role": page_analysis.get("page_role", "general_sheet"),
                        "page_scale_feet_per_inch": page_analysis.get("page_scale_feet_per_inch"),
                        "page_dimension_mode": page_analysis.get("page_dimension_mode"),
                        "excluded_region_count": page_analysis.get("excluded_region_count", 0),
                        "filtered_text_length": page_analysis.get("filtered_text_length", len(text)),
                    }
                )
                
                # Report progress (text extraction phase: 5-40%)
                progress = 5 + int((page_num / total_pages) * 35)
                self._report_progress(progress, 100, f"Reading page {page_num + 1}/{total_pages}")
            
            print(f"  [1/4] Text extraction: {len(pages_with_text)}/{total_pages} pages have text")
            
            # Phase 2: Extract dimensions (40-50%)
            self._report_progress(45, 100, "Analyzing dimensions...")
            
            # Check if we found dimensions - if not and OCR is available, use it
            needs_ocr = HAS_OCR and self._should_run_ocr(result, all_text)
            
            if needs_ocr:
                ranked_pages = self._rank_pages_for_ocr(doc, pages_with_text, page_profiles=page_profiles)
                pages_to_ocr = ranked_pages[: min(6, len(ranked_pages))]
                print(f"  [2/4] Running targeted OCR on {len(pages_to_ocr)} ranked pages...")
                self._report_progress(50, 100, "No dimensions found - running OCR...")

                ocr_start = time.time()
                max_ocr_seconds = 140
                combined_ocr_text = ""
                profile_map = {profile["page_number"]: profile for profile in page_profiles}

                # OCR only the most promising pages and stop early once we have enough data.
                for ocr_index, page_num in enumerate(pages_to_ocr):
                    if time.time() - ocr_start > max_ocr_seconds:
                        print("  OCR time cap reached; returning best-effort results")
                        break

                    page = doc[page_num]
                    page_profile = profile_map.get(page_num + 1, {})
                    self._report_progress(
                        50 + int(((ocr_index + 1) / max(len(pages_to_ocr), 1)) * 30),
                        100,
                        f"OCR page {page_num + 1}/{total_pages}..."
                    )

                    words = page.get_text("words")
                    lines = self._group_words_into_lines(words)
                    excluded_regions = self._estimate_excluded_regions(
                        page,
                        lines,
                        page_profile.get("page_type", "mixed"),
                    )
                    page_text = self._ocr_page_regions(
                        page,
                        page_type=page_profile.get("page_type", "mixed"),
                        excluded_regions=excluded_regions,
                    )
                    if page_text:
                        combined_ocr_text += page_text + "\n\n"
                        self._extract_dimensions_from_text(
                            page_text,
                            result,
                            source="ocr",
                            page_number=page_num + 1,
                            page_type=page_profile.get("page_type", "mixed"),
                            page_role=page_profile.get("page_role", "general_sheet"),
                        )

                    if self._has_enough_dimensions(result):
                        break

                if combined_ocr_text:
                    all_text += "\n\n=== OCR TEXT ===\n" + combined_ocr_text
                    result.extraction_method = "pymupdf_with_ocr"
                    print(f"       OCR extracted {len(combined_ocr_text)} chars of text")
            
            print(f"  [2/4] Dimension extraction complete")
            
            self._refine_footprint_from_plan_pages(doc, result, page_profiles)
            
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

            result.page_profiles = page_profiles
            
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
                    if text.strip():
                        self._extract_dimensions_from_text(
                            text,
                            result,
                            source="text",
                            page_number=i + 1,
                            page_type=self._classify_page_type(len(text), 0, 0),
                            page_role=self._classify_page_role(text),
                        )
                    
                    progress = int((i / pages_to_scan) * 60)
                    self._report_progress(progress, 100, f"Reading page {i + 1}/{pages_to_scan}")
                
                # Extract data
                self._report_progress(65, 100, "Analyzing dimensions...")
                
                self._report_progress(80, 100, "Extracting project info...")
                self._extract_project_info(all_text, result, pdf_path)
                
                self._report_progress(90, 100, "Calculating derived values...")
                self._calculate_derived_values(result)
                
                self._report_progress(100, 100, "Complete!")
                
        except Exception as e:
            print(f"  ERROR in pdfplumber parsing: {e}")
        
        return result
    
    @staticmethod
    def _parse_numeric_token(raw_value: str) -> Optional[float]:
        try:
            return float(raw_value.replace(",", "").strip())
        except ValueError:
            return None

    @staticmethod
    def _classify_page_type(text_length: int, word_count: int, drawing_count: int) -> str:
        if drawing_count >= 40 and word_count < 150:
            return "drawing_heavy"
        if text_length >= 3000 or word_count >= 600:
            return "text_heavy"
        if drawing_count >= 10:
            return "mixed"
        return "light_text"

    @staticmethod
    def _classify_page_role(text: str) -> str:
        lowered = text.lower()
        if any(
            term in lowered
            for term in (
                "roof plan",
                "floor plan",
                "site plan",
                "overall plan",
                "ground floor plan",
                "first floor plan",
                "footprint",
                "layout plan",
            )
        ):
            return "plan_sheet"
        if any(
            term in lowered
            for term in (
                "detail",
                "section",
                "elevation",
                "schedule",
                "legend",
                "window schedule",
                "door schedule",
                "joinery",
            )
        ):
            return "detail_sheet"
        return "general_sheet"

    @staticmethod
    def _has_component_dimension_noise(context: str) -> bool:
        component_terms = (
            "post",
            "posts",
            "timber",
            "beam",
            "column",
            "stud",
            "joist",
            "rafter",
            "cabinet",
            "fridge",
            "vanity",
            "bench",
            "bulkhead",
            "door",
            "window",
            "shower",
            "gutter",
            "fascia",
            "downpipe",
            "screen",
            "typ",
            "typ.",
            "approx",
            "overhead door",
            "sectional",
        )
        return any(term in context for term in component_terms)

    def _dimension_area_consistency_score(
        self,
        length_ft: float,
        width_ft: float,
        roof_area_sqft: Optional[float],
    ) -> float:
        if not roof_area_sqft or roof_area_sqft <= 0:
            return 0.0
        implied_area = length_ft * width_ft
        ratio = implied_area / roof_area_sqft
        if 0.65 <= ratio <= 1.55:
            return 1.5
        if 0.45 <= ratio <= 2.0:
            return 0.7
        if ratio < 0.2 or ratio > 4.0:
            return -2.4
        if ratio < 0.35 or ratio > 2.5:
            return -1.6
        return -0.6

    def _perimeter_consistency_score(
        self,
        perimeter_ft: float,
        roof_area_sqft: Optional[float],
    ) -> float:
        if not roof_area_sqft or roof_area_sqft <= 0:
            return 0.0
        square_perimeter = 4 * (roof_area_sqft ** 0.5)
        if perimeter_ft < square_perimeter * 0.55:
            return -2.2
        if perimeter_ft < square_perimeter * 0.8:
            return -0.8
        if perimeter_ft <= square_perimeter * 3.2:
            return 0.7
        if perimeter_ft <= square_perimeter * 5.0:
            return -0.3
        return -1.6

    @staticmethod
    def _expand_bbox(
        bbox: Tuple[float, float, float, float],
        pad_x: float,
        pad_y: float,
        page_rect=None,
    ) -> Tuple[float, float, float, float]:
        x0, y0, x1, y1 = bbox
        if page_rect is None:
            return (x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y)
        return (
            max(page_rect.x0, x0 - pad_x),
            max(page_rect.y0, y0 - pad_y),
            min(page_rect.x1, x1 + pad_x),
            min(page_rect.y1, y1 + pad_y),
        )

    @staticmethod
    def _rect_intersects(
        bbox_a: Tuple[float, float, float, float],
        bbox_b: Tuple[float, float, float, float],
    ) -> bool:
        ax0, ay0, ax1, ay1 = bbox_a
        bx0, by0, bx1, by1 = bbox_b
        return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0

    def _intersects_any_region(
        self,
        bbox: Tuple[float, float, float, float],
        excluded_regions: List[Tuple[float, float, float, float]],
    ) -> bool:
        return any(self._rect_intersects(bbox, region) for region in excluded_regions)

    @staticmethod
    def _group_words_into_lines(words: List[Tuple[Any, ...]]) -> List[Dict[str, Any]]:
        line_map: Dict[Tuple[int, int], List[Tuple[Any, ...]]] = {}
        for word in words:
            block_no = int(word[5]) if len(word) > 5 else 0
            line_no = int(word[6]) if len(word) > 6 else 0
            line_map.setdefault((block_no, line_no), []).append(word)

        lines: List[Dict[str, Any]] = []
        for _, line_words in sorted(line_map.items()):
            sorted_words = sorted(line_words, key=lambda item: item[0])
            text = " ".join(str(item[4]) for item in sorted_words).strip()
            if not text:
                continue
            x0 = min(float(item[0]) for item in sorted_words)
            y0 = min(float(item[1]) for item in sorted_words)
            x1 = max(float(item[2]) for item in sorted_words)
            y1 = max(float(item[3]) for item in sorted_words)
            lines.append(
                {
                    "text": text,
                    "bbox": (x0, y0, x1, y1),
                    "words": sorted_words,
                }
            )
        return lines

    def _estimate_excluded_regions(
        self,
        page,
        lines: List[Dict[str, Any]],
        page_type: str,
    ) -> List[Tuple[float, float, float, float]]:
        rect = page.rect
        width = rect.width
        height = rect.height
        excluded: List[Tuple[float, float, float, float]] = []
        layout_terms = (
            "schedule",
            "legend",
            "general notes",
            "notes",
            "abbreviations",
            "window",
            "door",
            "finish",
            "fixture",
            "revision",
            "title block",
            "key plan",
        )

        for line in lines:
            line_text = line["text"].lower()
            bbox = line["bbox"]
            rel_x0 = bbox[0] - rect.x0
            rel_y0 = bbox[1] - rect.y0
            is_layout_text = any(term in line_text for term in layout_terms)
            in_title_block = rel_x0 > width * 0.62 and rel_y0 > height * 0.68
            in_side_schedule = rel_x0 > width * 0.72 or rel_y0 > height * 0.86
            if is_layout_text and (in_title_block or in_side_schedule or page_type != "text_heavy"):
                excluded.append(self._expand_bbox(bbox, 18, 10, rect))

        bottom_right_lines = [
            line for line in lines
            if (line["bbox"][0] - rect.x0) > width * 0.62 and (line["bbox"][1] - rect.y0) > height * 0.68
        ]
        if len(bottom_right_lines) >= 6:
            excluded.append((rect.x0 + width * 0.62, rect.y0 + height * 0.68, rect.x1, rect.y1))

        right_margin_lines = [
            line for line in lines
            if (line["bbox"][0] - rect.x0) > width * 0.82 and len(line["text"]) > 8
        ]
        if len(right_margin_lines) >= 8 and page_type in {"drawing_heavy", "mixed"}:
            excluded.append((rect.x0 + width * 0.82, rect.y0, rect.x1, rect.y1))

        return excluded

    def _build_filtered_page_text(
        self,
        lines: List[Dict[str, Any]],
        excluded_regions: List[Tuple[float, float, float, float]],
    ) -> str:
        kept_lines = [
            line["text"]
            for line in lines
            if not self._intersects_any_region(line["bbox"], excluded_regions)
        ]
        return "\n".join(kept_lines)

    def _count_nearby_drawings(
        self,
        bbox: Tuple[float, float, float, float],
        drawing_rects: List[Tuple[float, float, float, float]],
    ) -> int:
        probe = self._expand_bbox(bbox, 36, 24)
        return sum(1 for rect in drawing_rects if self._rect_intersects(probe, rect))

    def _derive_dimensions_from_ratio(
        self,
        roof_area_sqft: float,
        aspect_ratio: float,
    ) -> Optional[Tuple[float, float]]:
        if roof_area_sqft <= 0 or aspect_ratio <= 0:
            return None
        aspect_ratio = max(1.0, min(aspect_ratio, 6.0))
        width_ft = (roof_area_sqft / aspect_ratio) ** 0.5
        length_ft = width_ft * aspect_ratio
        if length_ft <= 0 or width_ft <= 0:
            return None
        return length_ft, width_ft

    @staticmethod
    def _parse_fraction_token(raw_value: str) -> Optional[float]:
        token = (raw_value or "").strip()
        if not token:
            return None
        if "/" in token:
            try:
                numerator, denominator = token.split("/", 1)
                return float(numerator) / float(denominator)
            except (ValueError, ZeroDivisionError):
                return None
        try:
            return float(token)
        except ValueError:
            return None

    def _extract_page_scale(self, text: str) -> Optional[float]:
        lowered = text.lower()

        metric_match = re.search(r"(?:scale[:\s]*)?1\s*[:/]\s*(\d{2,4})\b", lowered)
        if metric_match:
            scale_ratio = self._parse_numeric_token(metric_match.group(1))
            if scale_ratio and 10 <= scale_ratio <= 1000:
                return scale_ratio / 12.0

        imperial_match = re.search(
            r"(\d+(?:/\d+)?)\s*(?:\"|in)?\s*=\s*(\d+(?:\.\d+)?)\s*'?\s*(?:-\s*0\s*\")?",
            lowered,
        )
        if imperial_match:
            paper_inches = self._parse_fraction_token(imperial_match.group(1))
            real_feet = self._parse_numeric_token(imperial_match.group(2))
            if paper_inches and real_feet and paper_inches > 0:
                return real_feet / paper_inches

        return None

    def _infer_page_dimension_mode(self, text: str) -> Optional[str]:
        lowered = text.lower()
        if re.search(r"\b\d+(?:\.\d+)?\s*mm\b", lowered) or "mÂ²" in lowered or re.search(r"\b1\s*[:/]\s*\d{2,4}\b", lowered):
            return "metric"
        if re.search(r"\d+(?:/\d+)?\s*(?:\"|in)?\s*=\s*\d+(?:\.\d+)?\s*'?", lowered):
            return "imperial"
        return None

    def _convert_dimension_chain_value(
        self,
        raw_value: float,
        unit: Optional[str],
        page_dimension_mode: Optional[str],
    ) -> Optional[float]:
        if unit:
            converted = self._length_to_feet(raw_value, unit)
            return converted if 4 <= converted <= 2000 else None
        if page_dimension_mode == "metric" and 500 <= raw_value <= 50000:
            converted = raw_value / 304.8
            return converted if 4 <= converted <= 2000 else None
        if page_dimension_mode == "imperial" and 4 <= raw_value <= 2000:
            return raw_value
        return None

    def _select_vector_cluster_rect(
        self,
        page,
        excluded_regions: List[Tuple[float, float, float, float]],
    ) -> Optional[Tuple[Tuple[float, float, float, float], float]]:
        rect = page.rect
        page_area = max(rect.width * rect.height, 1.0)
        candidates: List[Tuple[float, Tuple[float, float, float, float]]] = []

        cluster_rects = []
        try:
            if hasattr(page, "cluster_drawings"):
                cluster_rects = page.cluster_drawings()
        except Exception:
            cluster_rects = []

        normalized_clusters: List[Tuple[float, float, float, float]] = []
        for cluster in cluster_rects or []:
            try:
                normalized_clusters.append((float(cluster.x0), float(cluster.y0), float(cluster.x1), float(cluster.y1)))
            except Exception:
                continue

        if not normalized_clusters:
            try:
                for drawing in page.get_drawings():
                    drawing_rect = drawing.get("rect")
                    if drawing_rect:
                        normalized_clusters.append(
                            (
                                float(drawing_rect.x0),
                                float(drawing_rect.y0),
                                float(drawing_rect.x1),
                                float(drawing_rect.y1),
                            )
                        )
            except Exception:
                normalized_clusters = []

        center_x = rect.x0 + rect.width / 2.0
        center_y = rect.y0 + rect.height / 2.0

        for bbox in normalized_clusters:
            if self._intersects_any_region(bbox, excluded_regions):
                continue
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            if width < rect.width * 0.10 or height < rect.height * 0.10:
                continue
            if width > rect.width * 0.95 or height > rect.height * 0.95:
                continue
            area_ratio = (width * height) / page_area
            if area_ratio < 0.02 or area_ratio > 0.72:
                continue
            aspect_ratio = max(width, height) / max(min(width, height), 1.0)
            if aspect_ratio > 6.0:
                continue

            bbox_center_x = (bbox[0] + bbox[2]) / 2.0
            bbox_center_y = (bbox[1] + bbox[3]) / 2.0
            offset_x = abs(bbox_center_x - center_x) / max(rect.width, 1.0)
            offset_y = abs(bbox_center_y - center_y) / max(rect.height, 1.0)
            centrality = max(0.0, 1.0 - (offset_x + offset_y))
            score = (area_ratio * 4.5) + centrality
            candidates.append((score, bbox))

        if not candidates:
            return None

        best_score, best_bbox = max(candidates, key=lambda item: item[0])
        return best_bbox, best_score

    def _estimate_vector_footprint_dimensions(
        self,
        page,
        result: ExtractionResult,
        page_number: int,
        excluded_regions: List[Tuple[float, float, float, float]],
        page_role: str,
        page_scale_feet_per_inch: Optional[float] = None,
    ):
        if page_role != "plan_sheet" or not result.roof_area_sqft:
            return

        selection = self._select_vector_cluster_rect(page, excluded_regions)
        if not selection:
            return

        bbox, cluster_score = selection
        width_pt = bbox[2] - bbox[0]
        height_pt = bbox[3] - bbox[1]
        aspect_ratio = max(width_pt, height_pt) / max(min(width_pt, height_pt), 1.0)
        derived_dims = None
        footprint_source = "vector_footprint"
        if page_scale_feet_per_inch:
            width_ft_from_scale = (width_pt / 72.0) * page_scale_feet_per_inch
            height_ft_from_scale = (height_pt / 72.0) * page_scale_feet_per_inch
            scale_length_ft = max(width_ft_from_scale, height_ft_from_scale)
            scale_width_ft = min(width_ft_from_scale, height_ft_from_scale)
            scale_score = self._dimension_area_consistency_score(
                scale_length_ft,
                scale_width_ft,
                result.roof_area_sqft,
            )
            if scale_score >= -0.6:
                derived_dims = (scale_length_ft, scale_width_ft)
                footprint_source = "scale_vector_footprint"
        if not derived_dims:
            derived_dims = self._derive_dimensions_from_ratio(result.roof_area_sqft, aspect_ratio)
        if not derived_dims:
            return

        length_ft, width_ft = derived_dims
        perimeter_ft = 2 * (length_ft + width_ft)
        score = 2.4 + min(cluster_score, 1.6)
        score += self._dimension_area_consistency_score(length_ft, width_ft, result.roof_area_sqft)
        current_length_provenance = result.field_provenance.get("length_ft", {})
        current_perimeter_provenance = result.field_provenance.get("perimeter_ft", {})
        can_replace_dimensions = (
            not current_length_provenance
            or current_length_provenance.get("derived")
            or current_length_provenance.get("confidence", float("-inf")) < 3.4
        )
        can_replace_perimeter = (
            not current_perimeter_provenance
            or current_perimeter_provenance.get("derived")
            or current_perimeter_provenance.get("confidence", float("-inf")) < 3.6
        )

        if can_replace_dimensions and score > self._best_dimension_score:
            self._best_dimension_score = score
            self._apply_metric_candidate(
                result=result,
                attr_name="length_ft",
                field_name="length_ft",
                value=length_ft,
                confidence=score,
                source=footprint_source,
                page_number=page_number,
                original_text="derived from vector footprint geometry",
                context=f"vector bbox={bbox}",
            )
            self._apply_metric_candidate(
                result=result,
                attr_name="width_ft",
                field_name="width_ft",
                value=width_ft,
                confidence=score,
                source=footprint_source,
                page_number=page_number,
                original_text="derived from vector footprint geometry",
                context=f"vector bbox={bbox}",
            )

        perimeter_score = score + self._perimeter_consistency_score(perimeter_ft, result.roof_area_sqft)
        if can_replace_perimeter and perimeter_score > self._best_perimeter_score:
            self._best_perimeter_score = perimeter_score
            self._apply_metric_candidate(
                result=result,
                attr_name="perimeter_ft",
                field_name="perimeter_ft",
                value=perimeter_ft,
                confidence=perimeter_score,
                source=footprint_source,
                page_number=page_number,
                original_text="derived from vector footprint geometry",
                context=f"vector bbox={bbox}",
            )

    def _estimate_dimension_chain_footprint(
        self,
        page,
        result: ExtractionResult,
        page_number: int,
        lines: List[Dict[str, Any]],
        excluded_regions: List[Tuple[float, float, float, float]],
        page_role: str,
        page_dimension_mode: Optional[str],
    ):
        if page_role != "plan_sheet" or not result.roof_area_sqft:
            return

        selection = self._select_vector_cluster_rect(page, excluded_regions)
        if not selection:
            return

        cluster_bbox, cluster_score = selection
        x0, y0, x1, y1 = cluster_bbox
        margin_x = max(18.0, (x1 - x0) * 0.12)
        margin_y = max(18.0, (y1 - y0) * 0.12)
        value_pattern = re.compile(
            r"(\d{2,5}(?:\.\d+)?)\s*(mm|cm|m|ft|feet|')?",
            re.IGNORECASE,
        )

        horizontal_candidates: List[Dict[str, Any]] = []
        vertical_candidates: List[Dict[str, Any]] = []

        for line in lines:
            bbox = line["bbox"]
            if self._intersects_any_region(bbox, excluded_regions):
                continue
            line_text = line["text"]
            line_lower = line_text.lower()
            if "x" in line_lower or self._has_component_dimension_noise(line_lower):
                continue
            numeric_tokens = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", line_lower)
            if len(numeric_tokens) != 1:
                continue
            match = value_pattern.search(line_text)
            if not match:
                continue
            raw_value = self._parse_numeric_token(match.group(1))
            if raw_value is None:
                continue
            value_ft = self._convert_dimension_chain_value(raw_value, match.group(2), page_dimension_mode)
            if value_ft is None:
                continue

            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            horizontal_gap = min(abs(cy - y0), abs(cy - y1))
            vertical_gap = min(abs(cx - x0), abs(cx - x1))

            if x0 - margin_x <= cx <= x1 + margin_x and horizontal_gap <= margin_y:
                horizontal_candidates.append(
                    {
                        "value_ft": value_ft,
                        "gap": horizontal_gap,
                        "text": line_text,
                    }
                )
            if y0 - margin_y <= cy <= y1 + margin_y and vertical_gap <= margin_x:
                vertical_candidates.append(
                    {
                        "value_ft": value_ft,
                        "gap": vertical_gap,
                        "text": line_text,
                    }
                )

        if not horizontal_candidates or not vertical_candidates:
            return

        best_pair = None
        best_pair_score = float("-inf")
        for horizontal in horizontal_candidates:
            for vertical in vertical_candidates:
                length_ft = max(horizontal["value_ft"], vertical["value_ft"])
                width_ft = min(horizontal["value_ft"], vertical["value_ft"])
                score = 3.1 + min(cluster_score, 1.2)
                score += self._dimension_area_consistency_score(length_ft, width_ft, result.roof_area_sqft)
                score += max(0.0, 0.8 - (horizontal["gap"] / max(margin_y, 1.0)))
                score += max(0.0, 0.8 - (vertical["gap"] / max(margin_x, 1.0)))
                if score > best_pair_score:
                    best_pair_score = score
                    best_pair = (horizontal, vertical, length_ft, width_ft)

        if not best_pair or best_pair_score < 3.0:
            return

        current_length_provenance = result.field_provenance.get("length_ft", {})
        current_perimeter_provenance = result.field_provenance.get("perimeter_ft", {})
        can_replace_dimensions = (
            not current_length_provenance
            or current_length_provenance.get("derived")
            or current_length_provenance.get("confidence", float("-inf")) < 4.0
        )
        can_replace_perimeter = (
            not current_perimeter_provenance
            or current_perimeter_provenance.get("derived")
            or current_perimeter_provenance.get("confidence", float("-inf")) < 4.2
        )

        horizontal, vertical, length_ft, width_ft = best_pair
        perimeter_ft = 2 * (length_ft + width_ft)

        if can_replace_dimensions and best_pair_score > self._best_dimension_score:
            self._best_dimension_score = best_pair_score
            self._apply_metric_candidate(
                result=result,
                attr_name="length_ft",
                field_name="length_ft",
                value=length_ft,
                confidence=best_pair_score,
                source="dimension_chain",
                page_number=page_number,
                original_text=horizontal["text"],
                context=f"horizontal={horizontal['text']} vertical={vertical['text']}",
            )
            self._apply_metric_candidate(
                result=result,
                attr_name="width_ft",
                field_name="width_ft",
                value=width_ft,
                confidence=best_pair_score,
                source="dimension_chain",
                page_number=page_number,
                original_text=vertical["text"],
                context=f"horizontal={horizontal['text']} vertical={vertical['text']}",
            )

        perimeter_score = best_pair_score + self._perimeter_consistency_score(perimeter_ft, result.roof_area_sqft)
        if can_replace_perimeter and perimeter_score > self._best_perimeter_score:
            self._best_perimeter_score = perimeter_score
            self._apply_metric_candidate(
                result=result,
                attr_name="perimeter_ft",
                field_name="perimeter_ft",
                value=perimeter_ft,
                confidence=perimeter_score,
                source="dimension_chain",
                page_number=page_number,
                original_text="derived from outer dimension chain",
                context=f"horizontal={horizontal['text']} vertical={vertical['text']}",
            )

    def _refine_footprint_from_plan_pages(
        self,
        doc,
        result: ExtractionResult,
        page_profiles: List[Dict[str, Any]],
    ):
        if not result.roof_area_sqft:
            return

        for profile in page_profiles:
            if profile.get("page_role") != "plan_sheet":
                continue
            page_number = int(profile["page_number"])
            page = doc[page_number - 1]
            try:
                words = page.get_text("words")
            except Exception:
                words = []
            lines = self._group_words_into_lines(words)
            excluded_regions = self._estimate_excluded_regions(
                page,
                lines,
                profile.get("page_type", "mixed"),
            )
            self._estimate_dimension_chain_footprint(
                page=page,
                result=result,
                page_number=page_number,
                lines=lines,
                excluded_regions=excluded_regions,
                page_role=profile.get("page_role", "general_sheet"),
                page_dimension_mode=profile.get("page_dimension_mode"),
            )
            self._estimate_vector_footprint_dimensions(
                page=page,
                result=result,
                page_number=page_number,
                excluded_regions=excluded_regions,
                page_role=profile.get("page_role", "general_sheet"),
                page_scale_feet_per_inch=profile.get("page_scale_feet_per_inch"),
            )

    def _extract_dimensions_from_page_geometry(
        self,
        page,
        result: ExtractionResult,
        page_number: int,
        lines: List[Dict[str, Any]],
        excluded_regions: List[Tuple[float, float, float, float]],
        page_type: str,
        page_role: str,
    ):
        number_with_unit = re.compile(
            r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(mm|cm|mÂ²|m2|sq\.?\s*m|sqm|sqft|sq\.?\s*ft|sf|lf|linear\s*ft|m|ft|feet|')?",
            re.IGNORECASE,
        )
        lxw_pattern = re.compile(
            r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|feet|')?\s*[xXÃ—]\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|feet|')?",
            re.IGNORECASE,
        )
        drawing_rects: List[Tuple[float, float, float, float]] = []
        try:
            for drawing in page.get_drawings():
                rect = drawing.get("rect")
                if rect:
                    drawing_rects.append((float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)))
        except Exception:
            drawing_rects = []

        for line in lines:
            bbox = line["bbox"]
            if self._intersects_any_region(bbox, excluded_regions):
                continue
            nearby_drawings = self._count_nearby_drawings(bbox, drawing_rects)
            if nearby_drawings <= 0:
                continue

            line_text = line["text"]
            context = line_text.lower()

            dim_match = lxw_pattern.search(line_text)
            if dim_match:
                raw_a = self._parse_numeric_token(dim_match.group(1))
                raw_b = self._parse_numeric_token(dim_match.group(3))
                if raw_a is not None and raw_b is not None:
                    unit_a = dim_match.group(2)
                    unit_b = dim_match.group(4)
                    primary_unit = unit_a or unit_b
                    a_ft = self._length_to_feet(raw_a, primary_unit)
                    b_ft = self._length_to_feet(raw_b, unit_b or primary_unit)
                    if 8 <= a_ft <= 2000 and 8 <= b_ft <= 2000:
                        score = 2.2 + min(1.4, nearby_drawings * 0.08)
                        area_ft = a_ft * b_ft
                        numeric_tokens = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", line_text)
                        score += self._dimension_area_consistency_score(
                            max(a_ft, b_ft),
                            min(a_ft, b_ft),
                            result.roof_area_sqft,
                        )
                        if primary_unit:
                            score += 0.25
                        if any(keyword in context for keyword in ("building", "roof", "plan", "footprint")):
                            score += 0.8
                        if page_role == "plan_sheet":
                            score += 0.8
                        elif page_role == "detail_sheet":
                            score -= 1.0
                        if page_type == "drawing_heavy":
                            score += 0.2
                        if "approx" in context or "typ" in context:
                            score -= 1.2
                        if line_text.lower().count("x") >= 2:
                            score -= 1.2
                        if len(numeric_tokens) > 3:
                            score -= 0.9
                        if self._has_component_dimension_noise(context):
                            score -= 2.4
                        if min(a_ft, b_ft) < 15:
                            score -= 1.5
                        if max(a_ft, b_ft) < 40:
                            score -= 1.0
                        if area_ft < 1000:
                            score -= 1.6
                        elif area_ft > 20000:
                            score += 0.5
                        if score >= 2.8 and score > self._best_dimension_score:
                            self._best_dimension_score = score
                            self._apply_metric_candidate(
                                result=result,
                                attr_name="length_ft",
                                field_name="length_ft",
                                value=max(a_ft, b_ft),
                                confidence=score,
                                source="vector_text",
                                page_number=page_number,
                                raw_value=max(raw_a, raw_b),
                                unit=primary_unit,
                                original_text=dim_match.group(0),
                                context=line_text,
                            )
                            self._apply_metric_candidate(
                                result=result,
                                attr_name="width_ft",
                                field_name="width_ft",
                                value=min(a_ft, b_ft),
                                confidence=score,
                                source="vector_text",
                                page_number=page_number,
                                raw_value=min(raw_a, raw_b),
                                unit=primary_unit,
                                original_text=dim_match.group(0),
                                context=line_text,
                            )

            for value_match in number_with_unit.finditer(line_text):
                raw = self._parse_numeric_token(value_match.group(1))
                if raw is None:
                    continue
                unit = value_match.group(2)
                base_score = 1.5 + min(1.1, nearby_drawings * 0.06)
                if page_role == "plan_sheet":
                    base_score += 0.5
                elif page_role == "detail_sheet":
                    base_score -= 0.5
                if "height" in context or "ridge" in context or "parapet" in context:
                    height_ft = self._length_to_feet(raw, unit)
                    if 8 <= height_ft <= 250 and base_score > self._best_height_score:
                        self._best_height_score = base_score
                        self._apply_metric_candidate(
                            result=result,
                            attr_name="building_height_ft",
                            field_name="building_height_ft",
                            value=height_ft,
                            confidence=base_score,
                            source="vector_text",
                            page_number=page_number,
                            raw_value=raw,
                            unit=unit,
                            original_text=value_match.group(0),
                            context=line_text,
                        )
                if "area" in context:
                    area_sqft = self._area_to_sqft(raw, unit)
                    area_score = base_score + 0.4
                    if 100 <= area_sqft <= 10000000 and area_score > self._best_area_score:
                        self._best_area_score = area_score
                        self._apply_metric_candidate(
                            result=result,
                            attr_name="roof_area_sqft",
                            field_name="roof_area_sqft",
                            value=area_sqft,
                            confidence=area_score,
                            source="vector_text",
                            page_number=page_number,
                            raw_value=raw,
                            unit=unit,
                            original_text=value_match.group(0),
                            context=line_text,
                        )
                if "perimeter" in context or "linear" in context or "roof edge" in context:
                    perimeter_ft = self._length_to_feet(raw, unit)
                    perimeter_score = base_score + 0.2
                    perimeter_score += self._perimeter_consistency_score(perimeter_ft, result.roof_area_sqft)
                    if any(label in context for label in ("roof perimeter", "building perimeter", "roof edge perimeter", "total perimeter")):
                        perimeter_score += 1.4
                    elif "perimeter" in context:
                        perimeter_score += 0.8
                    if any(label in context for label in ("linear ft", "linear feet", "lf")):
                        perimeter_score += 0.4
                    if self._has_component_dimension_noise(context):
                        perimeter_score -= 1.8
                    if 20 <= perimeter_ft <= 50000 and perimeter_score > self._best_perimeter_score:
                        self._best_perimeter_score = perimeter_score
                        self._apply_metric_candidate(
                            result=result,
                            attr_name="perimeter_ft",
                            field_name="perimeter_ft",
                            value=perimeter_ft,
                            confidence=perimeter_score,
                            source="vector_text",
                            page_number=page_number,
                            raw_value=raw,
                            unit=unit,
                            original_text=value_match.group(0),
                            context=line_text,
                        )

    def _extract_dimensions_from_page(
        self,
        page,
        text: str,
        result: ExtractionResult,
        page_number: int,
        page_type: str,
    ) -> Dict[str, Any]:
        try:
            words = page.get_text("words")
        except Exception:
            words = []

        lines = self._group_words_into_lines(words)
        excluded_regions = self._estimate_excluded_regions(page, lines, page_type)
        filtered_text = self._build_filtered_page_text(lines, excluded_regions)
        text_for_scoring = filtered_text if filtered_text.strip() else text
        page_role = self._classify_page_role(text_for_scoring or text)
        page_scale_feet_per_inch = self._extract_page_scale(text_for_scoring or text)
        page_dimension_mode = self._infer_page_dimension_mode(text_for_scoring or text)

        if text_for_scoring.strip():
            self._extract_dimensions_from_text(
                text_for_scoring,
                result,
                source="text",
                page_number=page_number,
                page_type=page_type,
                page_role=page_role,
            )
        if lines:
            self._extract_dimensions_from_page_geometry(
                page=page,
                result=result,
                page_number=page_number,
                lines=lines,
                excluded_regions=excluded_regions,
                page_type=page_type,
                page_role=page_role,
            )

        return {
            "excluded_region_count": len(excluded_regions),
            "filtered_text_length": len(text_for_scoring),
            "word_count": len(words),
            "page_role": page_role,
            "page_scale_feet_per_inch": page_scale_feet_per_inch,
            "page_dimension_mode": page_dimension_mode,
        }

    @staticmethod
    def _normalize_unit(raw_unit: Optional[str]) -> str:
        return (raw_unit or "").lower().replace(" ", "")

    @classmethod
    def _length_to_feet(cls, value: float, unit: Optional[str]) -> float:
        normalized = cls._normalize_unit(unit)
        if normalized in {"mm"}:
            return value / 304.8
        if normalized in {"cm"}:
            return value / 30.48
        if normalized in {"m"}:
            return value * 3.28084
        return value

    @classmethod
    def _area_to_sqft(cls, value: float, unit: Optional[str]) -> float:
        normalized = cls._normalize_unit(unit)
        if normalized in {"m²", "m2", "sqm", "sq.m", "sqm.", "sqmeter", "sqmeters", "sqmetre", "sqmetres", "sqm²"}:
            return value * 10.7639
        if normalized in {"sq.m", "sq.m.", "sqmeter", "sqmetre", "sqmeters", "sqmetres"}:
            return value * 10.7639
        return value

    @staticmethod
    def _has_schedule_noise(context: str) -> bool:
        noise_terms = (
            "window schedule",
            "door schedule",
            "schedule",
            "door",
            "window",
            "joinery",
            "fixture",
            "cabinet",
            "room finish",
            "material schedule",
        )
        return any(term in context for term in noise_terms)

    def _extract_dimensions_from_text(
        self,
        text: str,
        result: ExtractionResult,
        source: str = "text",
        page_number: Optional[int] = None,
        page_type: str = "mixed",
        page_role: str = "general_sheet",
    ):
        """
        Extract dimensions using weighted scoring:
        - Labels boost confidence but are not required.
        - Unit-aware conversion (mm/cm/m/m² to ft/sqft).
        - Schedule/table noise is penalized to protect drawing-heavy plans.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        number_with_unit = re.compile(
            r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(mm|cm|m²|m2|sq\.?\s*m|sqm|sqft|sq\.?\s*ft|sf|lf|linear\s*ft|m|ft|feet|')?",
            re.IGNORECASE,
        )
        lxw_pattern = re.compile(
            r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|feet|')?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|feet|')?",
            re.IGNORECASE,
        )

        page_scope = text.lower()
        area_hint_match = re.search(
            r"(?:total|dwelling|roof|building|gross)\s*area[^\d]{0,24}(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(mÂ²|m2|sq\.?\s*m|sqm|sqft|sq\.?\s*ft|sf)",
            page_scope,
            re.IGNORECASE,
        )
        page_area_hint = None
        if area_hint_match:
            raw_area_hint = self._parse_numeric_token(area_hint_match.group(1))
            if raw_area_hint is not None:
                page_area_hint = self._area_to_sqft(raw_area_hint, area_hint_match.group(2))
        reference_area_sqft = result.roof_area_sqft or page_area_hint

        # Candidate 1: LxW dimensions (drawing callouts and labels)
        dim_candidates: List[Dict[str, Any]] = []
        for match in lxw_pattern.finditer(text):
            raw_a = self._parse_numeric_token(match.group(1))
            raw_b = self._parse_numeric_token(match.group(3))
            if raw_a is None or raw_b is None:
                continue
            unit_a = match.group(2)
            unit_b = match.group(4)
            primary_unit = unit_a or unit_b
            a_ft = self._length_to_feet(raw_a, primary_unit)
            b_ft = self._length_to_feet(raw_b, unit_b or primary_unit)
            if not (8 <= a_ft <= 2000 and 8 <= b_ft <= 2000):
                continue

            context = text[max(0, match.start() - 120):min(len(text), match.end() + 120)].lower()
            score = 1.0
            if any(keyword in context for keyword in ("building", "footprint", "roof", "ground floor", "first floor", "plan")):
                score += 1.5
            if page_role == "plan_sheet":
                score += 0.9
            elif page_role == "detail_sheet":
                score -= 1.1
            if page_type == "drawing_heavy":
                score += 0.15
            score += self._dimension_area_consistency_score(max(a_ft, b_ft), min(a_ft, b_ft), reference_area_sqft)
            if self._has_schedule_noise(context):
                score -= 1.5
            if self._has_component_dimension_noise(context):
                score -= 2.4
            if any(keyword in context for keyword in ("overall", "overall dimensions", "roof plan", "site plan")):
                score += 1.0
            if primary_unit:
                score += 0.35
            numeric_tokens = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", match.group(0))
            if len(numeric_tokens) > 2:
                score -= 0.8
            if a_ft * b_ft < 600:
                score -= 1.3
            if source == "ocr" and score <= 1.0:
                score -= 0.35
            dim_candidates.append(
                {
                    "score": score,
                    "length_ft": max(a_ft, b_ft),
                    "width_ft": min(a_ft, b_ft),
                    "raw_a": raw_a,
                    "raw_b": raw_b,
                    "unit": primary_unit,
                    "original_text": match.group(0),
                    "context": context,
                    "page_number": page_number,
                }
            )

        if dim_candidates:
            best_dim = max(
                dim_candidates,
                key=lambda item: (item["score"], item["length_ft"] * item["width_ft"]),
            )
            if best_dim["score"] >= 2.6 and best_dim["score"] > self._best_dimension_score:
                self._best_dimension_score = best_dim["score"]
                self._apply_metric_candidate(
                    result=result,
                    attr_name="length_ft",
                    field_name="length_ft",
                    value=best_dim["length_ft"],
                    confidence=best_dim["score"],
                    source=source,
                    page_number=best_dim["page_number"],
                    raw_value=max(best_dim["raw_a"], best_dim["raw_b"]),
                    unit=best_dim["unit"],
                    original_text=best_dim["original_text"],
                    context=best_dim["context"],
                )
                self._apply_metric_candidate(
                    result=result,
                    attr_name="width_ft",
                    field_name="width_ft",
                    value=best_dim["width_ft"],
                    confidence=best_dim["score"],
                    source=source,
                    page_number=best_dim["page_number"],
                    raw_value=min(best_dim["raw_a"], best_dim["raw_b"]),
                    unit=best_dim["unit"],
                    original_text=best_dim["original_text"],
                    context=best_dim["context"],
                )

        height_candidates: List[Dict[str, Any]] = []
        area_candidates: List[Dict[str, Any]] = []
        perimeter_candidates: List[Dict[str, Any]] = []

        # Candidate 2: Line-based extraction with nearby context.
        for idx, line in enumerate(lines):
            line_lower = line.lower()
            context = " ".join(lines[max(0, idx - 2):min(len(lines), idx + 3)]).lower()
            noise_penalty = 1.5 if self._has_schedule_noise(context) else 0.0
            numeric_tokens = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", line_lower)
            dense_numeric_row = len(numeric_tokens) >= 4

            # Height candidates
            if any(token in context for token in ("height", "ridge", "eave", "parapet", "hgt", "ht")):
                for value_match in number_with_unit.finditer(line):
                    raw = self._parse_numeric_token(value_match.group(1))
                    if raw is None:
                        continue
                    unit = value_match.group(2)
                    height_ft = self._length_to_feet(raw, unit)
                    if not (8 <= height_ft <= 250):
                        continue
                    score = 1.0
                    if "building height" in context:
                        score += 2.0
                    elif "height" in context:
                        score += 1.2
                    if any(word in context for word in ("ridge", "eave", "parapet")):
                        score += 0.45
                    if "max" in line_lower:
                        score -= 0.35
                    if unit:
                        score += 0.3
                    if idx < 10:
                        score += 0.2
                    if page_role == "plan_sheet":
                        score += 0.35
                    score -= noise_penalty
                    if dense_numeric_row:
                        score -= 0.4
                    height_candidates.append(
                        {
                            "score": score,
                            "value": height_ft,
                            "raw_value": raw,
                            "unit": unit,
                            "original_text": value_match.group(0),
                            "context": line,
                            "page_number": page_number,
                        }
                    )

            # Area candidates
            if "area" in context:
                for value_match in number_with_unit.finditer(line):
                    raw = self._parse_numeric_token(value_match.group(1))
                    if raw is None:
                        continue
                    unit = value_match.group(2)
                    area_sqft = self._area_to_sqft(raw, unit)
                    if not (100 <= area_sqft <= 10000000):
                        continue
                    score = 0.8
                    if "total roof area" in context:
                        score += 2.4
                    elif "roof area" in context:
                        score += 1.9
                    elif "building area" in context or "gross floor area" in context:
                        score += 1.5
                    elif "area" in context:
                        score += 0.9
                    if unit and any(token in unit.lower() for token in ("m", "sq", "sf", "ft")):
                        score += 0.3
                    if idx < 12:
                        score += 0.2
                    if page_role == "plan_sheet":
                        score += 0.35
                    score -= noise_penalty
                    if dense_numeric_row:
                        score -= 0.45
                    if source == "ocr" and score <= 1.0:
                        score -= 0.35
                    area_candidates.append(
                        {
                            "score": score,
                            "value": area_sqft,
                            "raw_value": raw,
                            "unit": unit,
                            "original_text": value_match.group(0),
                            "context": line,
                            "page_number": page_number,
                        }
                    )

            # Perimeter candidates
            if "perimeter" in context or "linear" in context or "roof edge" in context:
                for value_match in number_with_unit.finditer(line):
                    raw = self._parse_numeric_token(value_match.group(1))
                    if raw is None:
                        continue
                    unit = value_match.group(2)
                    if unit is None and (dense_numeric_row or noise_penalty > 0):
                        continue
                    perimeter_ft = self._length_to_feet(raw, unit)
                    if unit is None and perimeter_ft > 1200:
                        continue
                    if not (20 <= perimeter_ft <= 50000):
                        continue
                    score = 0.7
                    if "roof perimeter" in context or "roof edge perimeter" in context:
                        score += 2.2
                    elif "total perimeter" in context:
                        score += 2.0
                    elif "building perimeter" in context:
                        score += 1.8
                    elif "perimeter" in context:
                        score += 1.0
                    if "linear" in context or "lf" in context:
                        score += 0.35
                    if unit:
                        score += 0.25
                    if idx < 12:
                        score += 0.15
                    if page_role == "plan_sheet":
                        score += 0.55
                    elif page_role == "detail_sheet":
                        score -= 0.7
                    score += self._perimeter_consistency_score(perimeter_ft, reference_area_sqft)
                    if self._has_component_dimension_noise(context):
                        score -= 1.8
                    score -= noise_penalty
                    perimeter_candidates.append(
                        {
                            "score": score,
                            "value": perimeter_ft,
                            "raw_value": raw,
                            "unit": unit,
                            "original_text": value_match.group(0),
                            "context": line,
                            "page_number": page_number,
                        }
                    )

        if height_candidates:
            best_height = max(height_candidates, key=lambda item: (item["score"], item["value"]))
            if best_height["score"] > self._best_height_score:
                self._best_height_score = best_height["score"]
                self._apply_metric_candidate(
                    result=result,
                    attr_name="building_height_ft",
                    field_name="building_height_ft",
                    value=best_height["value"],
                    confidence=best_height["score"],
                    source=source,
                    page_number=best_height["page_number"],
                    raw_value=best_height["raw_value"],
                    unit=best_height["unit"],
                    original_text=best_height["original_text"],
                    context=best_height["context"],
                )

        if area_candidates:
            best_area = max(area_candidates, key=lambda item: (item["score"], item["value"]))
            if best_area["score"] > self._best_area_score:
                self._best_area_score = best_area["score"]
                self._apply_metric_candidate(
                    result=result,
                    attr_name="roof_area_sqft",
                    field_name="roof_area_sqft",
                    value=best_area["value"],
                    confidence=best_area["score"],
                    source=source,
                    page_number=best_area["page_number"],
                    raw_value=best_area["raw_value"],
                    unit=best_area["unit"],
                    original_text=best_area["original_text"],
                    context=best_area["context"],
                )

        if perimeter_candidates:
            best_perimeter = max(perimeter_candidates, key=lambda item: (item["score"], item["value"]))
            if best_perimeter["score"] > self._best_perimeter_score:
                self._best_perimeter_score = best_perimeter["score"]
                self._apply_metric_candidate(
                    result=result,
                    attr_name="perimeter_ft",
                    field_name="perimeter_ft",
                    value=best_perimeter["value"],
                    confidence=best_perimeter["score"],
                    source=source,
                    page_number=best_perimeter["page_number"],
                    raw_value=best_perimeter["raw_value"],
                    unit=best_perimeter["unit"],
                    original_text=best_perimeter["original_text"],
                    context=best_perimeter["context"],
                )
    
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
            self._apply_metric_candidate(
                result=result,
                attr_name="roof_area_sqft",
                field_name="roof_area_sqft",
                value=result.length_ft * result.width_ft,
                confidence=0.55,
                source="derived",
                original_text="derived from length x width",
                context="derived from extracted length and width",
                derived=True,
            )
        
        # Calculate perimeter from length x width
        if result.perimeter_ft is None and result.length_ft and result.width_ft:
            self._apply_metric_candidate(
                result=result,
                attr_name="perimeter_ft",
                field_name="perimeter_ft",
                value=2 * (result.length_ft + result.width_ft),
                confidence=0.5,
                source="derived",
                original_text="derived from 2 x (length + width)",
                context="derived from extracted length and width",
                derived=True,
            )
        
        # Estimate length/width from area (assume square-ish if not found)
        if result.roof_area_sqft and not result.length_ft and not result.width_ft:
            import math
            side = math.sqrt(result.roof_area_sqft)
            self._apply_metric_candidate(
                result=result,
                attr_name="length_ft",
                field_name="length_ft",
                value=side,
                confidence=0.3,
                source="derived",
                original_text="derived from sqrt(area)",
                context="estimated square footprint from roof area",
                derived=True,
            )
            self._apply_metric_candidate(
                result=result,
                attr_name="width_ft",
                field_name="width_ft",
                value=side,
                confidence=0.3,
                source="derived",
                original_text="derived from sqrt(area)",
                context="estimated square footprint from roof area",
                derived=True,
            )
            if result.perimeter_ft is None:
                self._apply_metric_candidate(
                    result=result,
                    attr_name="perimeter_ft",
                    field_name="perimeter_ft",
                    value=4 * side,
                    confidence=0.25,
                    source="derived",
                    original_text="derived from 4 x sqrt(area)",
                    context="estimated square footprint from roof area",
                    derived=True,
                )
        
        # Default height if not found
        if result.building_height_ft is None and result.roof_area_sqft:
            # Estimate: 20 ft for small buildings, 24 ft for larger ones
            if result.roof_area_sqft < 50000:
                estimated_height = 20.0
            else:
                estimated_height = 24.0
            self._apply_metric_candidate(
                result=result,
                attr_name="building_height_ft",
                field_name="building_height_ft",
                value=estimated_height,
                confidence=0.2,
                source="derived",
                original_text="default height estimate",
                context="fallback estimate based on roof area",
                derived=True,
            )
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
                "page_profiles": result.page_profiles,
                "field_provenance": result.field_provenance,
                "metric_candidates": [candidate.to_dict() for candidate in result.metric_candidates],
                "candidate_count": len(result.metric_candidates),
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
