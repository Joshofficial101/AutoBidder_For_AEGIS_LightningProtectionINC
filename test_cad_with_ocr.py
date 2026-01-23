"""
Test CAD parser WITH OCR enabled to see extracted dimensions
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

from adapters.pdf_loader_advanced import CADPlanParser

def test_with_ocr():
    pdf_path = Path("data/inputs/BC23-001053 Electrical Building Plans (General Building) - APPROVED.pdf")
    
    print("\n" + "="*70)
    print(" TESTING CAD PARSER WITH OCR ENABLED")
    print(" (This will take ~4 minutes - showing what CAN be extracted)")
    print("="*70)
    
    parser = CADPlanParser(pdf_path)
    
    # Enable OCR
    parser.parse(use_ocr=True)
    result = parser.get_formatted_output()
    
    print("\n" + "="*70)
    print(" SUCCESSFULLY EXTRACTED DIMENSIONS")
    print("="*70)
    
    print(f"\n📏 Building Dimensions:")
    print(f"   Length:          {result.get('length_ft', 'Not found')} ft")
    print(f"   Width:           {result.get('width_ft', 'Not found')} ft")
    print(f"   Height:          {result.get('building_height_ft', 'Not found')} ft")
    print(f"   Roof Area:       {result.get('roof_area_sqft', 'Not found'):,.0f} sq ft" if result.get('roof_area_sqft') else "   Roof Area:       Not found")
    print(f"   Perimeter:       {result.get('perimeter_ft', 'Not found'):,.0f} ft" if result.get('perimeter_ft') else "   Perimeter:       Not found")
    print(f"   Corners:         {result.get('num_corners', 'Not found')}")
    
    print(f"\n📋 Project Information:")
    print(f"   Project Name:    {result.get('project_name', 'Not found')}")
    print(f"   Location:        {result.get('location', 'Not found')}")
    
    print(f"\n⚙️  Extraction Method:")
    print(f"   Method:          {result.get('extraction_method', 'N/A')}")
    print(f"   Pages Processed: {result.get('extraction_metadata', {}).get('pages_processed', 'N/A')}")
    
    print("\n" + "="*70)
    print(" NOTE: This extraction took ~4 minutes with OCR enabled")
    print("="*70 + "\n")
    
    return result

if __name__ == "__main__":
    import time
    start = time.time()
    result = test_with_ocr()
    elapsed = time.time() - start
    
    print(f"\n⏱️  Total Time: {elapsed/60:.1f} minutes ({elapsed:.0f} seconds)")
    
    # Show if dimensions are usable
    if result.get('length_ft') and result.get('width_ft'):
        print(f"✅ SUCCESS: Dimensions extracted and ready for bidding!")
    else:
        print(f"⚠️  WARNING: Some dimensions missing - manual entry may be needed")
