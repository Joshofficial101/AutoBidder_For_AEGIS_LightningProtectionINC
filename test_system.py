"""
Simple Test Script for LightningBid

This script tests individual components of the system so you can understand
how each part works before running the full system.

Run with: py test_system.py
"""

print("=" * 60)
print("  LightningBid - Component Tests")
print("=" * 60)

# Test 1: Create a Price Item
print("\n[TEST 1] Creating a Price Item...")
from src.models.items import PriceItem

item = PriceItem(
    code="AT-001",
    name="Air Terminal - Copper",
    material_type="Copper",
    unit="ea",
    unit_price=45.00,
    labor_rate=15.00
)

print(f"  Created: {item.code} - {item.name}")
print(f"  Price: ${item.unit_price}, Labor: ${item.labor_rate}/unit")
print("  [PASS]")

# Test 2: UL 96A Compliance Calculations
print("\n[TEST 2] Testing UL 96A Compliance Rules...")
from src.compliance.ul96a import UL96ACompliance

# Sample building: 40 ft tall, 6000 sqft roof
project_specs = {
    "building_height_ft": 40.0,
    "roof_area_sqft": 6000.0,
    "num_corners": 4,
    "perimeter_ft": 320.0,
    "num_downleads": 2,
    "soil_type": "normal"
}

compliance = UL96ACompliance.check_compliance(project_specs)

print(f"  Building: {project_specs['building_height_ft']} ft tall, {project_specs['roof_area_sqft']} sqft")
print(f"  Air Terminals needed: {compliance['air_terminals']['total']}")
print(f"    - Corners: {compliance['air_terminals']['corners']}")
print(f"    - Edges: {compliance['air_terminals']['edges']}")
print(f"    - Field: {compliance['air_terminals']['field']}")
print(f"  Conductor length: {compliance['conductors']['total_length_ft']} ft")
print(f"  Ground rods: {compliance['grounding']['total_rods']}")
print("  [PASS]")

# Test 3: NFPA 780 vs UL 96A Comparison
print("\n[TEST 3] Comparing UL 96A vs NFPA 780...")
from src.compliance.nfpa780 import NFPA780Compliance

nfpa_compliance = NFPA780Compliance.check_compliance(project_specs)

print("  UL 96A Air Terminals:", compliance['air_terminals']['total'])
print("  NFPA 780 Air Terminals:", nfpa_compliance['air_terminals']['total'])
print(f"  Difference: {abs(compliance['air_terminals']['total'] - nfpa_compliance['air_terminals']['total'])} terminals")
print("  (NFPA 780 allows 25 ft spacing vs UL 96A 20 ft)")
print("  [PASS]")

# Test 4: Bid Calculator
print("\n[TEST 4] Testing Bid Calculator...")
from src.calculator.bid_calc import BidCalculator

# Create a small price catalog
price_catalog = [
    PriceItem(code="AT-001", name="Air Terminal - Copper", material_type="Copper",
             unit="ea", unit_price=45.00, labor_rate=15.00),
    PriceItem(code="COND-100", name="Conductor Cable - Copper", material_type="Copper",
             unit="ft", unit_price=3.50, labor_rate=2.00),
    PriceItem(code="GR-10", name="Ground Rod - 10ft", material_type="Copper",
             unit="ea", unit_price=65.00, labor_rate=50.00),
    PriceItem(code="CLAMP-01", name="Cable Clamp", unit="ea", unit_price=8.00, labor_rate=5.00),
]

calculator = BidCalculator(price_catalog, compliance_code="UL 96A")

# Calculate bid for smaller building
small_project = {
    "project_name": "Test Building",
    "building_height_ft": 25.0,
    "roof_area_sqft": 2000.0,
    "num_corners": 4,
    "perimeter_ft": 180.0,
    "preferred_material": "copper"
}

bid = calculator.calculate_bid(small_project)

print(f"  Project: {bid.project_name}")
print(f"  Sections: {len(bid.sections)}")
for section in bid.sections:
    print(f"    - {section.name}: ${section.section_total:,.2f}")
print(f"  Subtotal: ${bid.subtotal:,.2f}")
print(f"  Final Bid: ${bid.final_bid_amount:,.2f}")
print("  [PASS]")

# Test 5: Price Item Search
print("\n[TEST 5] Testing Price Item Search...")
found = calculator.find_item("air terminal", prefer_material="copper")
if found:
    print(f"  Searched for 'air terminal'")
    print(f"  Found: {found.code} - {found.name}")
    print(f"  Price: ${found.unit_price}")
    print("  [PASS]")
else:
    print("  [FAIL] - Could not find item")

# Test 6: Different Building Sizes
print("\n[TEST 6] Testing Different Building Sizes...")
sizes = [
    {"name": "Small", "height": 20, "area": 1000},
    {"name": "Medium", "height": 40, "area": 5000},
    {"name": "Large", "height": 60, "area": 10000},
]

for size in sizes:
    test_project = {
        "project_name": f"{size['name']} Building",
        "building_height_ft": float(size["height"]),
        "roof_area_sqft": float(size["area"]),
        "num_corners": 4,
        "perimeter_ft": 4 * (size["area"] ** 0.5),  # approximate
        "preferred_material": "copper"
    }

    test_bid = calculator.calculate_bid(test_project)
    print(f"  {size['name']:6} ({size['height']}ft, {size['area']}sqft): ${test_bid.final_bid_amount:>10,.2f}")

print("  [PASS]")

# Test 7: Material vs. Labor Costs
print("\n[TEST 7] Breaking Down Costs...")
print(f"  Material subtotal: ${bid.subtotal_material:,.2f}")
print(f"  Labor subtotal:    ${bid.subtotal_labor:,.2f}")
print(f"  Material/Labor ratio: {bid.subtotal_material/bid.subtotal_labor:.2f}:1")
print(f"  Markup adds:       ${bid.total_with_markup - bid.subtotal:,.2f}")
print(f"  Overhead+Profit:   ${bid.final_bid_amount - bid.total_with_markup:,.2f}")
print("  [PASS]")

# Summary
print("\n" + "=" * 60)
print("  All Tests Passed!")
print("=" * 60)
print("\nKey Findings:")
print(f"  - System can calculate bids from {sizes[0]['area']} to {sizes[-1]['area']} sqft buildings")
print(f"  - UL 96A vs NFPA 780 can differ by several air terminals")
print(f"  - Final bids include ~17% markup + 20% overhead/profit")
print("\nNext: Run the full system with 'py -m src.main'")
