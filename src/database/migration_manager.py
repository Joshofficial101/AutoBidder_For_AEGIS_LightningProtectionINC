from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional


MigrationFn = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migration:
    migration_id: str
    description: str
    up: MigrationFn
    down: MigrationFn


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _table_columns(conn: sqlite3.Connection, table_name: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name});").fetchall()
    return [row[1] for row in rows]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?;",
        (table_name,),
    ).fetchone()
    return bool(row)


def _replace_table(conn: sqlite3.Connection, old_table: str, create_sql: str, copy_sql: str) -> None:
    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.execute("BEGIN;")
        conn.execute(create_sql)
        conn.execute(copy_sql)
        conn.execute(f"DROP TABLE {old_table};")
        conn.execute(f"ALTER TABLE {old_table}_v2 RENAME TO {old_table};")
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")


def _up_drop_projects_customer_id(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "Projects"):
        return
    columns = _table_columns(conn, "Projects")
    if "customer_id" not in columns:
        return

    _replace_table(
        conn=conn,
        old_table="Projects",
        create_sql="""
            CREATE TABLE Projects_v2 (
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
        """,
        copy_sql="""
            INSERT INTO Projects_v2 (
                project_id, user_id, name, building_height_ft, roof_area_sqft, perimeter_ft,
                num_corners, has_metal_roof, preferred_material, created_at, updated_at
            )
            SELECT project_id, user_id, name, building_height_ft, roof_area_sqft, perimeter_ft,
                   num_corners, has_metal_roof, preferred_material, created_at, updated_at
            FROM Projects;
        """,
    )


def _down_drop_projects_customer_id(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "Projects"):
        return
    columns = _table_columns(conn, "Projects")
    if "customer_id" in columns:
        return
    conn.execute("ALTER TABLE Projects ADD COLUMN customer_id INTEGER;")


def _up_add_bid_status_tracking(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "Bids"):
        return
    columns = _table_columns(conn, "Bids")
    if "status" not in columns:
        conn.execute("ALTER TABLE Bids ADD COLUMN status TEXT DEFAULT 'draft';")
    if "date_sent" not in columns:
        conn.execute("ALTER TABLE Bids ADD COLUMN date_sent TEXT;")
    if "date_responded" not in columns:
        conn.execute("ALTER TABLE Bids ADD COLUMN date_responded TEXT;")
    if "follow_up_date" not in columns:
        conn.execute("ALTER TABLE Bids ADD COLUMN follow_up_date TEXT;")


def _down_add_bid_status_tracking(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "Bids"):
        return
    columns = _table_columns(conn, "Bids")
    if all(col not in columns for col in ("status", "date_sent", "date_responded", "follow_up_date")):
        return

    _replace_table(
        conn=conn,
        old_table="Bids",
        create_sql="""
            CREATE TABLE Bids_v2 (
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
                FOREIGN KEY (user_id) REFERENCES Users (user_id),
                FOREIGN KEY (project_id) REFERENCES Projects (project_id) ON DELETE CASCADE
            );
        """,
        copy_sql="""
            INSERT INTO Bids_v2 (
                bid_id, user_id, project_id, created_at, compliance_code,
                subtotal, total_with_markup, final_amount, material_total, labor_total
            )
            SELECT bid_id, user_id, project_id, created_at, compliance_code,
                   subtotal, total_with_markup, final_amount, material_total, labor_total
            FROM Bids;
        """,
    )


def _up_add_user_recovery_columns(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "Users"):
        return
    columns = _table_columns(conn, "Users")
    if "recovery_code_hash" not in columns:
        conn.execute("ALTER TABLE Users ADD COLUMN recovery_code_hash TEXT;")
    if "recovery_code_updated_at" not in columns:
        conn.execute("ALTER TABLE Users ADD COLUMN recovery_code_updated_at TEXT;")


def _down_add_user_recovery_columns(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "Users"):
        return
    columns = _table_columns(conn, "Users")
    if "recovery_code_hash" not in columns and "recovery_code_updated_at" not in columns:
        return

    _replace_table(
        conn=conn,
        old_table="Users",
        create_sql="""
            CREATE TABLE Users_v2 (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """,
        copy_sql="""
            INSERT INTO Users_v2 (
                user_id, username, email, password_hash, created_at
            )
            SELECT user_id, username, email, password_hash, created_at
            FROM Users;
        """,
    )


def _up_add_jobs_invoicing_columns(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "Jobs"):
        return
    columns = _table_columns(conn, "Jobs")
    if "invoice_number" not in columns:
        conn.execute("ALTER TABLE Jobs ADD COLUMN invoice_number TEXT;")
    if "invoice_date" not in columns:
        conn.execute("ALTER TABLE Jobs ADD COLUMN invoice_date TEXT;")


