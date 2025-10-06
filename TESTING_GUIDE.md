# 🧪 Testing Guide for LightningBid

## Quick Tests You Just Ran

You just successfully ran `test_system.py` which tested:

✅ **Test 1**: Creating price items
✅ **Test 2**: UL 96A compliance calculations
✅ **Test 3**: Comparing UL 96A vs NFPA 780
✅ **Test 4**: Bid calculator
✅ **Test 5**: Price item search
✅ **Test 6**: Different building sizes
✅ **Test 7**: Cost breakdown analysis

**All tests passed!** This means the core system is working correctly.

---

## Types of Testing You Can Do

### 1. Component Testing (What You Just Did)

Test individual parts of the system in isolation.

**Run it:**
```bash
py test_system.py
```

**What it tests:**
- Data models (PriceItem, Bid, etc.)
- Compliance calculations
- Bid calculator logic
- Price searching

**When to use it:**
- After making changes to code
- To understand how components work
- To verify calculations are correct

### 2. Full System Testing

Run the complete end-to-end workflow.

**Run it:**
```bash
py -m src.main
```

**What it tests:**
- File loading (Excel, PDF)
- Complete bid generation
- Excel export
- PDF export

**Check the outputs:**
- `data/outputs/bid_*.xlsx` - Open in Excel
- `data/outputs/submittal_*.pdf` - Open in PDF reader

### 3. Manual Testing with Different Inputs

Modify `src/main.py` to test different scenarios.

#### Example: Test a Tall Building

In `main.py` around line 88, change:

```python
project_data = {
    "project_name": "Tall Tower Test",
    "building_height_ft": 100.0,  # Changed from 35
    "roof_area_sqft": 3000.0,     # Changed from 5000
    "num_corners": 4,
    "perimeter_ft": 220.0,
    "num_downleads": 4,            # Changed from 2 (taller = more paths)
    "soil_type": "rocky",          # Changed from normal
    "preferred_material": "copper"
}
```

Run: `py -m src.main`

**Expected Results:**
- More conductor length (taller building)
- More ground rods (rocky soil)
- Higher final bid

#### Example: Test NFPA 780

In `main.py` around line 104:

```python
compliance_code = "NFPA 780"  # Changed from "UL 96A"
```

Run: `py -m src.main`

**Expected Results:**
- Fewer air terminals (25 ft spacing vs 20 ft)
- Additional bonding items (if metal roof)
- Different compliance notes in PDF

### 4. Price Sensitivity Testing

Test how price changes affect the bid.

Create a test file:

```python
# price_test.py
from src.models.items import PriceItem
from src.calculator.bid_calc import BidCalculator

# Original prices
original_prices = [
    PriceItem(code="AT-001", name="Air Terminal", unit="ea", unit_price=45.00, labor_rate=15.00),
    PriceItem(code="COND-100", name="Conductor", unit="ft", unit_price=3.50, labor_rate=2.00),
    PriceItem(code="GR-10", name="Ground Rod", unit="ea", unit_price=65.00, labor_rate=50.00),
    PriceItem(code="CLAMP-01", name="Clamp", unit="ea", unit_price=8.00, labor_rate=5.00),
]

# 20% price increase
increased_prices = [
    PriceItem(code="AT-001", name="Air Terminal", unit="ea", unit_price=54.00, labor_rate=18.00),
    PriceItem(code="COND-100", name="Conductor", unit="ft", unit_price=4.20, labor_rate=2.40),
    PriceItem(code="GR-10", name="Ground Rod", unit="ea", unit_price=78.00, labor_rate=60.00),
    PriceItem(code="CLAMP-01", name="Clamp", unit="ea", unit_price=9.60, labor_rate=6.00),
]

project = {
    "project_name": "Price Test",
    "building_height_ft": 30.0,
    "roof_area_sqft": 4000.0,
    "num_corners": 4,
    "perimeter_ft": 250.0,
    "preferred_material": "copper"
}

calc1 = BidCalculator(original_prices, "UL 96A")
bid1 = calc1.calculate_bid(project)

calc2 = BidCalculator(increased_prices, "UL 96A")
bid2 = calc2.calculate_bid(project)

print(f"Original prices bid: ${bid1.final_bid_amount:,.2f}")
print(f"20% increased prices: ${bid2.final_bid_amount:,.2f}")
print(f"Actual increase: {((bid2.final_bid_amount / bid1.final_bid_amount) - 1) * 100:.1f}%")
print("(Note: Due to markup compounding, 20% price increase = ~20% final bid increase)")
```

Run: `py price_test.py`

### 5. Compliance Rule Validation

Verify that compliance calculations are correct.

Create a validation test:

