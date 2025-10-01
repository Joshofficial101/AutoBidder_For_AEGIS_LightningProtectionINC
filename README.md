# ⚡ LightningBid - Lightning Protection Bidding Automation

Automated bidding and compliance tool for lightning protection contractors. Generates professional bid packages (Excel + PDF) from pricing sheets and project specifications.

## 🎯 What It Does

LightningBid automates the tedious process of creating lightning protection bids by:

1. **Loading pricing data** from your Excel bid sheets
2. **Parsing project specs** from PDF files
3. **Applying compliance rules** (UL 96A or NFPA 780)
4. **Calculating quantities** needed (air terminals, conductors, ground rods)
5. **Generating outputs**:
   - Professional Excel bid sheet with costs
   - PDF submittal package with compliance certifications

**Saves hours of manual work!**

## 📁 Project Structure

```
PythonProject/
├── data/
│   ├── inputs/          # Drop your Excel & PDF files here
│   └── outputs/         # Generated bids appear here
├── src/
│   ├── models/          # Data structures (Project, Bid, etc.)
│   ├── adapters/        # Input parsers (Excel, PDF)
│   ├── compliance/      # UL 96A & NFPA 780 rules
│   ├── calculator/      # Bid calculation engine
│   ├── exporters/       # Excel & PDF generators
│   └── main.py          # Main entry point
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Virtual environment (recommended)

### Installation

1. **Clone or download** this project

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Add your pricing files** to `data/inputs/`:
   - Excel pricing sheets (e.g., `ULP_BID_SHEET_2022.xlsx`)
   - Project spec PDFs (optional)

4. **Run the program**:
   ```bash
   python src/main.py
   ```

5. **Check outputs** in `data/outputs/`:
   - Excel bid sheet
   - PDF submittal package

## 📚 How It Works

### Step 1: Load Pricing Catalog

The system reads your Excel pricing sheet and extracts:
- Item codes (e.g., "AT-001")
- Descriptions (e.g., "Air Terminal - Copper")
- Unit prices
- Labor rates

**Smart column detection** - works with different spreadsheet formats!

### Step 2: Parse Specifications

Reads PDF specifications and extracts key requirements:
- Compliance standards (UL 96A, NFPA 780)
- Project requirements
- Special conditions

### Step 3: Apply Compliance Rules

Based on building dimensions, the system calculates:

**UL 96A Rules**:
- Air terminals: max 20 ft spacing
- Minimum 2 down conductors (two-way path)
- Ground rods: 10 ft minimum depth

**NFPA 780 Rules**:
- Air terminals: max 25 ft spacing
- Bonding requirements for metal objects
- Ground ring system (optional)

### Step 4: Calculate Bid

Maps requirements to pricing items:
- Quantities needed
- Material costs
- Labor costs
- Markup (configurable: 15% material, 20% labor)
- Overhead & profit

### Step 5: Generate Outputs

**Excel Bid Sheet** (3 tabs):
- Bill of Materials (itemized list)
- Cost Summary (by section)
- Final Bid (with markup)

**PDF Submittal Package**:
- Professional cover sheet
- Compliance certifications
- Material list

## 🔧 Configuration

### Adjusting Markup Percentages

In `src/calculator/bid_calc.py` or when creating a Bid:

```python
bid = Bid(
    project_name="My Project",
    material_markup_pct=15.0,  # Change these
    labor_markup_pct=20.0,     # Change these
    overhead_pct=10.0,
    profit_pct=10.0
)
```

### Selecting Compliance Code

In `src/main.py`:

```python
compliance_code = "UL 96A"  # or "NFPA 780"
```

### Customizing Contractor Info

In `src/main.py`, update the PDFSubmittalExporter:

```python
pdf_exporter = PDFSubmittalExporter(
    contractor_name="Your Company Name",
    contractor_info={
        "address": "Your Address",
        "phone": "Your Phone",
        "email": "your@email.com",
        "license": "Your License #"
    }
)
```

## 📖 Key Concepts Explained

### Data Models (src/models/)

**Think of these as "blueprints" for data structures**

- `PriceItem`: One item from pricing sheet (code, name, price)
- `Project`: Building info and requirements
- `Bid`: Complete bid with all costs and sections
- `BidLineItem`: One line in the bid (qty × price = cost)

### Adapters (src/adapters/)

**"Translators" that read external files**

- `excel_loader.py`: Reads Excel → Python objects
- `pdf_loader.py`: Reads PDF → Extract key terms

### Compliance (src/compliance/)

**"Rulebooks" that encode UL 96A and NFPA 780 standards**

- `ul96a.py`: UL 96A calculations (20 ft spacing, etc.)
- `nfpa780.py`: NFPA 780 calculations (25 ft spacing, bonding)

These modules know the rules and do the math for you!

### Calculator (src/calculator/)

**"The Brain" - maps requirements to pricing**

Takes compliance requirements (e.g., "need 15 air terminals") and finds matching items from your pricing sheet, calculates costs.

### Exporters (src/exporters/)

**"Output generators" - create final files**

- `excel_export.py`: Creates formatted Excel workbooks
- `pdf_export.py`: Creates professional PDF documents

## 🎓 Learning Resources

### Understanding the Code Flow

```
Excel File → Load Pricing → Price Catalog (List of PriceItems)
                                    ↓
Project Specs → Parse Requirements → Project Data (building dimensions)
                                    ↓
                            Compliance Engine (UL 96A/NFPA 780)
                                    ↓
                            Calculate Quantities Needed
                                    ↓
                            Match to Pricing Items
                                    ↓
                            Calculate Costs
                                    ↓
                            Generate Bid Object
                                    ↓
                        Export to Excel + PDF
```

### Key Python Concepts Used

1. **Pydantic Models**: Data validation and structure
   - Ensures data is correct type (no strings where numbers expected)
   - Auto-generates documentation

2. **Type Hints**: Makes code clearer
   ```python
   def calculate_cost(quantity: float, price: float) -> float:
       return quantity * price
   ```

3. **Dataclasses / Models**: Organize related data
   ```python
   class PriceItem(BaseModel):
       code: str
       price: float
   ```

4. **Pandas**: Excel file handling (powerful library for spreadsheets)

5. **ReportLab**: PDF generation

## 🛠️ Troubleshooting

### "No module named 'pydantic'"

Install requirements:
```bash
pip install -r requirements.txt
```

### "No Excel found in data/inputs"

The program will use demo data if no Excel file present. To use real data:
1. Copy your pricing Excel to `data/inputs/`
2. Run again

### Excel has different columns

The `excel_loader.py` tries to detect columns automatically. If it fails, check column names in your Excel and update the `col_map` in `excel_loader.py`.

## 🚧 Future Enhancements

- [ ] GUI interface (point-and-click instead of code)
- [ ] CAD/DWG drawing overlay
- [ ] Historical bid database
- [ ] AI-powered cost prediction
- [ ] Web version for team collaboration

## 📞 Need Help?

As you work through the code:
1. Read the docstrings (text in `"""triple quotes"""`)
2. Check variable names - they describe what they hold
3. Follow the flow in `main.py` to understand the pipeline

**Remember**: Programming is like following a recipe. Each function does one specific task, and they're chained together to make the final product!

## 📄 License

This is your project! Use it, modify it, and make it better.

---

**Built for lightning protection contractors who want to focus on the work, not the paperwork!** ⚡
