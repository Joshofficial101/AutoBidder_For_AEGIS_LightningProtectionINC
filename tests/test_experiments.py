"""
Experimental Tests - Try Changing These!

This file is designed for you to experiment with different scenarios.
Feel free to modify the values and see what happens!

Run with: py test_experiments.py
"""

from src.models.items import PriceItem
from src.calculator.bid_calc import BidCalculator
from src.compliance.ul96a import UL96ACompliance
from src.compliance.nfpa780 import NFPA780Compliance

print("=" * 70)
print("  LightningBid - Experimental Testing")
print("  Feel free to modify values and re-run!")
print("=" * 70)

# ============================================================================
# EXPERIMENT 1: How does building height affect cost?
# ============================================================================
print("\n[EXPERIMENT 1] Building Height Impact")
print("-" * 70)

# Create price catalog
prices = [
    PriceItem(code="AT-001", name="Air Terminal", unit="ea", unit_price=45.00, labor_rate=15.00),
    PriceItem(code="COND-100", name="Conductor", unit="ft", unit_price=3.50, labor_rate=2.00),
    PriceItem(code="GR-10", name="Ground Rod", unit="ea", unit_price=65.00, labor_rate=50.00),
    PriceItem(code="CLAMP-01", name="Clamp", unit="ea", unit_price=8.00, labor_rate=5.00),
]

calc = BidCalculator(prices, "UL 96A")

# Test different heights (same area)
heights = [20, 30, 40, 50, 60]  # TRY CHANGING THESE!
roof_area = 4000  # TRY CHANGING THIS!

print(f"Testing roof area: {roof_area} sqft at different heights")
print()

for height in heights:
    project = {
        "project_name": f"Test {height}ft",
        "building_height_ft": float(height),
        "roof_area_sqft": float(roof_area),
        "num_corners": 4,
        "perimeter_ft": 4 * (roof_area ** 0.5),  # approximate square
        "preferred_material": "copper"
    }

    bid = calc.calculate_bid(project)
    print(f"  {height:2d} ft tall: ${bid.final_bid_amount:>10,.2f}")

print("\n[TIP] Observation: Taller buildings need more conductor cable for downleads")

# ============================================================================
# EXPERIMENT 2: How does roof area affect cost?
# ============================================================================
print("\n[EXPERIMENT 2] Roof Area Impact")
print("-" * 70)

# Test different areas (same height)
areas = [2000, 4000, 6000, 8000, 10000]  # TRY CHANGING THESE!
building_height = 35  # TRY CHANGING THIS!

print(f"Testing building height: {building_height} ft at different roof areas")
print()

for area in areas:
    project = {
        "project_name": f"Test {area}sqft",
        "building_height_ft": float(building_height),
        "roof_area_sqft": float(area),
        "num_corners": 4,
        "perimeter_ft": 4 * (area ** 0.5),
        "preferred_material": "copper"
    }

    bid = calc.calculate_bid(project)
    cost_per_sqft = bid.final_bid_amount / area
    print(f"  {area:>5,} sqft: ${bid.final_bid_amount:>10,.2f} (${cost_per_sqft:.2f}/sqft)")

print("\n[TIP] Observation: Larger roofs need more air terminals and longer conductors")

# ============================================================================
# EXPERIMENT 3: Copper vs Aluminum pricing
# ============================================================================
print("\n[EXPERIMENT 3] Material Cost Comparison")
print("-" * 70)

copper_prices = [
    PriceItem(code="AT-C", name="Air Terminal - Copper", material_type="Copper",
              unit="ea", unit_price=45.00, labor_rate=15.00),
    PriceItem(code="COND-C", name="Conductor - Copper", material_type="Copper",
              unit="ft", unit_price=3.50, labor_rate=2.00),
    PriceItem(code="GR-C", name="Ground Rod - Copper", material_type="Copper",
              unit="ea", unit_price=65.00, labor_rate=50.00),
    PriceItem(code="CLAMP-C", name="Clamp", unit="ea", unit_price=8.00, labor_rate=5.00),
]

# Aluminum is typically 30-40% cheaper
aluminum_prices = [
    PriceItem(code="AT-A", name="Air Terminal - Aluminum", material_type="Aluminum",
              unit="ea", unit_price=30.00, labor_rate=15.00),  # 33% cheaper
    PriceItem(code="COND-A", name="Conductor - Aluminum", material_type="Aluminum",
              unit="ft", unit_price=2.30, labor_rate=2.00),  # 34% cheaper
    PriceItem(code="GR-A", name="Ground Rod - Aluminum", material_type="Aluminum",
              unit="ea", unit_price=45.00, labor_rate=50.00),  # 31% cheaper
    PriceItem(code="CLAMP-A", name="Clamp", unit="ea", unit_price=5.50, labor_rate=5.00),  # 31% cheaper
]

test_project = {
    "project_name": "Material Comparison",
    "building_height_ft": 40.0,
    "roof_area_sqft": 5000.0,
    "num_corners": 4,
    "perimeter_ft": 280.0,
}

copper_calc = BidCalculator(copper_prices, "UL 96A")
copper_bid = copper_calc.calculate_bid({**test_project, "preferred_material": "copper"})

aluminum_calc = BidCalculator(aluminum_prices, "UL 96A")
aluminum_bid = aluminum_calc.calculate_bid({**test_project, "preferred_material": "aluminum"})

