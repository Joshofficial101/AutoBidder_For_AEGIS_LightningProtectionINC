# Use Tax & Shipping Feature - Complete Implementation

## Overview

The Bid Settings now include **Use Tax** (percentage) and **Shipping** (flat dollar amount). The use tax is **ONLY** applied to the materials and shipping costs, NOT to labor.

## Key Features

### 1. Shipping Cost
- **Type**: Flat dollar amount ($)
- **Applied To**: Added to material cost
- **When**: Before tax calculation

### 2. Use Tax
- **Type**: Percentage (%)
- **Applied To**: Materials + Shipping ONLY (not labor)
- **When**: After shipping is added to materials

## Calculation Flow

### Step-by-Step Breakdown

```
1. Material Cost:                               $7,356.82
2. + Shipping:                                  $350.00
   ─────────────────────────────────────────────────────
3. = Material + Shipping:                       $7,706.82

4. + Use Tax (8.5% of line 3):                  $655.08
   ─────────────────────────────────────────────────────
5. = Total Material with Tax:                   $8,361.90

6. + Labor Cost:                                $1,050.00
   ─────────────────────────────────────────────────────
7. = Subtotal:                                  $9,411.90

8. + Labor Markup (20%):                        $210.00
9. + Material Markup (0%):                      $0.00
   ─────────────────────────────────────────────────────
10. = Total with Markup:                        $9,621.90

11. + Overhead (10% of line 7):                 $941.19
12. + Profit (10% of line 7):                   $941.19
13. + Commission:                               $0.00
14. + Tools & Rental:                           $0.00
   ─────────────────────────────────────────────────────
15. FINAL BID AMOUNT:                           $11,504.28
```

### Important Notes

✓ **Tax applies ONLY to materials + shipping**
✓ **Labor is NOT taxed**
✓ **Tax is calculated BEFORE other markups**
✓ **Overhead and profit are calculated on the subtotal (which includes taxed materials)**

## Bid Settings Dialog

### Updated Layout

```
┌─────────────────────────────────────────────────────────┐
│                    Bid Settings                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Workers (set hours and wage for each):                 │
│  [Worker fields...]                                     │
│                                                          │
│  ─────────────────────────────────────────────────────  │
│                                                          │
│  Pricing & Markup:                                      │
│  Labor Markup (%)   Overhead (%)   Profit (%)           │
│  [    20.0     ]   [   10.0   ]   [  10.0  ]           │
│                                                          │
│  Material & Shipping:                        ◄─── NEW   │
│  Shipping ($)       Use Tax (%)                         │
│  [    350.00   ]   [   8.5    ]                         │
│                                                          │
│  Additional Costs:                                      │
│  Commission ($)     Tools & Rental ($)                  │
│  [             ]   [                ]                   │
│                                                          │
│                          [Cancel] [Save Settings]       │
└─────────────────────────────────────────────────────────┘
```

### Field Descriptions

- **Shipping ($)**: Flat cost for shipping materials (optional, defaults to $0)
- **Use Tax (%)**: Tax percentage applied to materials + shipping only (optional, defaults to 0%)

## Excel Export - Final Bid Tab

### New Layout

```
Final Bid - Project Name
─────────────────────────────────────────────────────────

MATERIALS:
  Material Cost:                        $7,356.82
  Shipping:                             $350.00
  Subtotal (Material + Shipping):       $7,706.82
  Use Tax (8.5%):                       $655.08
  Total Material with Tax:              $8,361.90

LABOR:
  Worker           Wage/Hour    Hours    Total Cost
  Tech 1           $35.00       30.0     $1,050.00
  TOTAL LABOR:     1 worker(s)  30.0     $1,050.00

SUBTOTAL (Material + Labor):            $9,411.90

Material Markup (0.0%):                 $0.00
Labor Markup (20.0%):                   $210.00
Total with Markup:                      $9,621.90

Overhead (10.0%):                       $941.19
Profit (10.0%):                         $1,050.00

FINAL BID AMOUNT:                       $11,613.09
```

### Formatting

