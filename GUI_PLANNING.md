# GUI Planning Document - LightningBid System

## Application Requirements Analysis

### Core Features Needed:
1. **File Selection**
   - Excel pricing file picker
   - PDF specification file picker
   - Output directory selection

2. **Project Data Input**
   - Project name
   - Building dimensions (height, area, perimeter)
   - Number of corners
   - Material preferences (copper/aluminum)
   - Compliance standard (UL 96A / NFPA 780)
   - Soil type
   - Metal roof checkbox

3. **Data Display**
   - Extracted PDF data preview
   - Pricing catalog table
   - Bid breakdown table (sections, items, costs)
   - Cost summary (material, labor, markup, total)

4. **Actions**
   - Parse PDF button
   - Load Excel button
   - Calculate Bid button
   - Export Excel button
   - Export PDF button
   - Preview bid before export

5. **Settings**
   - Contractor information
   - Markup percentages
   - Default paths

---

## GUI Framework Comparison

### 1. **Flet** ⭐ RECOMMENDED FOR QUICK START
**Stack:** Python + Flet (Flutter-based)

**Pros:**
- ✅ Modern, beautiful UI out of the box
- ✅ Fast development (similar to web development)
- ✅ Cross-platform (Windows, Mac, Linux, Web, Mobile)
- ✅ Great for forms and tables
- ✅ Single executable deployment
- ✅ Active development, good documentation
- ✅ Easy to learn if you know web concepts

**Cons:**
- ❌ Newer framework (less Stack Overflow answers)
- ❌ Larger file size (~50MB executable)
- ❌ Less mature ecosystem

**Code Example:**
```python
import flet as ft

def main(page: ft.Page):
    page.title = "LightningBid"
    
    # File picker
    excel_file = ft.FilePicker()
    pdf_file = ft.FilePicker()
    
    # Input fields
    project_name = ft.TextField(label="Project Name")
    height = ft.TextField(label="Height (ft)", type=ft.TextFieldType.NUMBER)
    
    # Table for bid items
    bid_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Item")),
            ft.DataColumn(ft.Text("Quantity")),
            ft.DataColumn(ft.Text("Cost")),
        ],
        rows=[]
    )
    
    # Buttons
    calculate_btn = ft.ElevatedButton("Calculate Bid", on_click=calculate)
    
    page.add(
        ft.Row([excel_file, pdf_file]),
        project_name,
        height,
        bid_table,
        calculate_btn
    )

ft.app(target=main)
```

**Installation:**
```bash
pip install flet
```

**Deployment:**
```bash
flet build windows  # Creates .exe
```

---

### 2. **PyQt6 / PySide6** ⭐ RECOMMENDED FOR PROFESSIONAL APP
**Stack:** Python + PyQt6/PySide6 (Qt framework)

**Pros:**
- ✅ Most professional-looking desktop apps
- ✅ Extensive widget library
- ✅ Excellent documentation
- ✅ Mature, stable framework
- ✅ Native look and feel
- ✅ Great for complex UIs
- ✅ Designer tool (Qt Designer) for visual design

**Cons:**
- ❌ Steeper learning curve
- ❌ Larger install size
- ❌ PyQt6 requires commercial license for commercial use (PySide6 is free)

**Code Example:**
```python
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                                QVBoxLayout, QPushButton, QLineEdit, 
                                QTableWidget, QFileDialog)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LightningBid")
        
        # Central widget
        widget = QWidget()
        layout = QVBoxLayout()
        
        # File buttons
        excel_btn = QPushButton("Load Excel Pricing")
        excel_btn.clicked.connect(self.load_excel)
        
        # Input fields
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("Project Name")
        
        # Table
        self.bid_table = QTableWidget()
        
        layout.addWidget(excel_btn)
        layout.addWidget(self.project_name)
        layout.addWidget(self.bid_table)
        
        widget.setLayout(layout)
        self.setCentralWidget(widget)
    
    def load_excel(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        # Load file...

app = QApplication([])
window = MainWindow()
window.show()
app.exec()
```

**Installation:**
```bash
pip install PySide6  # Free, open-source
# OR
pip install PyQt6   # Commercial license needed for commercial apps
```

**Designer Tool:**
- Qt Designer (visual UI builder)
- Can design UI visually, then convert to Python

---

### 3. **CustomTkinter** (Modern Tkinter)
**Stack:** Python + CustomTkinter

**Pros:**
- ✅ Modern, dark-mode support
- ✅ Still simple (Tkinter-based)
- ✅ No extra dependencies (beyond CustomTkinter)
- ✅ Good for forms

**Cons:**
- ❌ Less mature
- ❌ Smaller community
- ❌ Limited advanced widgets

**Code Example:**
```python
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("LightningBid")

# Modern-looking widgets
project_name = ctk.CTkEntry(app, placeholder_text="Project Name")
calculate_btn = ctk.CTkButton(app, text="Calculate Bid")
```

**Installation:**
```bash
pip install customtkinter
```

---

### 4. **Web-Based (Flask/FastAPI)**
**Stack:** Python + Flask/FastAPI + HTML/CSS/JavaScript

