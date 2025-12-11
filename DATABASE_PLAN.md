# Database Integration Plan - LightningBid

## Overview

**Goal:** Add local database to save PDFs, project data, and bid history.

**Database Choice:** SQLite (perfect for local desktop apps)

---

## Why SQLite?

✅ **No server needed** - Single file database  
✅ **Built into Python** - No extra installation  
✅ **Works offline** - 100% local  
✅ **Fast** - Great for desktop apps  
✅ **Reliable** - Used by millions of apps  
✅ **Easy to backup** - Just copy the .db file  

---

## Database Schema Design

### Table 1: `projects`
Stores project information and metadata.

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    project_date TEXT,  -- ISO format: '2024-01-15'
    building_height_ft REAL,
    roof_area_sqft REAL,
    perimeter_ft REAL,
    num_corners INTEGER DEFAULT 4,
    soil_type TEXT DEFAULT 'normal',
    has_metal_roof INTEGER DEFAULT 0,  -- 0 = False, 1 = True
    preferred_material TEXT DEFAULT 'copper',
    compliance_standard TEXT DEFAULT 'UL 96A',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Table 2: `pdf_files`
Stores PDF specification files.

```sql
CREATE TABLE pdf_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,  -- Links to projects table
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,  -- Full path to PDF file
    file_size INTEGER,  -- Size in bytes
    uploaded_date TEXT DEFAULT CURRENT_TIMESTAMP,
    extracted_data TEXT,  -- JSON string of extracted data
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

### Table 3: `excel_files`
Stores Excel pricing files.

```sql
CREATE TABLE excel_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    uploaded_date TEXT DEFAULT CURRENT_TIMESTAMP,
    item_count INTEGER,  -- Number of pricing items loaded
    is_active INTEGER DEFAULT 1  -- 1 = current pricing, 0 = archived
);
```

### Table 4: `bids`
Stores generated bids.

```sql
CREATE TABLE bids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    excel_file_id INTEGER,  -- Which pricing file was used
    compliance_standard TEXT,
    subtotal_material REAL,
    subtotal_labor REAL,
    subtotal REAL,
    material_markup_pct REAL,
    labor_markup_pct REAL,
    overhead_pct REAL,
    profit_pct REAL,
    final_bid_amount REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (excel_file_id) REFERENCES excel_files(id)
);
```

### Table 5: `bid_items`
Stores individual line items from bids.

```sql
CREATE TABLE bid_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bid_id INTEGER NOT NULL,
    section_name TEXT,
    item_code TEXT,
    item_name TEXT,
    quantity REAL,
    unit_price REAL,
    material_cost REAL,
    labor_cost REAL,
    total_cost REAL,
    reason TEXT,
    FOREIGN KEY (bid_id) REFERENCES bids(id)
);
```

### Table 6: `output_files`
Stores generated output files (Excel/PDF exports).

```sql
CREATE TABLE output_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bid_id INTEGER NOT NULL,
    file_type TEXT,  -- 'excel' or 'pdf'
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bid_id) REFERENCES bids(id)
);
```

---

## Implementation Approach

### Option 1: Store PDF Paths (Recommended) ⭐
**Store file paths in database, keep PDFs in file system.**

**Pros:**
- ✅ Database stays small
- ✅ Easy to access PDFs
- ✅ Can move/backup files separately
- ✅ Standard approach

**How it works:**
- PDF saved to `data/uploads/projects/{project_id}/spec.pdf`
- Database stores: `file_path = "data/uploads/projects/1/spec.pdf"`
- App reads path from DB, opens file

### Option 2: Store PDFs as BLOB
**Store actual PDF binary data in database.**

**Pros:**
- ✅ Everything in one place
- ✅ Easy backup (just copy .db file)

**Cons:**
- ❌ Database gets very large
- ❌ Slower to access
- ❌ Harder to view PDFs outside app

**Not recommended** - Use Option 1 instead.

---

## Code Structure

### New Module: `src/database/`

```
src/database/
├── __init__.py
├── db_manager.py      # Database connection and setup
├── project_dao.py     # Project data access
├── pdf_dao.py         # PDF file management
├── bid_dao.py         # Bid storage and retrieval
└── models.py          # Database models (if using ORM)
```

---

## Example: Database Integration Code

### 1. Database Manager (`src/database/db_manager.py`)

```python
"""
Database manager for LightningBid.
Handles SQLite connection and table creation.
"""

import sqlite3
from pathlib import Path
from typing import Optional