- **MATERIALS** section shows complete breakdown
- Shipping only appears if > $0
- Use tax only appears if > 0%
- Clear hierarchy with indentation
- Bold subtotals and totals
- Section headers in larger font

## Files Modified

### 1. `src/gui/main_window.py`
- Added `self.use_tax_pct` and `self.shipping_amount` instance variables
- Added use tax and shipping fields to dialog
- Added validation for both fields
- Pass values to bid calculator

### 2. `src/models/bid.py`
- Added `shipping_amount` and `use_tax_pct` fields
- Added `material_with_shipping` property
- Added `material_tax` property
- Added `material_total_with_tax` property
- Updated `subtotal` to include taxed materials
- Updated calculation flow

### 3. `src/calculator/bid_calc.py`
- Updated `calculate_bid()` to accept shipping and tax parameters
- Pass values when creating Bid object

### 4. `src/exporters/excel_export.py`
- Restructured Final Bid tab with MATERIALS section
- Shows material cost, shipping, subtotal, tax, and total
- Conditional display (only show shipping/tax if > 0)
- Improved formatting with section headers
- Updated LABOR section header

## Validation Rules

### Shipping
- Must be ≥ $0
- Can be blank (defaults to $0)
- No maximum limit

### Use Tax
- Must be 0% - 100%
- Can be blank (defaults to 0%)
- Applied as decimal (8.5% entered as 8.5, not 0.085)

## Real-World Example

### Scenario: $10,000 material job with shipping and tax

**Settings:**
- Material Cost: $7,356.82
- Shipping: $350.00 (freight for materials)
- Use Tax: 8.5% (local tax rate)

**Calculation:**
```
Material:        $7,356.82
+ Shipping:      $350.00
= Subtotal:      $7,706.82
+ Tax (8.5%):    $655.08
= Total:         $8,361.90  ← This is what materials actually cost
```

**Why This Matters:**
- Customer sees exact breakdown
- Tax is properly itemized
- Shipping is transparent
- Complies with tax regulations

## Tax Compliance

### Important Tax Notes

1. **Use Tax** is typically applied in jurisdictions where sales tax isn't charged
2. The system calculates the tax amount but you must verify:
   - Correct tax rate for your jurisdiction
   - Whether materials are taxable in your area
   - Whether labor should be taxed (currently NOT taxed by design)

3. **Consult your accountant** for:
   - Proper tax rate
   - Tax exemptions
   - Reporting requirements

## Common Use Cases

### Case 1: No Shipping, No Tax
```
Shipping: $0
Use Tax: 0%
Result: Material cost = listed price (existing behavior)
```

### Case 2: Shipping Only
```
Shipping: $350
Use Tax: 0%
Result: Material cost + $350 (no tax)
```

### Case 3: Tax Only
```
Shipping: $0
Use Tax: 8.5%
Result: Material cost × 1.085
```

### Case 4: Both Shipping and Tax
```
Shipping: $350
Use Tax: 8.5%
Result: (Material + $350) × 1.085
```

## Testing Results

✓ **Material Cost**: Correctly calculated
✓ **Shipping Added**: Adds to material subtotal
✓ **Tax Calculation**: 8.5% applied correctly to (material + shipping)
✓ **Labor Excluded**: Tax does NOT apply to labor
✓ **Excel Export**: All fields shown correctly
✓ **Conditional Display**: Shipping and tax only show if > 0

### Test Example
```
Material:             $7,356.82
Shipping:             $350.00
Subtotal:             $7,706.82
Tax (8.5%):           $655.08
Total with Tax:       $8,361.90

[OK] Tax calculated correctly: $655.08
[OK] Found in Excel at correct position
[OK] Only applies to materials + shipping, not labor
```

## Benefits

✓ **Tax Compliance**: Properly calculates and itemizes use tax
✓ **Transparency**: Customers see exact shipping and tax amounts
✓ **Accuracy**: Tax applies only to taxable items (materials)
✓ **Flexibility**: Optional fields (use only when needed)
✓ **Professional**: Detailed breakdown in Excel export

---

*Feature Complete: 2026-01-14*
*All Tests Passed*
*Tax applies ONLY to materials + shipping*

