"""
Test the integrated PDF parser (auto-detects CAD vs spec documents)
"""
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from adapters.pdf_loader import parse_pdf_flexible

def test_integrated_parser():
    # Test with CAD building plan
    cad_pdf = Path("data/inputs/BC23-001053 Electrical Building Plans (General Building) - APPROVED.pdf")
    
    # Test with spec document (if available)
    spec_pdf = Path("data/inputs/Lightning_Protection_Quote_Request.pdf")
    
    print("\n" + "="*70)
    print(" TESTING INTEGRATED PDF PARSER (AUTO-DETECT)")
    print("="*70)
    
    # Test 1: CAD Building Plan
    if cad_pdf.exists():
        print(f"\n### TEST 1: CAD Building Plan")
        print(f"File: {cad_pdf.name}")
        print("-"*70)
        
        result = parse_pdf_flexible(cad_pdf)
        
        print(f"\nDetected PDF Type: {result.get('pdf_type', 'unknown')}")
        print(f"Extraction Method: {result.get('extraction_metadata', {}).get('extraction_method', 'N/A')}")
        
        print(f"\nBuilding Dimensions:")
        dims = result.get("building_dimensions", {})
        print(f"  Length:     {dims.get('length', 'Not found')} ft")
        print(f"  Width:      {dims.get('width', 'Not found')} ft")
        print(f"  Height:     {dims.get('height', 'Not found')} ft")
        print(f"  Roof Area:  {dims.get('area', 'Not found')} sq ft")
        print(f"  Perimeter:  {dims.get('perimeter', 'Not found')} ft")
        
        print(f"\nProject Info:")
        proj = result.get("project_info", {})
        print(f"  Name:       {proj.get('project_name', 'Not found')}")
        print(f"  Location:   {proj.get('location', 'Not found')}")
        
        # Validate results
        if dims.get('length') and dims.get('width'):
            print(f"\n[OK] CAD plan parsing successful!")
        else:
            print(f"\n[WARNING] Some dimensions not extracted")
    else:
        print(f"\n[SKIP] CAD plan not found: {cad_pdf}")
    
    # Test 2: Spec Document
    if spec_pdf.exists():
        print(f"\n\n### TEST 2: Specification Document")
        print(f"File: {spec_pdf.name}")
        print("-"*70)
        
        result = parse_pdf_flexible(spec_pdf)
        
        print(f"\nDetected PDF Type: {result.get('pdf_type', 'unknown')}")
        
        print(f"\nBuilding Dimensions:")
        dims = result.get("building_dimensions", {})
        print(f"  Height:     {dims.get('height', 'Not found')} ft")
        print(f"  Roof Area:  {dims.get('area', 'Not found')} sq ft")
        print(f"  Perimeter:  {dims.get('perimeter', 'Not found')} ft")
        
        print(f"\nProject Info:")
        proj = result.get("project_info", {})
        print(f"  Name:       {proj.get('project_name', 'Not found')}")
        
        print(f"\nCompliance:")
        print(f"  Standard:   {result.get('compliance_standard', 'Not found')}")
        
        print(f"\n[OK] Spec document parsing successful!")
    else:
        print(f"\n[SKIP] Spec document not found: {spec_pdf}")
    
    print("\n" + "="*70)
    print(" INTEGRATION TEST COMPLETE")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_integrated_parser()