print(f"  Copper system:    ${copper_bid.final_bid_amount:>10,.2f}")
print(f"  Aluminum system:  ${aluminum_bid.final_bid_amount:>10,.2f}")
print(f"  Savings:          ${copper_bid.final_bid_amount - aluminum_bid.final_bid_amount:>10,.2f}")
print(f"  Percent savings:  {((copper_bid.final_bid_amount - aluminum_bid.final_bid_amount) / copper_bid.final_bid_amount * 100):.1f}%")

print("\n[TIP] Observation: Material choice significantly impacts bid amount")

# ============================================================================
# EXPERIMENT 4: UL 96A vs NFPA 780 comparison
# ============================================================================
print("\n[EXPERIMENT 4] Compliance Code Comparison")
print("-" * 70)

test_building = {
    "building_height_ft": 45.0,
    "roof_area_sqft": 6000.0,
    "num_corners": 4,
    "perimeter_ft": 310.0,
    "num_downleads": 2,
    "soil_type": "normal"
}

ul96a_result = UL96ACompliance.check_compliance(test_building)
nfpa780_result = NFPA780Compliance.check_compliance(test_building)

print("Testing 45 ft tall, 6000 sqft building:")
print()
print(f"  {'Item':<25} {'UL 96A':>10} {'NFPA 780':>10} {'Diff':>10}")
print("-" * 58)

at_ul = ul96a_result['air_terminals']['total']
at_nf = nfpa780_result['air_terminals']['total']
print(f"  {'Air Terminals':<25} {at_ul:>10} {at_nf:>10} {abs(at_ul - at_nf):>10}")

cond_ul = ul96a_result['conductors']['total_length_ft']
cond_nf = nfpa780_result['conductors']['total_length_ft']
print(f"  {'Conductor (ft)':<25} {cond_ul:>10.1f} {cond_nf:>10.1f} {abs(cond_ul - cond_nf):>10.1f}")

gr_ul = ul96a_result['grounding']['total_rods']
gr_nf = nfpa780_result['grounding']['total_rods']
print(f"  {'Ground Rods':<25} {gr_ul:>10} {gr_nf:>10} {abs(gr_ul - gr_nf):>10}")

print("\n[TIP] Observation: NFPA 780 allows wider spacing (25 ft vs 20 ft)")

# ============================================================================
# EXPERIMENT 5: Soil type impact on grounding
# ============================================================================
print("\n[EXPERIMENT 5] Soil Type Impact on Grounding")
print("-" * 70)

soil_types = ["normal", "rocky", "sandy"]

print("Testing same building with different soil conditions:")
print()

for soil in soil_types:
    test_project = {
        "building_height_ft": 30.0,
        "roof_area_sqft": 4000.0,
        "num_corners": 4,
        "perimeter_ft": 250.0,
        "num_downleads": 2,
        "soil_type": soil
    }

    result = UL96ACompliance.check_compliance(test_project)
    rods = result['grounding']['total_rods']

    print(f"  {soil.capitalize():<10} soil: {rods} ground rods needed")

print("\n[TIP] Observation: Rocky soil requires more ground rods for proper grounding")

# ============================================================================
# EXPERIMENT 6: Cost breakdown by section
# ============================================================================
print("\n[EXPERIMENT 6] Understanding Cost Distribution")
print("-" * 70)

typical_project = {
    "project_name": "Cost Analysis",
    "building_height_ft": 35.0,
    "roof_area_sqft": 5000.0,
    "num_corners": 4,
    "perimeter_ft": 280.0,
    "preferred_material": "copper"
}

calc = BidCalculator(prices, "UL 96A")
bid = calc.calculate_bid(typical_project)

print(f"Project: {typical_project['building_height_ft']} ft tall, {typical_project['roof_area_sqft']} sqft")
print()
print(f"{'Section':<30} {'Material':>12} {'Labor':>12} {'Total':>12} {'%':>8}")
print("-" * 76)

for section in bid.sections:
    pct = (section.section_total / bid.subtotal) * 100
    print(f"{section.name:<30} ${section.total_material:>10,.2f} ${section.total_labor:>10,.2f} ${section.section_total:>10,.2f} {pct:>6.1f}%")

print("-" * 76)
print(f"{'SUBTOTAL':<30} ${bid.subtotal_material:>10,.2f} ${bid.subtotal_labor:>10,.2f} ${bid.subtotal:>10,.2f} {'100.0':>6}%")
print()
print(f"Markup (Mat: 15%, Lab: 20%):  ${bid.total_with_markup - bid.subtotal:>10,.2f}")
print(f"Overhead (10%) + Profit (10%): ${bid.final_bid_amount - bid.total_with_markup:>10,.2f}")
print(f"{'FINAL BID AMOUNT':<30} ${bid.final_bid_amount:>33,.2f}")

print("\n[TIP] Observation: Conductors typically make up 60-70% of project cost")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 70)
print("  Experiment Complete!")
print("=" * 70)

print("\n[NOTE] Things to Try:")
print("  1. Change the building heights in Experiment 1")
print("  2. Change the roof areas in Experiment 2")
print("  3. Modify material prices in Experiment 3")
print("  4. Add your own experiment!")
print()
print("[TIP] Pro Tip: Copy this file and make your own experiments:")
print("   cp test_experiments.py my_experiments.py")
print("   Then edit my_experiments.py with your own scenarios!")
