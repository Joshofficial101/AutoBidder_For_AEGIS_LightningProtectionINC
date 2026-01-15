# Cost Per Square Foot Warning Thresholds

## Overview

The system now uses **size-scaled warning thresholds** to account for the fact that larger buildings have lower cost per square foot (costs don't scale linearly with area).

## Threshold Scaling

### Small Buildings (< 10,000 sqft)
- **Low Warning**: < $1.50/sqft
- **High Warning**: > $8.00/sqft
- **Typical Range**: $1.50 - $8.00/sqft

### Medium Buildings (10,000 - 20,000 sqft)
- **Low Warning**: Scales from $1.50 to $0.60/sqft (proportional)
- **High Warning**: Scales from $8.00 to $5.00/sqft (proportional)

### Large Buildings (> 20,000 sqft)
- **Low Warning**: < $0.60/sqft
- **High Warning**: > $5.00/sqft
- **Typical Range**: $0.60 - $5.00/sqft

## Why Costs Scale Down

1. **Fixed Costs**: Ground rods, downleads, and connections don't multiply with size
2. **Perimeter Growth**: Conductors follow perimeter, which grows as √area
3. **Air Terminal Spacing**: Terminals are spaced by distance, not per square foot
4. **Economy of Scale**: Larger projects have better cost efficiency

## Examples

### Small Building (5,000 sqft)
- Bid: $9,500
- Cost/sqft: $1.90
- Status: ✅ Normal (within $1.50-$8.00 range)

### Medium Building (15,000 sqft)
- Bid: $18,000
- Cost/sqft: $1.20
- Threshold: ~$1.05-$6.50/sqft (interpolated)
- Status: ✅ Normal

### Large Building (38,500 sqft)
- Bid: $31,639
- Cost/sqft: $0.82
- Status: ✅ Normal (within $0.60-$5.00 range)
- **Previous**: Would trigger low warning
- **Now**: No warning - appropriate for size

### Very Large Building (50,000 sqft)
- Bid: $35,000
- Cost/sqft: $0.70
- Status: ✅ Normal (within $0.60-$5.00 range)

## Interpolation Formula

For buildings between 10,000 and 20,000 sqft:

```python
scale_factor = (roof_area - 10000) / 10000  # 0 to 1
low_threshold = 1.50 - (0.90 × scale_factor)  # 1.50 → 0.60
high_threshold = 8.0 - (3.0 × scale_factor)   # 8.0 → 5.0
```

### Example at 15,000 sqft (midpoint):
```
scale_factor = (15000 - 10000) / 10000 = 0.5
low_threshold = 1.50 - (0.90 × 0.5) = $1.05/sqft
high_threshold = 8.0 - (3.0 × 0.5) = $6.50/sqft
```

## When Warnings Appear

### Low Cost Warning
Appears when cost/sqft is below the threshold for building size:
```
⚠️ WARNING: Low cost/sqft - verify quantities 
(typical: $X.XX-$X.XX/sqft)
```

This suggests:
- Possible missing components
- Underestimated quantities
- Need to verify project scope

### High Cost Warning
Appears when cost/sqft exceeds the threshold:
```
⚠️ WARNING: High cost/sqft 
(typical for XX,XXX sqft: $X.XX-$X.XX/sqft)
```

This suggests:
- Possible overestimation
- Specialty items selected
- Complex project requirements
- Need to review item selection

## No Warning
When cost falls within the appropriate range for building size, no warning appears - the bid is considered reasonable.