class DatabaseManager:
    """Manages SQLite database connection and setup."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to database file. If None, uses default location.
        """
        if db_path is None:
            # Default: data/lightningbid.db
            db_path = Path(__file__).parent.parent.parent / "data" / "lightningbid.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
    
    def connect(self):
        """Connect to database."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Access columns by name
        return self.conn
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def initialize_tables(self):
        """Create all database tables if they don't exist."""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                project_date TEXT,
                building_height_ft REAL,
                roof_area_sqft REAL,
                perimeter_ft REAL,
                num_corners INTEGER DEFAULT 4,
                soil_type TEXT DEFAULT 'normal',
                has_metal_roof INTEGER DEFAULT 0,
                preferred_material TEXT DEFAULT 'copper',
                compliance_standard TEXT DEFAULT 'UL 96A',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # PDF files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdf_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                uploaded_date TEXT DEFAULT CURRENT_TIMESTAMP,
                extracted_data TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        
        # Excel files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS excel_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                uploaded_date TEXT DEFAULT CURRENT_TIMESTAMP,
                item_count INTEGER,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Bids table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                excel_file_id INTEGER,
                compliance_standard TEXT,
                subtotal_material REAL,
                subtotal_labor REAL,
                subtotal REAL,
                material_markup_pct REAL,
                labor_markup_pct REAL,
                overhead_pct REAL,
                profit_pct REAL,
                final_bid_amount REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (excel_file_id) REFERENCES excel_files(id)
            )
        """)
        
        # Bid items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bid_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bid_id INTEGER NOT NULL,
                section_name TEXT,
                item_code TEXT,
                item_name TEXT,
                quantity REAL,
                unit_price REAL,
                material_cost REAL,
                labor_cost REAL,
                total_cost REAL,
                reason TEXT,
                FOREIGN KEY (bid_id) REFERENCES bids(id)
            )
        """)
        
        # Output files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS output_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bid_id INTEGER NOT NULL,
                file_type TEXT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bid_id) REFERENCES bids(id)
            )
        """)
        
        conn.commit()
        print("✅ Database tables initialized")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
```

### 2. PDF Data Access (`src/database/pdf_dao.py`)

```python
"""
Data Access Object for PDF files.
"""

import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime

class PDFDAO:
    """Handles PDF file storage and retrieval."""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def save_pdf(self, project_id: int, pdf_path: Path, 
                 extracted_data: Optional[Dict[str, Any]] = None) -> int:
        """
        Save PDF file to database and copy to storage.
        
        Args:
            project_id: ID of associated project
            pdf_path: Path to source PDF file
            extracted_data: Extracted data from PDF parser
        
        Returns:
            ID of saved PDF record
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Create project storage directory
        storage_dir = Path(__file__).parent.parent.parent / "data" / "uploads" / f"project_{project_id}"
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy PDF to storage
        dest_path = storage_dir / pdf_path.name
        shutil.copy2(pdf_path, dest_path)
        
        # Prepare extracted data as JSON
        extracted_json = json.dumps(extracted_data) if extracted_data else None
        
        # Insert into database
        cursor.execute("""
            INSERT INTO pdf_files 
            (project_id, file_name, file_path, file_size, extracted_data)
            VALUES (?, ?, ?, ?, ?)
        """, (
            project_id,
            pdf_path.name,
            str(dest_path),
            dest_path.stat().st_size,
            extracted_json
        ))
        
        pdf_id = cursor.lastrowid
        conn.commit()
        return pdf_id
    
    def get_pdf(self, pdf_id: int) -> Optional[Dict]:
        """Retrieve PDF file information."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM pdf_files WHERE id = ?
        """, (pdf_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_project_pdfs(self, project_id: int) -> list:
        """Get all PDFs for a project."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM pdf_files 
            WHERE project_id = ? 
            ORDER BY uploaded_date DESC
        """, (project_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_pdf(self, pdf_id: int) -> bool:
        """Delete PDF file and database record."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Get file path
        cursor.execute("SELECT file_path FROM pdf_files WHERE id = ?", (pdf_id,))
        row = cursor.fetchone()
        
        if row:
            file_path = Path(row['file_path'])
            
            # Delete file
            if file_path.exists():
                file_path.unlink()
            
            # Delete database record
            cursor.execute("DELETE FROM pdf_files WHERE id = ?", (pdf_id,))
            conn.commit()
            return True
        
        return False
```

### 3. Project Data Access (`src/database/project_dao.py`)

```python
"""
Data Access Object for Projects.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

class ProjectDAO:
    """Handles project data storage and retrieval."""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def create_project(self, project_data: Dict[str, Any]) -> int:
        """Create a new project."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO projects 
            (project_name, project_date, building_height_ft, roof_area_sqft,
             perimeter_ft, num_corners, soil_type, has_metal_roof,
             preferred_material, compliance_standard)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_data.get('project_name'),
            project_data.get('project_date', datetime.now().isoformat()),
            project_data.get('building_height_ft'),
            project_data.get('roof_area_sqft'),
            project_data.get('perimeter_ft'),
            project_data.get('num_corners', 4),
            project_data.get('soil_type', 'normal'),
            1 if project_data.get('has_metal_roof', False) else 0,
            project_data.get('preferred_material', 'copper'),
            project_data.get('compliance_standard', 'UL 96A')
        ))
        
        project_id = cursor.lastrowid
        conn.commit()
        return project_id
    
    def get_project(self, project_id: int) -> Optional[Dict]:
        """Get project by ID."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        
        if row:
            data = dict(row)
            # Convert has_metal_roof back to boolean
            data['has_metal_roof'] = bool(data['has_metal_roof'])
            return data
        return None
    
    def get_all_projects(self) -> List[Dict]:
        """Get all projects."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        projects = []
        for row in rows:
            data = dict(row)
            data['has_metal_roof'] = bool(data['has_metal_roof'])
            projects.append(data)
        
        return projects
    
    def update_project(self, project_id: int, project_data: Dict[str, Any]) -> bool:
        """Update project data."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE projects SET
                project_name = ?,
                building_height_ft = ?,
                roof_area_sqft = ?,
                perimeter_ft = ?,
                num_corners = ?,
                soil_type = ?,
                has_metal_roof = ?,
                preferred_material = ?,
                compliance_standard = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            project_data.get('project_name'),
            project_data.get('building_height_ft'),
            project_data.get('roof_area_sqft'),
            project_data.get('perimeter_ft'),
            project_data.get('num_corners'),
            project_data.get('soil_type'),
            1 if project_data.get('has_metal_roof', False) else 0,
            project_data.get('preferred_material'),
            project_data.get('compliance_standard'),
            project_id
        ))
        
        conn.commit()
        return cursor.rowcount > 0