def _down_add_jobs_invoicing_columns(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "Jobs"):
        return
    columns = _table_columns(conn, "Jobs")
    if "invoice_number" not in columns and "invoice_date" not in columns:
        return

    _replace_table(
        conn=conn,
        old_table="Jobs",
        create_sql="""
            CREATE TABLE Jobs_v2 (
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
        """,
        copy_sql="""
            INSERT INTO Jobs_v2 (
                job_id, bid_id, user_id, status, scheduled_date, start_date, completion_date,
                assigned_crew, notes, created_at, updated_at
            )
            SELECT
                job_id, bid_id, user_id, status, scheduled_date, start_date, completion_date,
                assigned_crew, notes, created_at, updated_at
            FROM Jobs;
        """,
    )


def _up_add_project_workplans(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
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
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_projectworkplans_user_project
            ON ProjectWorkPlans (user_id, project_id);
        """
    )


def _down_add_project_workplans(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "ProjectWorkPlans"):
        return
    conn.execute("DROP TABLE IF EXISTS ProjectWorkPlans;")


MIGRATIONS: List[Migration] = [
    Migration(
        migration_id="20260220_001_projects_drop_customer_id",
        description="Drop legacy Projects.customer_id column",
        up=_up_drop_projects_customer_id,
        down=_down_drop_projects_customer_id,
    ),
    Migration(
        migration_id="20260220_002_bids_status_tracking",
        description="Add bid status/date tracking columns",
        up=_up_add_bid_status_tracking,
        down=_down_add_bid_status_tracking,
    ),
    Migration(
        migration_id="20260220_003_users_recovery_columns",
        description="Add user recovery code columns",
        up=_up_add_user_recovery_columns,
        down=_down_add_user_recovery_columns,
    ),
    Migration(
        migration_id="20260221_004_jobs_invoicing_fields",
        description="Add invoice fields to jobs workflow",
        up=_up_add_jobs_invoicing_columns,
        down=_down_add_jobs_invoicing_columns,
    ),
    Migration(
        migration_id="20260315_005_project_workplans",
        description="Add persisted project work plan storage",
        up=_up_add_project_workplans,
        down=_down_add_project_workplans,
    ),
]


class MigrationManager:
    def __init__(self, connection: sqlite3.Connection, migrations: Optional[Iterable[Migration]] = None) -> None:
        self.conn = connection
        self.migrations = list(migrations or MIGRATIONS)
        self._migration_index: Dict[str, Migration] = {m.migration_id: m for m in self.migrations}

    def ensure_migration_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS SchemaMigrations (
                migration_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def applied_ids(self) -> List[str]:
        rows = self.conn.execute(
            "SELECT migration_id FROM SchemaMigrations ORDER BY applied_at ASC, migration_id ASC;"
        ).fetchall()
        return [row[0] for row in rows]

    def pending_migrations(self) -> List[Migration]:
        applied = set(self.applied_ids())
        return [migration for migration in self.migrations if migration.migration_id not in applied]

    def has_pending_migrations(self) -> bool:
        return len(self.pending_migrations()) > 0

    def apply_pending_migrations(self) -> List[str]:
        applied_now: List[str] = []
        for migration in self.pending_migrations():
            migration.up(self.conn)
            self.conn.execute(
                """
                INSERT INTO SchemaMigrations (migration_id, description, applied_at)
                VALUES (?, ?, ?);
                """,
                (migration.migration_id, migration.description, _utc_now()),
            )
            self.conn.commit()
            applied_now.append(migration.migration_id)
        return applied_now

    def rollback_last(self, steps: int = 1) -> List[str]:
        if steps < 1:
            return []

        rows = self.conn.execute(
            """
            SELECT migration_id
            FROM SchemaMigrations
            ORDER BY applied_at DESC, migration_id DESC
            LIMIT ?;
            """,
            (steps,),
        ).fetchall()
        to_rollback = [row[0] for row in rows]
        rolled_back: List[str] = []

        for migration_id in to_rollback:
            migration = self._migration_index.get(migration_id)
            if migration is None:
                raise ValueError(
                    f"Cannot rollback migration '{migration_id}' because its definition is missing."
                )
            migration.down(self.conn)
            self.conn.execute(
                "DELETE FROM SchemaMigrations WHERE migration_id = ?;",
                (migration_id,),
            )
            self.conn.commit()
            rolled_back.append(migration_id)

        return rolled_back