```python
# validate_compliance.py
from src.compliance.ul96a import UL96ACompliance

# Test Case 1: Square building
print("Test Case 1: 100ft x 100ft building (10,000 sqft)")
print("-" * 50)

project1 = {
    "roof_area_sqft": 10000.0,
    "num_corners": 4,
    "perimeter_ft": 400.0,
    "building_height_ft": 30.0,
}

result1 = UL96ACompliance.check_compliance(project1)

print(f"Air terminals: {result1['air_terminals']['total']}")
print(f"Expected: ~4 corners + ~18 edges + ~16 field = ~38 total")
print()

# Manual calculation:
# Perimeter: 400 ft, minus corners leaves ~392 ft
# At 20 ft spacing: 392/20 = ~20 edge terminals
# Field: 10000/500 = 20, minus 4 corners = 16
# Total should be around 40

print("Test Case 2: Small building (50ft x 40ft = 2000 sqft)")
print("-" * 50)

project2 = {
    "roof_area_sqft": 2000.0,
    "num_corners": 4,
    "perimeter_ft": 180.0,
    "building_height_ft": 25.0,
}

result2 = UL96ACompliance.check_compliance(project2)

print(f"Air terminals: {result2['air_terminals']['total']}")
print(f"Expected: 4 corners + ~9 edges + ~0 field = ~13 total")
```

Run: `py validate_compliance.py`

### 6. Output Quality Testing

Check that generated files look professional.

**Manual Steps:**

1. Run the system: `py -m src.main`

2. Open the Excel file in `data/outputs/`
   - ✅ Check formulas are correct
   - ✅ Verify currency formatting
   - ✅ Look at all 3 sheets
   - ✅ Ensure no #DIV/0! errors

3. Open the PDF file in `data/outputs/`
   - ✅ Check cover page has project name
   - ✅ Verify compliance section is readable
   - ✅ Material list is complete
   - ✅ No text cutoff or formatting issues

**Expected Quality Checklist:**
- [ ] Numbers formatted as currency ($X,XXX.XX)
- [ ] Tables have borders and headers
- [ ] No calculation errors
- [ ] Professional appearance
- [ ] All sections present

### 7. Error Handling Testing

Test how the system handles problems.

#### Test 1: Missing Files

```bash
# Remove files from data/inputs temporarily
# Run: py -m src.main
# Should gracefully use demo data
```

Expected output:
```
[INFO] No PDF found - using sample project data
Using demo mode with sample pricing...
```

#### Test 2: Invalid Excel Format

The system already handles this - your Excel file triggers demo mode.

#### Test 3: Invalid Project Data

Create a test with bad data:

```python
# test_errors.py
from src.calculator.bid_calc import BidCalculator
from src.models.items import PriceItem

prices = [
    PriceItem(code="AT-001", name="Air Terminal", unit="ea", unit_price=45.00, labor_rate=15.00),
]

calc = BidCalculator(prices, "UL 96A")

# Missing required fields
bad_project = {
    "project_name": "Bad Test",
    # Missing building_height_ft
    # Missing roof_area_sqft
}

try:
    bid = calc.calculate_bid(bad_project)
    print("Should have failed!")
except Exception as e:
    print(f"Correctly caught error: {type(e).__name__}")
```

---

## Creating Your Own Tests

### Simple Test Template

```python
# my_test.py
"""
Test: [What you're testing]
Expected: [What should happen]
"""

# Import what you need
from src.models.items import PriceItem

# Setup test data
test_item = PriceItem(
    code="TEST",
    name="Test Item",
    unit_price=10.0
)

# Run test
print(f"Item price: ${test_item.unit_price}")

# Verify result
assert test_item.unit_price == 10.0, "Price should be $10"

print("✓ Test passed!")
```

### Tips for Writing Tests

1. **Test one thing at a time**
   - Don't test everything in one script
   - Easier to debug when something fails

2. **Use clear names**
   - `test_air_terminal_calculation.py` (good)
   - `test1.py` (bad - what does it test?)

3. **Print intermediate results**
   ```python
   print(f"DEBUG: quantity={qty}, price={price}")
   print(f"DEBUG: total should be {qty * price}")
   ```

4. **Compare expected vs actual**
   ```python
   expected = 100
   actual = calculation_result
   print(f"Expected: {expected}, Got: {actual}")
   if expected == actual:
       print("✓ Pass")
   else:
       print("✗ Fail")
   ```

---

## Understanding Test Results

### Test 6 Results Explained

When you ran `test_system.py`, Test 6 showed:

```
Small  (20ft, 1000sqft): $  4,070.18
Medium (40ft, 5000sqft): $  8,383.01
Large  (60ft, 10000sqft): $ 12,209.04
```

**Analysis:**
- Doubling size doesn't double cost (1000→2000 sqft ≠ 2× cost)
- Why? Some costs scale linearly (materials) but others don't (corners are fixed)
- Height matters more than area for conductors