```

---

## Integration with Flet GUI

### Example: Save PDF in Flet App

```python
import flet as ft
from pathlib import Path
from src.database.db_manager import DatabaseManager
from src.database.pdf_dao import PDFDAO
from src.database.project_dao import ProjectDAO
from src.adapters.pdf_loader import extract_project_data

def main(page: ft.Page):
    # Initialize database
    db = DatabaseManager()
    db.initialize_tables()
    
    pdf_dao = PDFDAO(db)
    project_dao = ProjectDAO(db)
    
    # File picker
    file_picker = ft.FilePicker()
    
    def on_file_selected(e):
        if file_picker.result.files:
            pdf_path = Path(file_picker.result.files[0].path)
            
            # Extract data from PDF
            extracted_data = extract_project_data(pdf_path)
            
            # Create project
            project_data = {
                'project_name': extracted_data['project_info']['project_name'] or 'New Project',
                'building_height_ft': extracted_data['building_dimensions']['height'],
                'roof_area_sqft': extracted_data['building_dimensions']['area'],
                # ... more fields
            }
            
            project_id = project_dao.create_project(project_data)
            
            # Save PDF
            pdf_id = pdf_dao.save_pdf(project_id, pdf_path, extracted_data)
            
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"PDF saved! Project ID: {project_id}"),
                bgcolor=ft.colors.GREEN
            )
            page.snack_bar.open = True
            page.update()
    
    # UI
    page.add(
        ft.ElevatedButton(
            "Select PDF",
            on_click=lambda _: file_picker.pick_files(
                allowed_extensions=["pdf"],
                dialog_title="Select PDF Specification"
            )
        )
    )
    
    page.overlay.append(file_picker)
    file_picker.on_result = on_file_selected

ft.app(target=main)
```

---

## File Storage Structure

```
data/
├── lightningbid.db              # SQLite database
├── uploads/
│   ├── project_1/
│   │   ├── spec.pdf
│   │   └── spec_2.pdf
│   ├── project_2/
│   │   └── spec.pdf
│   └── pricing/
│       ├── pricing_2024.xlsx
│       └── pricing_2023.xlsx
└── outputs/
    ├── project_1/
    │   ├── bid_1.xlsx
    │   └── submittal_1.pdf
    └── project_2/
        └── bid_2.xlsx
```

---

## Benefits of Database Integration

1. **Project History** - Save all projects, view later
2. **PDF Management** - Track all uploaded PDFs
3. **Bid History** - Compare bids over time
4. **Search** - Find projects by name, date, etc.
5. **Backup** - Easy to backup (just copy .db file)
6. **Reporting** - Generate reports from historical data

---

## Migration Path

### Phase 1: Basic Database
- Add SQLite database
- Save projects
- Save PDF paths

### Phase 2: Full Integration
- Save bids
- Save output files
- History tracking

### Phase 3: Advanced Features
- Search functionality
- Reports
- Export database

---

## Summary

✅ **Flet + SQLite = Perfect Match**
- Flet handles GUI
- SQLite handles data
- Both work 100% locally
- No server needed
- Easy to deploy

**Your partner's idea is great!** Database will make the app much more useful for tracking projects and bids over time.

