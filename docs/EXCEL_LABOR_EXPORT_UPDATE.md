# Excel Export - Labor Breakdown Enhancement

## Update Summary

The Excel export has been enhanced to show detailed worker information in the "Final Bid" tab.

## What Changed

### Before
The Final Bid tab showed only:
```
Subtotal (Material): $5,000.00
Subtotal (Labor): $3,346.00
Subtotal: $8,346.00
```

### After
The Final Bid tab now shows:
```
Subtotal (Material): $5,000.00

Labor Breakdown:
  Worker          Wage/Hour    Hours    Total Cost
  John Smith      $35.00       40.0     $1,400.00
  Jane Doe        $28.00       32.0     $896.00
  Bob Johnson     $42.00       25.0     $1,050.00
  TOTAL LABOR:    3 worker(s)  97.0     $3,346.00

Subtotal: $8,346.00
```

## Implementation Details

### Files Modified

1. **`src/exporters/excel_export.py`**
   - Updated `export_bid()` method to accept optional `workers` parameter
   - Enhanced `_create_final_bid_sheet()` to show detailed worker breakdown
   - Added formatted table with worker names, wages, hours, and costs
   - Shows total workers count and total hours

2. **`src/gui/main_window.py`**
   - Updated Excel export call to pass `self.workers` data
   - Worker information now flows from GUI to Excel export

### Excel Layout

The labor breakdown section includes:
- **Header row**: "Labor Breakdown:" (bold)
- **Column headers**: Worker | Wage/Hour | Hours | Total Cost (gray background)
- **Worker rows**: One row per worker with all details
- **Total row**: Summary with worker count, total hours, and total cost (highlighted)

### Formatting
- Currency values formatted as `$#,##0.00`
- Hours formatted as `0.0` (one decimal)
- Total row has bold font and gray background
- Column widths adjusted for readability

## Example Output

For a project with 3 workers:

| Worker | Wage/Hour | Hours | Total Cost |
|--------|-----------|-------|------------|
| John Smith | $35.00 | 40.0 | $1,400.00 |
| Jane Doe | $28.00 | 32.0 | $896.00 |
| Bob Johnson | $42.00 | 25.0 | $1,050.00 |
| **TOTAL LABOR:** | **3 worker(s)** | **97.0** | **$3,346.00** |

## Benefits

✓ **Transparency**: Client can see exactly who worked and for how long
✓ **Verification**: Easy to verify labor costs are calculated correctly
✓ **Professional**: Shows detailed breakdown like professional contractors
✓ **Flexibility**: Each worker's rate and hours clearly displayed
✓ **Audit Trail**: Complete record of labor allocation

## Testing

✓ Tested with 1 worker - displays correctly
✓ Tested with 3 workers - all shown with proper formatting
✓ Tested with different wage rates - currency formatting correct
✓ Tested with decimal hours - displays with one decimal place
✓ Total calculations verified - matches sum of individual workers

## Usage

No changes needed in workflow. When you export to Excel:

1. Set up workers in "Labor & Crew Settings" dialog
2. Calculate bid as normal
3. Export to Excel
4. Open "Final Bid" tab
5. See detailed worker breakdown automatically included

## Backward Compatibility

If no worker data is provided (shouldn't happen in normal use), the system falls back to showing:
```
Subtotal (Labor): $X,XXX.XX
```

This ensures the export still works even if worker data is missing.

---

*Updated: 2026-01-14*
*Status: Tested and Working*

