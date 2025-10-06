# 🚀 Quick Start Guide - LightningBid

## What Just Happened?

You successfully built and ran an **automated lightning protection bidding system**! Here's what it does:

1. ✅ Loads pricing data (from Excel or demo data)
2. ✅ Scans project specs (from PDFs)
3. ✅ Calculates compliance requirements (UL 96A or NFPA 780)
4. ✅ Generates professional bid packages (Excel + PDF)

## Your First Run

You just ran the system and it created:

📊 **Excel Bid Sheet** (`bid_Sample_Office_Building_-_Lightning_Protection.xlsx`)
- Sheet 1: Bill of Materials (detailed item list)
- Sheet 2: Cost Summary (totals by section)
- Sheet 3: Final Bid (with markup and profit)

📄 **PDF Submittal** (`submittal_Sample_Office_Building_-_Lightning_Protection.pdf`)
- Professional cover page
- Compliance certifications
- Material list

**Check them out in:** `data/outputs/`

## How to Run It Again

```bash
py -m src.main
```

That's it! Super simple.

## Next Steps

### 1. Understand the Code Flow

Open `src/main.py` and read through it. It's well-commented and shows the complete workflow:

```
Load Pricing → Parse Specs → Calculate Compliance → Generate Bid → Export Files
```

### 2. Customize Project Data

In `src/main.py` around line 88, you'll find:

```python
project_data = {
    "project_name": "Sample Office Building - Lightning Protection",
    "building_height_ft": 35.0,
    "roof_area_sqft": 5000.0,
    # ... more fields
}
```

**Try changing these values!** For example:
- Change `building_height_ft` to `50.0` (taller building)
- Change `roof_area_sqft` to `10000.0` (larger roof)
- Run again and see how the bid changes

### 3. Switch Compliance Codes

Around line 104 in `main.py`:

```python
compliance_code = "UL 96A"  # Change to "NFPA 780"
```

**Try switching to NFPA 780** and see how requirements differ!

### 4. Adjust Pricing

In `main.py` around line 72, the demo pricing is defined:

```python
PriceItem(code="AT-001", name="Air Terminal - Copper",
          unit="ea", unit_price=45.00, labor_rate=15.00)
```

**Try changing prices:**
- Increase `unit_price` to `60.00`
- Increase `labor_rate` to `20.00`
- Run again and watch the final bid amount change

### 5. Adjust Markup Percentages

In `src/models/bid.py` around line 25:

```python
material_markup_pct: float = 15.0  # 15% markup
labor_markup_pct: float = 20.0     # 20% markup
overhead_pct: float = 10.0
profit_pct: float = 10.0
```

Change these to match your business model!

## Understanding Key Files

### 📁 `src/models/` - Data Structures

- `items.py` - What a pricing item looks like (code, name, price)
- `project.py` - Project information (building details, requirements)
- `bid.py` - Complete bid with costs and sections

**Think of these as templates/blueprints for organizing data**

### 📁 `src/adapters/` - Input Parsers

- `excel_loader.py` - Reads Excel pricing sheets
- `pdf_loader.py` - Extracts info from PDF specs

**These are "translators" that convert Excel/PDF → Python objects**

### 📁 `src/compliance/` - Code Standards

- `ul96a.py` - UL 96A rules (20 ft spacing, etc.)
- `nfpa780.py` - NFPA 780 rules (25 ft spacing, bonding)

**These encode the "rulebooks" that determine what's needed**

### 📁 `src/calculator/` - Bid Engine

- `bid_calc.py` - The "brain" that maps requirements → pricing

**This is where compliance requirements meet pricing data**

### 📁 `src/exporters/` - Output Generators

- `excel_export.py` - Creates formatted Excel workbooks
- `pdf_export.py` - Creates professional PDFs

**These turn bid data into beautiful documents**

## Common Customizations

### Change Contractor Info

In `main.py` around line 127:

```python
pdf_exporter = PDFSubmittalExporter(
    contractor_name="ABC Lightning Protection Co.",  # Your company name
    contractor_info={
        "address": "123 Main St, Your City, ST 12345",  # Your address
        "phone": "(555) 123-4567",  # Your phone
        "email": "info@abclightning.com",  # Your email
        "license": "LP-12345"  # Your license number
    }
)
```

**Update this with your real company info!**

### Add More Materials to Demo Catalog

In `main.py` around line 72, add more items:

```python
PriceItem(code="SPLICE-01", name="Cable Splice",
          unit="ea", unit_price=12.50, labor_rate=8.00)
```

## Learning the Compliance Rules

### UL 96A Quick Summary

Open `src/compliance/ul96a.py` and read the comments:

```python
AIR_TERMINAL_MAX_SPACING = 20  # Air terminals ≤20 ft apart
GROUND_ROD_MIN_DEPTH = 10      # Ground rods ≥10 ft deep
```

