import sqlite3
import threading
from pathlib import Path
from typing import List, Tuple, Any, Optional

class DBConnector:
    """
    Manages the connection to the SQLite database and handles schema initialization.
    """
    
    # Path to the database file (relative to the project root's src folder)
    DB_PATH = Path(__file__).parent / "app.db"
    
    # SQL to create all necessary tables based on the provided schema
    CREATE_TABLES_SQL = """
    CREATE TABLE IF NOT EXISTS Users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS SourceDocuments (
        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_type TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        upload_date TEXT NOT NULL,
        parsed_status TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES Users (user_id)
    );
    
    CREATE TABLE IF NOT EXISTS BidSheets (
        bid_sheet_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        generation_date TEXT NOT NULL,
        bid_file_path TEXT NOT NULL,
        version INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES Users (user_id)
    );
    
    -- MVP data layer tables (multi-user, SaaS-ready schema)
    CREATE TABLE IF NOT EXISTS Customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, name),
        FOREIGN KEY (user_id) REFERENCES Users (user_id)
    );
    
    CREATE TABLE IF NOT EXISTS Projects (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        building_height_ft REAL,
        roof_area_sqft REAL,
        perimeter_ft REAL,
        num_corners INTEGER,
        has_metal_roof INTEGER DEFAULT 0,
        preferred_material TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user_id, name),
        FOREIGN KEY (user_id) REFERENCES Users (user_id)
    );
    
    CREATE TABLE IF NOT EXISTS Bids (
        bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        compliance_code TEXT,
        subtotal REAL,
        total_with_markup REAL,
        final_amount REAL,
        material_total REAL,
        labor_total REAL,
        status TEXT DEFAULT 'draft',
        date_sent TEXT,
        date_responded TEXT,
        follow_up_date TEXT,
        FOREIGN KEY (user_id) REFERENCES Users (user_id),
        FOREIGN KEY (project_id) REFERENCES Projects (project_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS BidSettings (
        bid_id INTEGER PRIMARY KEY,
        labor_markup_pct REAL,
        overhead_pct REAL,
        profit_pct REAL,
        commission_amount REAL,
        tools_rental_amount REAL,
        tools_rental_type TEXT,
        shipping_amount REAL,
        use_tax_pct REAL,
        FOREIGN KEY (bid_id) REFERENCES Bids (bid_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS BidWorkers (
        worker_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bid_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        wage_per_hour REAL,
        hours REAL,
        total_cost REAL,
        FOREIGN KEY (bid_id) REFERENCES Bids (bid_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS BidSections (
        section_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bid_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        material_total REAL,
        labor_total REAL,
        FOREIGN KEY (bid_id) REFERENCES Bids (bid_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS BidLineItems (
        line_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_id INTEGER NOT NULL,
        item_code TEXT,
        description TEXT,
        material_type TEXT,
        unit TEXT,
        unit_price REAL,
        quantity REAL,
        material_cost REAL,
        labor_cost REAL,
        reason TEXT,
        FOREIGN KEY (section_id) REFERENCES BidSections (section_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS Exports (
        export_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bid_id INTEGER NOT NULL,
        export_type TEXT NOT NULL,
        file_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (bid_id) REFERENCES Bids (bid_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS Autosaves (
        autosave_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES Users (user_id) ON DELETE CASCADE
    );
    
    -- Job Management Tables (Phase 1)
    -- Track job lifecycle from bid acceptance to completion
    CREATE TABLE IF NOT EXISTS Jobs (
        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bid_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'scheduled',
        scheduled_date TEXT,
        start_date TEXT,
        completion_date TEXT,
        assigned_crew TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (bid_id) REFERENCES Bids (bid_id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES Users (user_id)
    );
    
    -- Job photos and documents storage tracking
    CREATE TABLE IF NOT EXISTS JobDocuments (
        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        document_type TEXT NOT NULL,
        file_path TEXT NOT NULL,
        tag TEXT,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY (job_id) REFERENCES Jobs (job_id) ON DELETE CASCADE
    );
    
    -- Job activity log for audit trail and timeline
    CREATE TABLE IF NOT EXISTS JobActivity (
        activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        activity_type TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (job_id) REFERENCES Jobs (job_id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES Users (user_id)
    );
    
    -- Financial tracking for completed jobs (Phase 3)
    CREATE TABLE IF NOT EXISTS JobFinancials (
        financial_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        bid_amount REAL NOT NULL,
        estimated_materials REAL NOT NULL,
        estimated_labor_hours REAL NOT NULL,
        estimated_labor_cost REAL NOT NULL,
        actual_materials_cost REAL,
        actual_labor_hours REAL,
        actual_labor_cost REAL,
        overhead_cost REAL,
        tools_rental_cost REAL,
        shipping_cost REAL,
        tax_amount REAL,
        commission_amount REAL,
        other_costs REAL,
        payment_status TEXT DEFAULT 'unpaid',
        amount_paid REAL DEFAULT 0,
        payment_date TEXT,
        total_costs REAL,
        net_profit REAL,
        profit_margin_pct REAL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (job_id) REFERENCES Jobs (job_id) ON DELETE CASCADE
    );
    """

    def __init__(self):
        """Initializes the database connection and ensures tables exist."""
        self._connection = None
        self._cursor = None
        self._lock = threading.Lock()
        self._initialize_db()

    def _initialize_db(self):
        """Creates the database file and schema if they do not exist."""
        try:
            # Ensure the directory exists
            self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Connect to the database (creates file if it doesn't exist)
            # Allow access from multiple threads; guard with a lock for safety.
            self._connection = sqlite3.connect(self.DB_PATH, check_same_thread=False)
            self._cursor = self._connection.cursor()
            self._cursor.execute("PRAGMA foreign_keys = ON;")
            
            # Execute schema creation script
            self._cursor.executescript(self.CREATE_TABLES_SQL)
            self._connection.commit()
            
            # --- Lightweight schema migration: drop customer_id from Projects ---
            # NOTE: This keeps historical data but aligns schema with the
            # "project-only" model until customer management is needed.
            columns = [row[1] for row in self._cursor.execute("PRAGMA table_info(Projects);")]
            if "customer_id" in columns:
                self._cursor.execute("PRAGMA foreign_keys = OFF;")
                self._cursor.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS Projects_v2 (
                        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        building_height_ft REAL,
                        roof_area_sqft REAL,
                        perimeter_ft REAL,
                        num_corners INTEGER,
                        has_metal_roof INTEGER DEFAULT 0,
                        preferred_material TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(user_id, name),
                        FOREIGN KEY (user_id) REFERENCES Users (user_id)
                    );
                    INSERT INTO Projects_v2 (
                        project_id, user_id, name, building_height_ft, roof_area_sqft, perimeter_ft,
                        num_corners, has_metal_roof, preferred_material, created_at, updated_at
                    )
                    SELECT project_id, user_id, name, building_height_ft, roof_area_sqft, perimeter_ft,
                           num_corners, has_metal_roof, preferred_material, created_at, updated_at
                    FROM Projects;
                    DROP TABLE Projects;
                    ALTER TABLE Projects_v2 RENAME TO Projects;
                    """
                )
                self._cursor.execute("PRAGMA foreign_keys = ON;")
                self._connection.commit()
            
            # --- Schema migration: Add status tracking to Bids table ---
            bid_columns = [row[1] for row in self._cursor.execute("PRAGMA table_info(Bids);")]
            if "status" not in bid_columns:
                print("Migrating Bids table to add status tracking...")
                self._cursor.execute("ALTER TABLE Bids ADD COLUMN status TEXT DEFAULT 'draft';")
                self._cursor.execute("ALTER TABLE Bids ADD COLUMN date_sent TEXT;")
                self._cursor.execute("ALTER TABLE Bids ADD COLUMN date_responded TEXT;")
                self._cursor.execute("ALTER TABLE Bids ADD COLUMN follow_up_date TEXT;")
                self._connection.commit()
                print("Bids table migration complete.")
            
        except sqlite3.Error as e:
            print(f"Database error during initialization: {e}")
            raise
        
    def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Executes a non-query SQL statement (e.g., INSERT, UPDATE, DELETE)."""
        try:
            with self._lock:
                self._cursor.execute(sql, params)
                self._connection.commit()
                return self._cursor
        except sqlite3.Error as e:
            print(f"Database error executing SQL: {e}")
            with self._lock:
                self._connection.rollback()
            raise

    def fetchone(self, sql: str, params: Tuple[Any, ...] = ()) -> Any:
        """Executes a query and returns a single row."""
        with self._lock:
            self._cursor.execute(sql, params)
            return self._cursor.fetchone()

    def fetchall(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Any]:
        """Executes a query and returns all rows."""
        with self._lock:
            self._cursor.execute(sql, params)
            return self._cursor.fetchall()

    def close(self):
        """Closes the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            self._cursor = None

    def create_user(self, username: str, email: str, password_hash: str) -> Optional[int]:
        """Inserts a new user into the Users table and returns their user_id."""
        from datetime import datetime
        
        sql = """
        INSERT INTO Users (username, email, password_hash, created_at) 
        VALUES (?, ?, ?, ?);
        """
        # Get current timestamp for created_at
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            self.execute(sql, (username, email, password_hash, timestamp))
            # Return the ID of the last inserted row
            return self._cursor.lastrowid
        
        except sqlite3.IntegrityError as e: # <-- NEW: Catch the integrity error
            # This handles UNIQUE constraints (e.g., username or email already exists)
            print(f"User creation failed: Integrity error - {e}")
            return None # Indicate failure
            
        except Exception as e:
            print(f"Error creating user {username}: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[tuple]:
        """Retrieves a user's details by username."""
        sql = "SELECT user_id, username, password_hash FROM Users WHERE username = ?;"
        return self.fetchone(sql, (username,))

# Optional: Simple test execution for sanity check
if __name__ == '__main__':
    print(f"Database path: {DBConnector.DB_PATH}")
    db = DBConnector()
    print(".tables result:", db.fetchall("SELECT name FROM sqlite_master WHERE type='table';"))
    db.close()
