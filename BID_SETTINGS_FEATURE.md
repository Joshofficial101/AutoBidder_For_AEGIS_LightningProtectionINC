# Bid Settings Feature - Complete Implementation

## Overview

The "Bid Settings" button (formerly "Labor & Crew Settings") now provides comprehensive control over labor, pricing, and additional costs. All settings are configurable and automatically flow through to the final bid calculation and Excel export.

## Features Implemented

### 1. Configurable Pricing Percentages
- **Labor Markup (%)** - Markup applied to labor costs (default: 20%)
- **Overhead (%)** - Business overhead percentage (default: 10%)
- **Profit (%)** - Profit margin percentage (default: 10%)

### 2. Additional Flat Costs
- **Commission ($)** - Flat dollar amount for sales commission (default: $0)
- **Tools & Rental ($)** - Flat dollar amount for tools and equipment rental (default: $0)

### 3. Worker Management
- Individual worker names, hourly wages, and hours
- Dynamic worker addition/removal
- Real-time cost calculation per worker

## User Interface

### Button Renamed
- **Old**: "👷 Labor & Crew Settings"
- **New**: "⚙️ Bid Settings"

### Dialog Layout

```
┌─────────────────────────────────────────────────────────┐
│                    Bid Settings                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Configure your crew, pricing, and bid settings:        │
│  ─────────────────────────────────────────────────────  │
│                                                          │
│  Workers (set hours and wage for each):                 │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Worker 1    Hours: 40   Wage: $35/hr   $1,400  ❌ │ │
│  │ Worker 2    Hours: 32   Wage: $28/hr   $896    ❌ │ │
│  └────────────────────────────────────────────────────┘ │
│  [➕ Add Worker]                                        │
│                                                          │
│  ─────────────────────────────────────────────────────  │
│                                                          │
│  Pricing & Markup:                                      │
│  Labor Markup (%)   Overhead (%)   Profit (%)           │
│  [    20.0     ]   [   10.0   ]   [  10.0  ]           │
│                                                          │
│  Additional Costs:                                      │
│  Commission ($)     Tools & Rental ($)                  │
│  [             ]   [                ]                   │
│                                                          │
│                          [Cancel] [Save Settings]       │
└─────────────────────────────────────────────────────────┘
```

## Calculation Flow

### How Costs Are Applied

```
Base Costs:
  Material Cost:                              $7,356.82
  Labor Cost (from workers):                  $3,346.00
  ───────────────────────────────────────────
  Subtotal:                                   $10,702.82

Markups:
  Material Markup (0%):                       $0.00
  Labor Markup (25%):                         $836.50
  ───────────────────────────────────────────
  Total with Markup:                          $11,539.32

Additional Costs (% applied to original subtotal):
  Overhead (15%):                             $1,605.42
  Profit (12%):                               $1,284.34
  Commission (flat):                          $500.00
  Tools & Rental (flat):                      $750.00
  ───────────────────────────────────────────
  FINAL BID AMOUNT:                           $15,679.08
```

### Formula

```python
subtotal = material_cost + labor_cost

material_markup = material_cost × (material_markup_pct / 100)
labor_markup = labor_cost × (labor_markup_pct / 100)
total_with_markup = subtotal + material_markup + labor_markup

overhead = subtotal × (overhead_pct / 100)
profit = subtotal × (profit_pct / 100)

final_bid = total_with_markup + overhead + profit + commission + tools_rental
```

## Excel Export

The "Final Bid" tab now shows all pricing details:

```
Final Bid - Project Name
─────────────────────────────────────────

Subtotal (Material):                    $7,356.82

Labor Breakdown:
  Worker           Wage/Hour    Hours    Total Cost
  Lead Tech        $40.00       30.0     $1,200.00
  Helper           $25.00       20.0     $500.00
  TOTAL LABOR:     2 worker(s)  50.0     $1,700.00

Subtotal:                               $9,056.82

Material Markup (0.0%):                 $0.00
Labor Markup (25.0%):                   $425.00
Total with Markup:                      $9,481.82

Overhead (15.0%):                       $1,358.52
Profit (12.0%):                         $1,086.82
Commission:                             $500.00
Tools & Rental:                         $750.00

FINAL BID AMOUNT:                       $13,177.16
```

## Files Modified

### 1. `src/gui/main_window.py`
- Added instance variables for pricing settings
- Updated dialog to include pricing fields
- Renamed button to "Bid Settings"
- Added validation for all new fields
- Pass pricing settings to bid calculator

### 2. `src/models/bid.py`
- Added `commission_amount` field
- Added `tools_rental_amount` field
- Updated `final_bid_amount` calculation to include new costs
- Changed defaults to be configurable

### 3. `src/calculator/bid_calc.py`
- Updated `calculate_bid()` to accept pricing parameters
- Pass pricing settings when creating Bid object
- Updated docstring with new parameters

### 4. `src/exporters/excel_export.py`
- Fixed overhead/profit calculation (use subtotal, not marked-up amount)
- Added commission row (if > 0)
- Added tools & rental row (if > 0)
- Improved formatting and layout

## Validation Rules

### Percentages
- Labor Markup: 0% - 100%
- Overhead: 0% - 100%
- Profit: 0% - 100%

### Flat Amounts
- Commission: ≥ $0 (can be blank/0)
- Tools & Rental: ≥ $0 (can be blank/0)

### Workers
- Hours: 0 - 1,000 per worker
- Wage: $0 - $500/hour

## Default Values

When opening the dialog, fields are pre-filled with:
- **Labor Markup**: 20.0%
- **Overhead**: 10.0%
- **Profit**: 10.0%
- **Commission**: (blank/0)
- **Tools & Rental**: (blank/0)
- **Workers**: 1 worker at $25/hr for 40 hours

## Usage Example

### Scenario: Custom Bid with Commission

1. Click "⚙️ Bid Settings"
2. Set workers:
   - Lead Installer: $42/hr × 40hrs = $1,680
   - Helper: $22/hr × 32hrs = $704
3. Set pricing:
   - Labor Markup: 25%
   - Overhead: 15%
   - Profit: 12%
4. Add costs:
   - Commission: $500 (sales commission)
   - Tools & Rental: $750 (lift rental for 3 days)
5. Click "Save Settings"
6. Calculate bid
7. Export to Excel - all values appear in Final Bid tab

## Benefits

✓ **Flexibility**: Adjust pricing for different project types
✓ **Transparency**: All costs clearly shown in Excel export
✓ **Accuracy**: Include all real costs (commission, rentals)
✓ **Professional**: Detailed breakdown for clients
✓ **Easy to Use**: Pre-filled defaults, clear validation
✓ **Automatic**: Settings persist for session, apply to all bids

## Testing Results

✓ All percentages apply correctly
✓ Commission and tools/rental add to final bid
✓ Excel export shows all fields
✓ Validation prevents invalid values
✓ Recalculation works when settings change
✓ Default values load correctly

---

*Feature Complete: 2026-01-14*
*All Tests Passed*