**Key Rules:**
- Air terminals every 20 ft max on roof edges
- Minimum 2 down conductors (two-way path to ground)
- 8 inch minimum bend radius for conductors
- Ground rods at least 10 ft deep

### NFPA 780 Quick Summary

Open `src/compliance/nfpa780.py`:

```python
AIR_TERMINAL_MAX_SPACING = 25  # Slightly more lenient
```

**Key Differences from UL 96A:**
- Allows 25 ft spacing (vs 20 ft)
- Additional bonding requirements for metal objects
- Ground ring system recommended for large structures

## Troubleshooting

### "No module named 'pandas'"

You need to install dependencies:

```bash
py -m pip install -r requirements.txt
```

### Excel file not loading

The current Excel loader works with simple pricing sheets. Your actual Excel file (`ULP BID SHEET 2022.xlsx`) has a complex format.

**Two options:**
1. **Use demo mode** (what you're doing now) - fine for learning
2. **Customize the Excel loader** - edit `src/adapters/excel_loader.py` to match your Excel structure

### Want to see what's in the Excel?

Open it in Excel and look at which row the headers are on, what they're named, etc. Then update the loader accordingly.

## Practice Exercises

### Exercise 1: Change Building Size

Modify `project_data` in `main.py`:
- Building height: 60 ft
- Roof area: 8000 sqft
- Perimeter: 360 ft

Run the system. **How did the bid amount change?**

### Exercise 2: Price Increase

In the demo pricing, increase all prices by 20%. Run again.

**Question:** By how much did the final bid increase? (Hint: it's not 20% because of markup and profit!)

### Exercise 3: UL 96A vs NFPA 780

Run the system twice:
1. First with `compliance_code = "UL 96A"`
2. Then with `compliance_code = "NFPA 780"`

**Compare the outputs:** Which requires more air terminals? Why?

### Exercise 4: Add a New Material

Add a new PriceItem to the demo catalog:

```python
PriceItem(code="SURGE-01", name="Surge Protector",
          unit="ea", unit_price=125.00, labor_rate=30.00)
```

This won't automatically appear in bids yet - you'd need to add logic in `bid_calc.py` to include it. But you're learning the structure!

## What's Next?

### Phase 1: Master the Current System ✅ (You're here!)
- Understand the code flow
- Experiment with different inputs
- Customize for your needs

### Phase 2: Improve Excel Parsing
- Modify `excel_loader.py` to read your actual Excel files
- Handle multiple sheets
- Extract labor rates, material types

### Phase 3: Enhance PDF Parsing
- Extract actual building dimensions from PDFs
- Identify compliance requirements automatically
- Parse project-specific notes

### Phase 4: Add GUI
- Create simple interface (maybe with `tkinter`)
- Point-and-click file selection
- Preview bid before generating

### Phase 5: Advanced Features
- Historical bid database
- Cost trend analysis
- CAD/DWG drawing integration
- AI-powered quantity estimation

## Getting Help

### Read the Code Comments

Every file has detailed comments explaining what it does:

```python
"""
This is a docstring - it explains what the module/function does.
Read these first!
"""
```

### Understand One File at a Time

Don't try to understand everything at once. Pick one file and read it thoroughly:

1. Start with `src/models/items.py` (simple!)
2. Then `src/compliance/ul96a.py` (has calculations)
3. Then `src/calculator/bid_calc.py` (brings it together)

### Use Print Statements for Debugging

Add print statements to see what's happening:

```python
print(f"DEBUG: quantity = {quantity}, price = {price}")
```

### Run Small Tests

Create a test file to experiment:

```python
# test.py
from src.models.items import PriceItem

item = PriceItem(code="TEST", name="Test Item", unit_price=10.0)
print(f"Item: {item.name} costs ${item.unit_price}")
```

Run it: `py test.py`

## Key Takeaways

1. **Software is just data + transformations**
   - Input data (Excel, PDFs) → Process (calculations) → Output data (Excel, PDFs)

2. **Break complex problems into small pieces**
   - Each module does ONE thing well
   - Chain them together for complex workflows

3. **Code is meant to be read and understood**
   - Comments explain WHY
   - Variable names explain WHAT
   - Structure shows HOW

4. **It's OK to not understand everything**
   - Focus on the parts you need
   - Google unfamiliar concepts
   - Experiment and learn by doing

## Congratulations! 🎉

You've built a real, working software system that:
- Reads multiple file types
- Applies complex business rules
- Generates professional outputs
- Saves hours of manual work

**This is impressive work for a college senior!** Keep building, keep learning, and don't be afraid to break things and try again.

---

**Questions?** Read the main `README.md` or dive into the code comments!