**Try it yourself:**
- Modify Test 6 in `test_system.py`
- Add extra large: `{"name": "XL", "height": 80, "area": 15000}`
- See if cost continues scaling linearly

### Test 7 Results Explained

```
Material subtotal: $2,476.00
Labor subtotal:    $1,342.00
Material/Labor ratio: 1.85:1
```

**This means:**
- Material costs are ~65% of subtotal
- Labor costs are ~35% of subtotal
- This ratio depends on your labor rates

**Experiment:**
- In demo pricing, change `labor_rate` to `0.0`
- Rerun Test 4
- Labor subtotal should be $0

---

## Common Testing Scenarios

### Scenario 1: "I changed the code, does it still work?"

```bash
py test_system.py
```

All tests pass = You didn't break anything ✓

### Scenario 2: "How does changing X affect the bid?"

1. Run system once: `py -m src.main`
2. Note the final bid amount
3. Change X in `main.py`
4. Run again: `py -m src.main`
5. Compare bid amounts

### Scenario 3: "Is my compliance calculation correct?"

1. Open `src/compliance/ul96a.py`
2. Read the calculation in `calculate_air_terminals()`
3. Manually calculate for a test building
4. Run `test_system.py` and compare

Example:
- 100 ft × 100 ft building = 10,000 sqft
- Perimeter = 400 ft
- UL 96A: 20 ft max spacing
- Edges: 400 ft ÷ 20 ft = 20 terminals (rough)
- Corners: 4
- Field: ~10,000 ÷ 500 = 20
- Total: ~44 terminals

Does the code calculate similar numbers?

### Scenario 4: "Testing with real project data"

When you get a real project:

1. Create a test file:
```python
# test_margaritaville.py
project_data = {
    "project_name": "Margaritaville Project",
    "building_height_ft": 45.0,  # from actual drawings
    "roof_area_sqft": 7200.0,    # from actual drawings
    "num_corners": 6,            # from actual drawings (complex shape)
    "perimeter_ft": 380.0,
    "preferred_material": "copper"
}
```

2. Run through calculator
3. Compare with manual estimate
4. Adjust if needed

---

## Automated Testing (Advanced)

For when you want to get fancy:

```python
# test_suite.py
"""
Automated test suite - runs multiple tests automatically
"""

def test_price_item_creation():
    """Test that PriceItems can be created"""
    from src.models.items import PriceItem
    item = PriceItem(code="TEST", name="Test", unit_price=10.0)
    assert item.unit_price == 10.0
    return True

def test_compliance_calculation():
    """Test UL 96A calculations"""
    from src.compliance.ul96a import UL96ACompliance
    result = UL96ACompliance.calculate_air_terminals(1000.0, 4)
    assert result['total'] > 0
    return True

def test_bid_generation():
    """Test bid can be generated"""
    from src.calculator.bid_calc import BidCalculator
    from src.models.items import PriceItem

    prices = [PriceItem(code="T", name="Test", unit="ea", unit_price=10.0, labor_rate=5.0)]
    calc = BidCalculator(prices, "UL 96A")

    project = {
        "project_name": "Test",
        "building_height_ft": 30.0,
        "roof_area_sqft": 2000.0,
        "num_corners": 4,
        "perimeter_ft": 180.0,
        "preferred_material": "copper"
    }

    bid = calc.calculate_bid(project)
    assert bid.final_bid_amount > 0
    return True

# Run all tests
tests = [
    test_price_item_creation,
    test_compliance_calculation,
    test_bid_generation,
]

print("Running automated test suite...")
passed = 0
failed = 0

for test in tests:
    try:
        if test():
            print(f"✓ {test.__name__}")
            passed += 1
    except Exception as e:
        print(f"✗ {test.__name__}: {e}")
        failed += 1

print(f"\nResults: {passed} passed, {failed} failed")
```

---

## Quick Reference

**Run component tests:**
```bash
py test_system.py
```

**Run full system:**
```bash
py -m src.main
```

**Create custom test:**
```bash
# 1. Create test_whatever.py
# 2. Import modules you need
# 3. Write test code
# 4. Run: py test_whatever.py
```

**Check outputs:**
- Excel: `data/outputs/*.xlsx`
- PDF: `data/outputs/*.pdf`

---

## Summary

You now have **multiple ways to test**:

1. ✅ **Component tests** - Test individual parts
2. ✅ **Full system tests** - Test end-to-end
3. ✅ **Manual testing** - Change inputs, verify outputs
4. ✅ **Output validation** - Check Excel/PDF quality
5. ✅ **Custom tests** - Write your own test scripts

**Start with `test_system.py` whenever you change code to make sure nothing broke!**
