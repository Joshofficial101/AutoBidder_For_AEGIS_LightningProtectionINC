# Flet GUI Quick Start Guide

## ✅ What's Been Set Up

I've created a complete Flet GUI for your LightningBid system! Here's what you have:

### Files Created:
- `src/gui/__init__.py` - GUI module initialization
- `src/gui/main_window.py` - Main GUI window with all functionality
- `src/gui/run_gui.py` - Entry point to run the GUI
- `requirements.txt` - Updated with Flet dependency

### Features Included:
✅ File pickers for Excel and PDF  
✅ Project information input form  
✅ PDF parsing with auto-fill  
✅ Excel pricing loading  
✅ Bid calculation  
✅ Bid results display (table + summary)  
✅ Export to Excel and PDF  
✅ Progress indicators  
✅ Error handling with notifications  

---

## 🚀 How to Run the GUI

### Step 1: Install Flet
```bash
pip install flet
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### Step 2: Run the GUI
```bash
python -m src.gui.run_gui
```

Or directly:
```bash
python src/gui/run_gui.py
```

### Step 3: Use the GUI
1. **Select Excel File** - Click "Select Excel Pricing File" button
2. **Select PDF File** - Click "Select PDF Specification" button (optional)
3. **Parse PDF** - Click "Parse PDF" to auto-fill project data
4. **Load Excel** - Click "Load Excel" to load pricing
5. **Enter/Edit Project Info** - Fill in any missing fields
6. **Calculate Bid** - Click "Calculate Bid" button
7. **View Results** - See bid breakdown in table
8. **Export** - Click "Export Excel" or "Export PDF"

---

## 📋 GUI Workflow

```
1. Select Files
   ├── Excel Pricing File
   └── PDF Specification (optional)

2. Parse PDF (optional)
   └── Auto-fills project data

3. Load Excel
   └── Loads pricing catalog

4. Enter Project Info
   ├── Project Name
   ├── Building Dimensions
   ├── Material Preferences
   └── Compliance Standard

5. Calculate Bid
   └── Generates bid with costs

6. View Results
   ├── Bid Summary
   └── Section Breakdown Table

7. Export
   ├── Excel Bid Sheet
   └── PDF Submittal
```

---

## 🎨 GUI Layout

```
┌─────────────────────────────────────────────────────┐
│  LightningBid - Lightning Protection Bidding System │
├─────────────────────────────────────────────────────┤
│                                                       │
│  [File Selection]                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ [Select Excel] [Select PDF]                  │   │
│  └─────────────────────────────────────────────┘   │
│                                                       │
│  [Project Information]                               │
│  ┌─────────────────────────────────────────────┐   │
│  │ Project Name: [____________]                  │   │
│  │ Height: [__] Area: [__] Perimeter: [__]      │   │
│  │ Material: [Copper ▼] Standard: [UL 96A ▼]    │   │
│  └─────────────────────────────────────────────┘   │
│                                                       │
│  [Actions]                                           │
│  [Parse PDF] [Load Excel] [Calculate Bid]          │
│                                                       │
│  [Bid Results]                                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ Project: Sample Office Building              │   │
│  │ Subtotal: $3,818.00                          │   │
│  │ FINAL BID: $5,349.36                         │   │
│  │                                               │   │
│  │ [Section Breakdown Table]                   │   │
│  │                                               │   │
│  │ [Export Excel] [Export PDF]                  │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 🔧 Customization

### Change Window Size
Edit `src/gui/main_window.py`, line ~30:
```python
self.page.window.width = 1200  # Change width
self.page.window.height = 800  # Change height
```

### Change Theme
Edit `src/gui/main_window.py`, line ~29:
```python
self.page.theme_mode = ft.ThemeMode.DARK  # or LIGHT
```

### Change Contractor Info
Edit `src/gui/main_window.py`, in `_export_pdf` method:
```python
pdf_exporter = PDFSubmittalExporter(
    contractor_name="Your Company Name",
    contractor_info={
        "address": "Your Address",
        "phone": "Your Phone",
        "email": "Your Email",
        "license": "Your License"
    }
)
```

---

## 🗄️ Adding Database Later

The GUI is designed to be **database-agnostic**. When you're ready to add SQLite:

1. **No major refactoring needed** - The GUI code is separate from data storage
2. **Add database layer** - Create `src/database/` module (see `DATABASE_PLAN.md`)
3. **Update save methods** - Add database calls to save buttons
4. **Add load methods** - Add "Load Project" button that queries database

### Example: Adding Save to Database

In `src/gui/main_window.py`, add to `_calculate_bid` method:
```python
# After calculating bid, save to database
from src.database.db_manager import DatabaseManager
from src.database.project_dao import ProjectDAO
from src.database.bid_dao import BidDAO

db = DatabaseManager()
project_dao = ProjectDAO(db)
bid_dao = BidDAO(db)

# Save project
project_id = project_dao.create_project(self.project_data)

# Save bid
bid_id = bid_dao.save_bid(project_id, self.current_bid)
```

---

## 🐛 Troubleshooting

### "Module 'flet' not found"
```bash
pip install flet
```

### GUI doesn't open
- Check if Flet is installed: `pip list | grep flet`
- Try running: `python -m src.gui.run_gui`

### File pickers don't work
- Make sure you're clicking the buttons
- Check file permissions
- Try selecting files from `data/inputs/` folder

### Bid calculation fails
- Make sure Excel is loaded first
- Check that project data has required fields (height, area)
- Look at error message in snackbar (bottom of window)

---

## 📝 Next Steps

1. **Test the GUI** - Run it and try all features
2. **Customize** - Update contractor info, colors, etc.
3. **Add features** - Add more fields, validation, etc.
4. **Add database** - When ready, integrate SQLite (see `DATABASE_PLAN.md`)

---

## 💡 Tips

- **PDF parsing is optional** - You can manually enter all project data
- **Excel must be loaded** - Before calculating bid
- **Results update automatically** - After calculation
- **Exports go to** - `data/outputs/` folder

---

## 🎯 What's Ready for Database Integration

The GUI is structured so you can easily add:
- ✅ Save project button → Save to database
- ✅ Load project button → Load from database
- ✅ Project history list → Query database
- ✅ PDF storage → Save PDF paths to database
- ✅ Bid history → Save all bids to database

All the UI is ready - you just need to add the database calls!

---

Enjoy your new GUI! 🎉

