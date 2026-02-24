# Data Safety (Offline SQLite)

This project now includes:

1. Automated SQLite-safe backups (daily)
2. Pre-migration backups (before schema updates)
3. Versioned migrations with rollback support

## Backup Behavior

- Backup location: `src/database/backups/`
- Daily backup: created automatically once per day when the app/API starts and initializes DB.
- Pre-migration backup: created automatically before pending migrations are applied.
- Pre-rollback backup: created automatically before rolling back migrations.
- Backup method: SQLite backup API (safe while DB is in use).

## Migration Behavior

- Migration table: `SchemaMigrations`
- Migrations are versioned and applied in order.
- Pending migrations run automatically during DB initialization.
- Rollback support is available for latest migration(s).

## Commands

Run from project root using your venv Python:

```powershell
.venv\Scripts\python.exe -m src.database.db_maintenance status
.venv\Scripts\python.exe -m src.database.db_maintenance migrate
.venv\Scripts\python.exe -m src.database.db_maintenance backup --reason manual
.venv\Scripts\python.exe -m src.database.db_maintenance rollback --steps 1
```

## Operational Notes

- This works fully offline on a manager's computer.
- Backups are local files; no cloud service is required.
- Keep external copies (USB/network share) if you need disaster recovery beyond the local machine.
