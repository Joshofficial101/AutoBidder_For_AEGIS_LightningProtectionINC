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
from src.adapters.pdf_loader import extract_spec_terms
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

    # Step 2: Parse spec PDF (optional - we'll use sample data for demo)
    print("\nStep 2: Parsing Project Specifications...")
    pdf_path = find_first(["*.pdf"])

    if pdf_path:
        spec_terms = extract_spec_terms(pdf_path)
        print(f"  [OK] Scanned {pdf_path.name}")
        print(f"  Found references: {', '.join(list(spec_terms.keys())[:5])}...")
    else:
        print("  [INFO] No PDF found - using sample project data")

    # Step 3: Define project (in real use, this comes from PDF + user input)
    print("\nStep 3: Setting Up Project...")

    project_data = {
        "project_name": "Sample Office Building - Lightning Protection",
        "building_height_ft": 35.0,
        "roof_area_sqft": 5000.0,
        "num_corners": 4,
        "perimeter_ft": 280.0,
        "num_downleads": 2,
        "soil_type": "normal",
        "has_metal_roof": False,
        "preferred_material": "copper"
    }

    print(f"  Project: {project_data['project_name']}")
    print(f"  Building: {project_data['building_height_ft']} ft tall, {project_data['roof_area_sqft']} sqft roof")

    # Step 4: Calculate bid using selected compliance code
    compliance_code = "UL 96A"  # Could be "NFPA 780" instead
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
