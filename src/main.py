"""
LightningBid - Automated Lightning Protection Bidding System

Main entry point that orchestrates the entire bid generation process:
1. Load pricing data from Excel
2. Parse project specs from PDF (optional for demo)
3. Calculate compliance requirements (UL 96A or NFPA 780)
4. Generate bid with costs
5. Export to Excel and PDF

For demo purposes, we'll use sample project data.
"""

from pathlib import Path
from src.adapters.excel_loader import load_pricing_from_excel
from src.adapters.pdf_loader import extract_spec_terms, extract_project_data
from src.calculator.bid_calc import BidCalculator
from src.exporters.excel_export import ExcelBidExporter
from src.exporters.pdf_export import PDFSubmittalExporter

# Paths
ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "data" / "inputs"
OUTPUTS = ROOT / "data" / "outputs"

# Ensure output directory exists
OUTPUTS.mkdir(parents=True, exist_ok=True)


def find_first(patterns):
    """Find first file matching any of the given patterns."""
    for pat in patterns:
        for p in INPUTS.glob(pat):
            return p
    return None


def main():
    """
    Main workflow for LightningBid system.

    This demonstrates the complete pipeline from inputs to outputs.
    """
    print("=" * 60)
    print("  LIGHTNINGBID - Lightning Protection Bid Generator")
    print("=" * 60)
    print()

    # Step 1: Load pricing catalog from Excel
    print("Step 1: Loading Pricing Catalog...")
    excel_path = find_first(["*.xlsx", "*.xls"])

    if not excel_path:
        print("  [X] No Excel pricing file found in data/inputs/")
        print("  Please add a pricing spreadsheet (e.g., ULP_BID_SHEET_2022.xlsx)")
        print("\nUsing demo mode with sample pricing...")
        use_demo = True
    else:
        try:
            price_catalog = load_pricing_from_excel(excel_path)
            print(f"  [OK] Loaded {len(price_catalog)} pricing items from {excel_path.name}")
            use_demo = False
        except Exception as e:
            print(f"  WARNING: Could not parse {excel_path.name}")
            print(f"  Error: {str(e)[:100]}...")
            print("  (Your Excel may have a custom format - will use demo pricing)")
            print("\nUsing demo mode with sample pricing...")
            use_demo = True

    if use_demo:
        # For demo, we'll create some sample items
        from src.models.items import PriceItem
        price_catalog = [
            PriceItem(code="AT-001", name="Air Terminal - Copper", material_type="Copper",
                     unit="ea", unit_price=45.00, labor_rate=15.00),
            PriceItem(code="COND-100", name="Conductor Cable - Copper 4/0 AWG", material_type="Copper",
                     unit="ft", unit_price=3.50, labor_rate=2.00),
            PriceItem(code="GR-10", name="Ground Rod - 10ft Copper", material_type="Copper",
                     unit="ea", unit_price=65.00, labor_rate=50.00),
            PriceItem(code="CLAMP-01", name="Cable Clamp", unit="ea", unit_price=8.00, labor_rate=5.00),
            PriceItem(code="BOND-6", name="Bonding Wire #6 AWG", material_type="Copper",
                     unit="ft", unit_price=2.00, labor_rate=1.50),
        ]
        print(f"  [OK] Loaded {len(price_catalog)} demo pricing items")

    # Step 2: Parse spec PDF and extract project data
    print("\nStep 2: Parsing Project Specifications...")
    pdf_path = find_first(["*.pdf"])

    # Initialize project data with defaults
    project_data = {
        "project_name": "Lightning Protection Project",
        "building_height_ft": None,
        "roof_area_sqft": None,
        "num_corners": 4,
        "perimeter_ft": None,
        "num_downleads": 2,
        "soil_type": "normal",
        "has_metal_roof": False,
        "preferred_material": "copper"
    }
    
    # Default compliance code (will be overridden if found in PDF)
    compliance_code = "UL 96A"

    if pdf_path:
        try:
            print(f"  [OK] Scanning {pdf_path.name}...")
            extracted_data = extract_project_data(pdf_path)
            
            # Extract project info
            if extracted_data["project_info"]["project_name"]:
                project_data["project_name"] = extracted_data["project_info"]["project_name"]
            
            # Extract dimensions
            dims = extracted_data["building_dimensions"]
            if dims["height"]:
                project_data["building_height_ft"] = dims["height"]
            if dims["area"]:
                project_data["roof_area_sqft"] = dims["area"]
            if dims["perimeter"]:
                project_data["perimeter_ft"] = dims["perimeter"]
            
            # Extract material preferences
            mat_prefs = extracted_data["material_preferences"]
            if mat_prefs["preferred_material"]:
                project_data["preferred_material"] = mat_prefs["preferred_material"]
            if mat_prefs["has_metal_roof"]:
                project_data["has_metal_roof"] = True
            
            # Extract other info
            project_data["num_corners"] = extracted_data.get("num_corners", 4)
            project_data["soil_type"] = extracted_data.get("soil_type", "normal")
            
            # Use extracted compliance standard if found
            compliance_code = extracted_data.get("compliance_standard") or "UL 96A"
            
            print(f"  [OK] Extracted project data:")
            if project_data["project_name"]:
                print(f"    Project: {project_data['project_name']}")
            if dims["height"]:
                print(f"    Height: {dims['height']} ft")
            if dims["area"]:
                print(f"    Roof Area: {dims['area']} sqft")
            if dims["perimeter"]:
                print(f"    Perimeter: {dims['perimeter']} ft")
            if mat_prefs["preferred_material"]:
                print(f"    Material: {mat_prefs['preferred_material']}")
            if extracted_data.get("compliance_standard"):
                print(f"    Compliance: {extracted_data['compliance_standard']}")
            
            # Show what's missing
            missing = []
            if not dims["height"]:
                missing.append("height")
            if not dims["area"]:
                missing.append("roof area")
            if missing:
                print(f"  [INFO] Could not extract: {', '.join(missing)} - using defaults")
        except Exception as e:
            print(f"  [WARNING] Error parsing PDF: {str(e)[:100]}")
            print("  [INFO] Using sample project data")
            compliance_code = "UL 96A"
    else:
        print("  [INFO] No PDF found - using sample project data")
        compliance_code = "UL 96A"

    # Step 3: Fill in missing project data with defaults
    print("\nStep 3: Setting Up Project...")
    
    # Use defaults for missing critical data
    if not project_data["building_height_ft"]:
        project_data["building_height_ft"] = 35.0
        print("  [INFO] Using default height: 35 ft")
    
    if not project_data["roof_area_sqft"]:
        project_data["roof_area_sqft"] = 5000.0
        print("  [INFO] Using default roof area: 5000 sqft")
    
    if not project_data["perimeter_ft"]:
        # Estimate perimeter from area (assuming square building)
        import math
        side_length = math.sqrt(project_data["roof_area_sqft"])
        project_data["perimeter_ft"] = side_length * 4
        print(f"  [INFO] Estimated perimeter: {project_data['perimeter_ft']:.1f} ft")

    print(f"  Final Project: {project_data['project_name']}")
    print(f"  Building: {project_data['building_height_ft']} ft tall, {project_data['roof_area_sqft']} sqft roof")

    # Step 4: Calculate bid using extracted or default compliance code
    # compliance_code is set above from PDF extraction or defaults to "UL 96A"
    print(f"\nStep 4: Calculating Bid (using {compliance_code})...")

    calculator = BidCalculator(price_catalog, compliance_code=compliance_code)
    bid = calculator.calculate_bid(project_data)

    print(f"  [OK] Bid calculated with {len(bid.sections)} sections")
    for section in bid.sections:
        print(f"    - {section.name}: {len(section.line_items)} items, ${section.section_total:,.2f}")

    print(f"\n  Subtotal: ${bid.subtotal:,.2f}")
    print(f"  Total with markup: ${bid.total_with_markup:,.2f}")
    print(f"  FINAL BID: ${bid.final_bid_amount:,.2f}")

    # Step 5: Export to Excel
    print("\nStep 5: Generating Excel Bid Sheet...")
    excel_exporter = ExcelBidExporter()
    excel_output = OUTPUTS / f"bid_{project_data['project_name'].replace(' ', '_')}.xlsx"
    excel_exporter.export_bid(bid, excel_output)
    print(f"  [OK] Excel saved to: {excel_output}")

    # Step 6: Export to PDF
    print("\nStep 6: Generating PDF Submittal...")
    pdf_exporter = PDFSubmittalExporter(
        contractor_name="ABC Lightning Protection Co.",
        contractor_info={
            "address": "123 Main St, Your City, ST 12345",
            "phone": "(555) 123-4567",
            "email": "info@abclightning.com",
            "license": "LP-12345"
        }
    )
    pdf_output = OUTPUTS / f"submittal_{project_data['project_name'].replace(' ', '_')}.pdf"
    pdf_exporter.export_submittal(bid, pdf_output, compliance_code)
    print(f"  [OK] PDF saved to: {pdf_output}")

    # Done!
    print("\n" + "=" * 60)
    print("  [SUCCESS] BID PACKAGE COMPLETE!")
    print("=" * 60)
    print(f"\nOutputs saved to: {OUTPUTS}")
    print(f"  - {excel_output.name}")
    print(f"  - {pdf_output.name}")
    print("\nYou can now review and send these files to your client.")


if __name__ == "__main__":
    main()
