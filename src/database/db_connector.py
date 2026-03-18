import sqlite3
import threading
from pathlib import Path
from typing import List, Tuple, Any, Optional, Dict

from src.database.backup_manager import SQLiteBackupManager
from src.database.migration_manager import MigrationManager

class DBConnector:
    """
    Manages the connection to the SQLite database and handles schema initialization.
    """
    
    # Path to the database file (relative to the project root's src folder)
    DB_PATH = Path(__file__).parent / "app.db"
    BACKUP_DIR = DB_PATH.parent / "backups"

    _maintenance_lock = threading.Lock()
    _maintenance_ran = False
    
    # SQL to create all necessary tables based on the provided schema
    CREATE_TABLES_SQL = """
    CREATE TABLE IF NOT EXISTS Users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        recovery_code_hash TEXT,
        recovery_code_updated_at TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS AuthSecurity (
        username TEXT PRIMARY KEY,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        locked_until TEXT,
        last_failed_at TEXT,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS AuthSessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        last_used_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked_at TEXT,
        FOREIGN KEY (user_id) REFERENCES Users (user_id) ON DELETE CASCADE
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
        invoice_number TEXT,
        invoice_date TEXT,
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

    CREATE TABLE IF NOT EXISTS ProjectWorkPlans (
        work_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        source_file_name TEXT,
        compliance_code TEXT NOT NULL,
        canvas_width REAL NOT NULL,
        canvas_height REAL NOT NULL,
        plan_payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES Projects (project_id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES Users (user_id)
    );

    -- Dashboard and board query indexes
    CREATE INDEX IF NOT EXISTS idx_jobs_user_status
        ON Jobs (user_id, status);
    CREATE INDEX IF NOT EXISTS idx_jobs_user_updated_at
        ON Jobs (user_id, updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_jobs_user_scheduled_date
        ON Jobs (user_id, scheduled_date);
    CREATE INDEX IF NOT EXISTS idx_jobfinancials_job_id
        ON JobFinancials (job_id);
    CREATE INDEX IF NOT EXISTS idx_projectworkplans_user_project
        ON ProjectWorkPlans (user_id, project_id);
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
            self._connection = sqlite3.connect(str(self.DB_PATH), check_same_thread=False)
            self._cursor = self._connection.cursor()
            self._cursor.execute("PRAGMA foreign_keys = ON;")
            
            # Execute schema creation script
            self._cursor.executescript(self.CREATE_TABLES_SQL)
            self._connection.commit()

            self._run_startup_maintenance()
            
        except sqlite3.Error as e:
            print(f"Database error during initialization: {e}")
            raise

    def _run_startup_maintenance(self) -> None:
        """
        Runs one-time maintenance per process:
        - Applies pending migrations (with pre-migration backup)
        - Creates daily backup snapshot
        """
        with DBConnector._maintenance_lock:
            if DBConnector._maintenance_ran:
                return

            backup_manager = SQLiteBackupManager(self.DB_PATH, backup_dir=self.BACKUP_DIR)
            migration_manager = MigrationManager(self._connection)
            migration_manager.ensure_migration_table()

            pending = migration_manager.pending_migrations()
            if pending:
                backup_path = backup_manager.create_backup(
                    reason="pre_migration",
                    source_connection=self._connection,
                )
                print(f"Database backup created before migrations: {backup_path}")
                applied = migration_manager.apply_pending_migrations()
                print(f"Applied DB migrations: {', '.join(applied)}")

            daily_backup = backup_manager.create_daily_backup_if_due(
                source_connection=self._connection,
            )
            if daily_backup:
                print(f"Daily database backup created: {daily_backup}")

            DBConnector._maintenance_ran = True
        
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

    @classmethod
    def migration_status(cls) -> Dict[str, Any]:
        """Returns applied and pending migration IDs."""
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(cls.DB_PATH))
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.executescript(cls.CREATE_TABLES_SQL)
            conn.commit()

            migration_manager = MigrationManager(conn)
            migration_manager.ensure_migration_table()
            applied = migration_manager.applied_ids()
            pending = [m.migration_id for m in migration_manager.pending_migrations()]
            return {"applied": applied, "pending": pending}
        finally:
            conn.close()

    @classmethod
    def create_backup(cls, reason: str = "manual") -> Path:
        """Creates a safe database backup snapshot."""
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        backup_manager = SQLiteBackupManager(cls.DB_PATH, backup_dir=cls.BACKUP_DIR)
        return backup_manager.create_backup(reason=reason)

    @classmethod
    def rollback_last_migrations(cls, steps: int = 1) -> List[str]:
        """
        Rolls back the most recently applied migrations.

        A safety backup is created before rollback.
        """
        if steps < 1:
            return []

        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(cls.DB_PATH))
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.executescript(cls.CREATE_TABLES_SQL)
            conn.commit()

            backup_manager = SQLiteBackupManager(cls.DB_PATH, backup_dir=cls.BACKUP_DIR)
            backup_path = backup_manager.create_backup(reason="pre_rollback", source_connection=conn)
            print(f"Database backup created before rollback: {backup_path}")

            migration_manager = MigrationManager(conn)
            migration_manager.ensure_migration_table()
            return migration_manager.rollback_last(steps=steps)
        finally:
            conn.close()

    def create_user(
        self,
        username: str,
        email: str,
        password_hash: str,
        recovery_code_hash: Optional[str] = None,
    ) -> Optional[int]:
        """Inserts a new user into the Users table and returns their user_id."""
        from datetime import datetime
        
        sql = """
        INSERT INTO Users (
            username,
            email,
            password_hash,
            recovery_code_hash,
            recovery_code_updated_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?);
        """
        # Get current timestamp for created_at
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            self.execute(
                sql,
                (
                    username,
                    email,
                    password_hash,
                    recovery_code_hash,
                    timestamp if recovery_code_hash else None,
                    timestamp,
                ),
            )
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

    def get_user_auth_by_id(self, user_id: int) -> Optional[tuple]:
        """Retrieves user auth fields by user_id."""
        sql = "SELECT user_id, username, password_hash FROM Users WHERE user_id = ?;"
        return self.fetchone(sql, (user_id,))

    def get_user_recovery_by_username(self, username: str) -> Optional[tuple]:
        """Retrieves user recovery details by username."""
        sql = """
        SELECT user_id, username, recovery_code_hash
        FROM Users
        WHERE username = ?;
        """
        return self.fetchone(sql, (username,))

    def update_user_password_and_recovery(
        self,
        user_id: int,
        password_hash: str,
        recovery_code_hash: str,
        recovery_code_updated_at: str,
    ) -> None:
        """Updates user password hash and rotates backup recovery code hash."""
        sql = """
        UPDATE Users
        SET
            password_hash = ?,
            recovery_code_hash = ?,
            recovery_code_updated_at = ?
        WHERE user_id = ?;
        """
        self.execute(sql, (password_hash, recovery_code_hash, recovery_code_updated_at, user_id))

    def get_auth_security_by_username(self, username: str) -> Optional[tuple]:
        """Retrieves auth security state by username."""
        sql = """
        SELECT failed_attempts, locked_until, last_failed_at
        FROM AuthSecurity
        WHERE username = ?;
        """
        return self.fetchone(sql, (username,))

    def upsert_auth_security(
        self,
        username: str,
        failed_attempts: int,
        locked_until: Optional[str],
        last_failed_at: str,
        updated_at: str,
    ) -> None:
        """Creates or updates auth security state for a username."""
        sql = """
        INSERT INTO AuthSecurity (username, failed_attempts, locked_until, last_failed_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            failed_attempts = excluded.failed_attempts,
            locked_until = excluded.locked_until,
            last_failed_at = excluded.last_failed_at,
            updated_at = excluded.updated_at;
        """
        self.execute(sql, (username, failed_attempts, locked_until, last_failed_at, updated_at))

    def clear_auth_security(self, username: str) -> None:
        """Clears auth security state for a username after successful login."""
        sql = "DELETE FROM AuthSecurity WHERE username = ?;"
        self.execute(sql, (username,))

    def purge_stale_auth_sessions(self, active_time_iso: str) -> None:
        """
        Removes expired and revoked sessions to keep local auth storage bounded.

        Args:
            active_time_iso: Current UTC timestamp string in ISO-like format.
        """
        sql = """
        DELETE FROM AuthSessions
        WHERE expires_at <= ?
           OR (revoked_at IS NOT NULL AND revoked_at <= ?);
        """
        self.execute(sql, (active_time_iso, active_time_iso))

    def create_auth_session(
        self,
        user_id: int,
        token_hash: str,
        created_at: str,
        last_used_at: str,
        expires_at: str,
    ) -> int:
        """Creates a new auth session and returns session_id."""
        sql = """
        INSERT INTO AuthSessions (
            user_id,
            token_hash,
            created_at,
            last_used_at,
            expires_at
        ) VALUES (?, ?, ?, ?, ?);
        """
        self.execute(sql, (user_id, token_hash, created_at, last_used_at, expires_at))
        return int(self._cursor.lastrowid)

    def get_auth_session_by_token_hash(self, token_hash: str) -> Optional[tuple]:
        """Finds a session by token hash and includes username for fast auth checks."""
        sql = """
        SELECT
            s.session_id,
            s.user_id,
            u.username,
            s.last_used_at,
            s.expires_at,
            s.revoked_at
        FROM AuthSessions s
        JOIN Users u ON u.user_id = s.user_id
        WHERE s.token_hash = ?;
        """
        return self.fetchone(sql, (token_hash,))

    def touch_auth_session(self, session_id: int, last_used_at: str) -> None:
        """Updates last-used timestamp for an active session."""
        sql = """
        UPDATE AuthSessions
        SET last_used_at = ?
        WHERE session_id = ? AND revoked_at IS NULL;
        """
        self.execute(sql, (last_used_at, session_id))

    def revoke_auth_session(self, session_id: int, revoked_at: str) -> None:
        """Marks a session revoked (idempotent)."""
        sql = """
        UPDATE AuthSessions
        SET revoked_at = ?
        WHERE session_id = ? AND revoked_at IS NULL;
        """
        self.execute(sql, (revoked_at, session_id))

# Optional: Simple test execution for sanity check
if __name__ == '__main__':
    print(f"Database path: {DBConnector.DB_PATH}")
    db = DBConnector()
    print(".tables result:", db.fetchall("SELECT name FROM sqlite_master WHERE type='table';"))
    db.close()
