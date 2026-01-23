"""
Test the advanced CAD building plan parser
"""
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from adapters.pdf_loader_advanced import parse_building_plan_auto

def test_cad_parser():
    pdf_path = Path("data/inputs/BC23-001053 Electrical Building Plans (General Building) - APPROVED.pdf")
    
    if not pdf_path.exists():
        print(f"ERROR: PDF not found at {pdf_path}")
        return
    
    print("\n" + "="*70)
    print(" TESTING ADVANCED CAD BUILDING PLAN PARSER")
    print("="*70)
    
    # Parse the PDF
    result = parse_building_plan_auto(pdf_path)
    
    # Display results
    print("\n" + "="*70)
    print(" EXTRACTION RESULTS")
    print("="*70)
    
    print(f"\nProject Information:")
    print(f"  Project Name:    {result.get('project_name', 'Not found')}")
    print(f"  Location:        {result.get('location', 'Not found')}")
    
    print(f"\nBuilding Dimensions:")
    print(f"  Length:          {result.get('length_ft', 'Not found')} ft")
    print(f"  Width:           {result.get('width_ft', 'Not found')} ft")
    print(f"  Height:          {result.get('building_height_ft', 'Not found')} ft")
    print(f"  Roof Area:       {result.get('roof_area_sqft', 'Not found')} sq ft")
    print(f"  Perimeter:       {result.get('perimeter_ft', 'Not found')} ft")
    print(f"  Corners:         {result.get('num_corners', 'Not found')}")
    
    print(f"\nExtraction Metadata:")
    print(f"  PDF Type:        {result.get('pdf_type', 'unknown')}")
    print(f"  Method:          {result.get('extraction_method', 'unknown')}")
    
    metadata = result.get('extraction_metadata', {})
    if metadata:
        print(f"  Pages Processed: {metadata.get('pages_processed', 'N/A')}")
        print(f"  Has OCR:         {metadata.get('has_ocr', False)}")
        print(f"  Has Vision:      {metadata.get('has_vision', False)}")
        print(f"  Rooms Found:     {metadata.get('room_count', 0)}")
    
    print("\n" + "="*70)
    
    # Check what's missing
    missing_libs = []
    try:
        import pdf2image
    except ImportError:
        missing_libs.append("pdf2image")
    
    try:
        import pytesseract
    except ImportError:
        missing_libs.append("pytesseract")
    
    try:
        import cv2
    except ImportError:
        missing_libs.append("opencv-python")
    
    if missing_libs:
        print("\n[WARNING] ADVANCED FEATURES DISABLED")
        print(f"   Missing libraries: {', '.join(missing_libs)}")
        print(f"\n   To enable OCR and computer vision, run:")
        print(f"   pip install {' '.join(missing_libs)}")
        print("\n   Note: pytesseract also requires Tesseract-OCR installed on your system")
        print("   Download from: https://github.com/UB-Mannheim/tesseract/wiki")
    else:
        print("\n[OK] All advanced features available!")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    test_cad_parser()
