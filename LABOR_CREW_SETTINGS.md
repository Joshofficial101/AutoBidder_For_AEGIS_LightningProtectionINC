# Labor & Crew Settings

## Overview
The Lightning Protection Bidding System now includes an intuitive **Labor & Crew Settings** feature that allows you to configure your workforce and calculate accurate labor costs based on real workers, with individual hours and wages for each worker.

## Location
Click the **"👷 Labor & Crew Settings"** button in the Actions section of the main window.

## Features

### 1. Manage Your Crew
- **Add Workers**: Add as many workers as needed for the project
- **Remove Workers**: Remove workers you don't need (minimum 1 worker required)
- **Name Workers**: Give each worker a descriptive name (e.g., "Lead Electrician", "Apprentice")
- **Individual Hours**: Set different hours for each worker (they don't all work the same amount)
- **Individual Wages**: Set different hourly wages for each worker

### 2. Flexible Hours Per Worker
- Each worker has their own hours field
- Perfect for scenarios where workers work different amounts of time
- Lead might work 40 hours, helper might work 20 hours

### 3. Real-Time Cost Calculation
- See each worker's total cost displayed immediately (Hours × Wage)
- See overall project labor cost
- Automatic recalculation when settings change

## How to Use

### Step 1: Open Labor Settings
1. Click the **"👷 Labor & Crew Settings"** button
2. The Labor & Crew Settings dialog will appear

### Step 2: Add and Configure Workers
- **Default**: Starts with 1 worker at $25/hour, 40 hours
- **To Add Worker**: Click the "➕ Add Worker" button
- **To Set Hours**: Enter hours for each worker (0-1000 hours)
- **To Set Wage**: Enter the hourly wage for each worker ($0-$500/hr)
- **To Rename**: Change the worker name in the name field
- **See Total**: Each worker's total cost is displayed automatically
- **To Remove**: Click the trash icon (🗑️) next to the worker

### Step 3: Save Settings
- Click **"Save Settings"** to apply changes
- If a bid is already calculated, it will automatically recalculate with new labor costs

## Example Scenarios

### Example 1: Single Worker
```
Workers:
  - Worker 1: 40 hours × $30/hour = $1,200

Total Labor Cost: $1,200
```

### Example 2: Mixed Crew (Different Hours)
```
Workers:
  - Lead Electrician: 40 hours × $45/hour = $1,800
  - Electrician: 30 hours × $35/hour = $1,050
  - Apprentice: 20 hours × $20/hour = $400

Total Hours: 90
Total Labor Cost: $3,250
```

### Example 3: Large Project (Variable Time)
```
Workers:
  - Foreman: 80 hours × $50/hour = $4,000
  - Electrician 1: 80 hours × $40/hour = $3,200
  - Electrician 2: 60 hours × $40/hour = $2,400
  - Helper 1: 40 hours × $25/hour = $1,000
  - Helper 2: 40 hours × $25/hour = $1,000

Total Hours: 300
Total Labor Cost: $11,600
```

## How Labor Costs Are Applied

The system calculates labor costs as follows:

1. **Each Worker's Cost** = Worker Hours × Worker Wage
   - Example: Worker 1: 40 hours × $30/hour = $1,200
   - Example: Worker 2: 30 hours × $25/hour = $750

2. **Total Project Labor Cost** = Sum of all workers' individual costs
   - Example: $1,200 + $750 + $400 = $2,350

3. **Distribution**: The total labor cost is distributed across bid sections proportionally based on material costs in each section

## Input Validation

- **Hours**: Must be between 0 and 1,000 hours
- **Wages**: Must be between $0 and $500 per hour
- **Minimum Workers**: At least 1 worker is required
- All fields must contain valid numbers

## Tips for Accurate Estimates

1. **Consider Skill Levels**: Set appropriate wages for different skill levels
2. **Variable Hours**: Lead might work full time (40hrs), helpers might work part time (20hrs)
3. **Include Travel Time**: Factor in travel time in each worker's hours if needed
4. **Account for Complexity**: Add more hours for workers on difficult tasks
5. **Use Realistic Wages**: Base wages on your local market rates
6. **Overlapping vs Sequential**: Some workers work simultaneously, others at different times
7. **Update as Needed**: Recalculate anytime your crew or schedule changes

## Success Messages

When you save settings, you'll see:
```
Labor settings saved!
Workers: 3 | Total Hours: 90.0
Total Labor Cost: $3,250.00
```

When you calculate a bid with custom labor settings:
```
Bid calculated successfully!
Crew: 3 worker(s), 90.0 total hours
```

## Integration with Bid Calculation

- Labor settings are automatically applied to new bid calculations
- Existing bids are recalculated when settings change
- The system adjusts the standard labor estimates based on your crew configuration
- All labor costs in the final bid reflect your actual crew rates

## Benefits

✅ **Accurate Pricing**: Calculate labor based on your actual crew costs
✅ **Flexible**: Each worker can have different hours and wages
✅ **Transparent**: See each worker's total cost displayed in real-time
✅ **Realistic**: Accounts for workers working different amounts of time
✅ **Simple**: No complex multipliers—just workers, their hours, and wages
✅ **Professional**: Present bids based on your real operational costs

---

*This feature replaces abstract multipliers with real-world labor parameters for easier and more accurate bid preparation.*