**Pros:**
- ✅ Accessible from any device
- ✅ Modern web UI (React, Vue, etc.)
- ✅ Easy to share (just send URL)
- ✅ Familiar technologies

**Cons:**
- ❌ Requires server/running process
- ❌ More complex deployment
- ❌ Need to learn web technologies
- ❌ File handling more complex

**Best For:** Multi-user, remote access scenarios

---

## Recommendation Matrix

### For Your Use Case (Business Desktop App):

| Framework | Speed to Build | Professional Look | Learning Curve | Best For |
|-----------|----------------|-------------------|----------------|----------|
| **Flet** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Quick modern app |
| **PyQt6** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | Professional desktop |
| **CustomTkinter** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | Simple modern app |
| **Tkinter** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | Quick prototype |
| **Web** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | Multi-user access |

---

## My Recommendation: **Start with Flet**

### Why Flet?
1. **Fastest to get a working GUI** - You can have a basic UI in hours
2. **Modern look** - Professional appearance without much effort
3. **Perfect for your needs** - Forms, tables, file pickers are all easy
4. **Easy deployment** - Single executable file
5. **Good documentation** - Easy to learn

### Migration Path:
- **Phase 1:** Build MVP with Flet (1-2 weeks)
- **Phase 2:** If you need more advanced features, migrate to PyQt6
- **Phase 3:** If you need web access, add Flask backend

---

## Suggested GUI Layout

### Main Window Structure:

```
┌─────────────────────────────────────────────────────┐
│  LightningBid - Lightning Protection Bidding System │
├─────────────────────────────────────────────────────┤
│                                                       │
│  [File Selection Section]                           │
│  ┌─────────────────────────────────────────────┐   │
│  │ Excel Pricing: [Browse...] [file.xlsx]      │   │
│  │ PDF Specs:    [Browse...] [spec.pdf]        │   │
│  └─────────────────────────────────────────────┘   │
│                                                       │
│  [Project Information]                               │
│  ┌─────────────────────────────────────────────┐   │
│  │ Project Name: [________________]             │   │
│  │ Height (ft):  [____]  Area (sqft): [____]   │   │
│  │ Material:     [Copper ▼]  Standard: [UL96A▼]│   │
│  └─────────────────────────────────────────────┘   │
│                                                       │
│  [Actions]                                           │
│  [Parse PDF] [Load Excel] [Calculate Bid]          │
│                                                       │
│  [Bid Preview Table]                                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ Section    │ Items │ Material │ Labor │ Total│   │
│  ├────────────┼───────┼──────────┼───────┼──────┤   │
│  │ Air Terms  │   28  │ $1,260  │ $420  │ $1,680│   │
│  │ Conductors │  484  │ $1,694  │ $968  │ $2,662│   │
│  └─────────────────────────────────────────────┘   │
│                                                       │
│  [Summary]                                           │
│  Subtotal: $4,342                                    │
│  Markup:    $739                                     │
│  Total:     $5,081                                   │
│                                                       │
│  [Export] [Export Excel] [Export PDF]                │
└─────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Basic GUI (Week 1)
- File pickers for Excel and PDF
- Basic input fields for project data
- Calculate button
- Simple text output of bid

### Phase 2: Enhanced UI (Week 2)
- Table display for bid items
- Preview extracted PDF data
- Settings panel for contractor info
- Progress indicators

### Phase 3: Polish (Week 3)
- Better styling
- Error handling UI
- Save/load project configurations
- Help/documentation

---

## Next Steps

1. **Choose Framework:** I recommend Flet for quick start
2. **Create GUI Branch:** `git checkout -b feature/gui`
3. **Build MVP:** Start with file pickers and basic form
4. **Integrate:** Connect GUI to existing `src/main.py` logic
5. **Test:** Get feedback from your uncle
6. **Iterate:** Add features based on usage

---

## Questions to Consider

1. **Who will use it?**
   - Just you? → Desktop app (Flet/PyQt)
   - Multiple people? → Web app (Flask)
   - Mobile access needed? → Flet (supports mobile)

2. **Deployment needs?**
   - Single computer? → Desktop app
   - Multiple computers? → Web app or packaged executable

3. **Timeline?**
   - Need it fast? → Flet
   - Can take time? → PyQt6 (more professional)

4. **Technical comfort?**
   - New to GUIs? → Flet or CustomTkinter
   - Experienced? → PyQt6

---

## Resources

### Flet:
- Docs: https://flet.dev/docs/
- Examples: https://flet.dev/gallery/
- GitHub: https://github.com/flet-dev/flet

### PyQt6:
- Docs: https://www.riverbankcomputing.com/static/Docs/PyQt6/
- Tutorial: https://www.pythonguis.com/tutorials/
- Designer: https://build-system.fman.io/qt-designer-download

### CustomTkinter:
- Docs: https://customtkinter.tomschimansky.com/
- GitHub: https://github.com/TomSchimansky/CustomTkinter

---

## Final Recommendation

**Start with Flet** - You can have a working GUI in a weekend, and it's easy to migrate to PyQt6 later if needed.

Would you like me to create a basic Flet GUI skeleton to get you started?

