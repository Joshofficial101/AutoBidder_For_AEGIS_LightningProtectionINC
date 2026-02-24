from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


class SQLiteBackupManager:
    """
    Creates SQLite-safe backups using the SQLite backup API.

    This works while the app is running and does not require internet access.
    """

    def __init__(
        self,
        db_path: Path,
        backup_dir: Optional[Path] = None,
        retention_days: int = 30,
        max_backups: int = 120,
    ) -> None:
        self.db_path = Path(db_path)
        self.backup_dir = backup_dir or (self.db_path.parent / "backups")
        self.retention_days = retention_days
        self.max_backups = max_backups
        self.state_file = self.backup_dir / "backup_state.json"

    def create_backup(
        self,
        reason: str,
        source_connection: Optional[sqlite3.Connection] = None,
    ) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_reason = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in reason)
        backup_path = self.backup_dir / f"{self.db_path.stem}_{stamp}_{safe_reason}.db"

        if source_connection is not None:
            # Best-effort WAL checkpoint before taking a snapshot.
            try:
                source_connection.execute("PRAGMA wal_checkpoint(FULL);")
            except sqlite3.Error:
                pass
            with sqlite3.connect(str(backup_path)) as dest_conn:
                source_connection.backup(dest_conn)
        else:
            with sqlite3.connect(str(self.db_path)) as src_conn:
                with sqlite3.connect(str(backup_path)) as dest_conn:
                    src_conn.backup(dest_conn)

        self._prune_old_backups()
        return backup_path

    def create_daily_backup_if_due(
        self,
        source_connection: Optional[sqlite3.Connection] = None,
    ) -> Optional[Path]:
        today = datetime.now().strftime("%Y-%m-%d")
        state = self._load_state()
        if state.get("last_daily_backup") == today:
            return None

        backup_path = self.create_backup("daily", source_connection=source_connection)
        state["last_daily_backup"] = today
        self._save_state(state)
        return backup_path

    def _prune_old_backups(self) -> None:
        if not self.backup_dir.exists():
            return

        now = datetime.now()
        backups = sorted(
            self.backup_dir.glob(f"{self.db_path.stem}_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        to_keep = []
        for path in backups:
            age_days = (now - datetime.fromtimestamp(path.stat().st_mtime)).days
            if age_days <= self.retention_days:
                to_keep.append(path)

        # Keep the newest backups up to max_backups, prune the rest.
        protected = set(to_keep[: self.max_backups])
        for index, path in enumerate(backups):
            if index < self.max_backups and path in protected:
                continue
            age_days = (now - datetime.fromtimestamp(path.stat().st_mtime)).days
            if age_days > self.retention_days or index >= self.max_backups:
                path.unlink(missing_ok=True)

    def _load_state(self) -> dict:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, state: dict) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
