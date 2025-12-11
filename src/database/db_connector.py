import sqlite3
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
    """

    def __init__(self):
        """Initializes the database connection and ensures tables exist."""
        self._connection = None
        self._cursor = None
        self._initialize_db()

    def _initialize_db(self):
        """Creates the database file and schema if they do not exist."""
        try:
            # Ensure the directory exists
            self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Connect to the database (creates file if it doesn't exist)
            self._connection = sqlite3.connect(self.DB_PATH)
            self._cursor = self._connection.cursor()
            
            # Execute schema creation script
            self._cursor.executescript(self.CREATE_TABLES_SQL)
            self._connection.commit()
            
        except sqlite3.Error as e:
            print(f"Database error during initialization: {e}")
            raise
        
    def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Executes a non-query SQL statement (e.g., INSERT, UPDATE, DELETE)."""
        try:
            self._cursor.execute(sql, params)
            self._connection.commit()
            return self._cursor
        except sqlite3.Error as e:
            print(f"Database error executing SQL: {e}")
            self._connection.rollback()
            raise

    def fetchone(self, sql: str, params: Tuple[Any, ...] = ()) -> Any:
        """Executes a query and returns a single row."""
        self._cursor.execute(sql, params)
        return self._cursor.fetchone()

    def fetchall(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Any]:
        """Executes a query and returns all rows."""
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