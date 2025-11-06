-- 1. Create the Users table
CREATE TABLE Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 2. Create the SourceDocuments table
CREATE TABLE SourceDocuments (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    upload_date TEXT NOT NULL,
    parsed_status TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users (user_id)
);

-- 3. Create the BidSheets table
CREATE TABLE BidSheets (
    bid_sheet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    generation_date TEXT NOT NULL,
    bid_file_path TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES Users (user_id)
);
