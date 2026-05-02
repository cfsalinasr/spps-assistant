"""SQLite implementation of the DatabaseRepository port."""

import csv
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from spps_assistant.application.ports import DatabaseRepository
from spps_assistant.domain.models import ResidueInfo

# Default DB location
_DB_DIR = Path.home() / '.spps_assistant'
_DB_PATH = _DB_DIR / 'spps_database.db'


def _get_connection(db_path: Path = _DB_PATH) -> sqlite3.Connection:
    """Open (or create) the SQLite database and return a Row-factory connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(db_path: Path = _DB_PATH) -> None:
    """Create all tables if they do not already exist."""
    conn = _get_connection(db_path)
    try:
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS residue_mw (
                    token        TEXT PRIMARY KEY,
                    base_code    TEXT NOT NULL,
                    protection   TEXT NOT NULL DEFAULT '',
                    fmoc_mw      REAL NOT NULL,
                    free_mw      REAL NOT NULL,
                    stock_conc   REAL NOT NULL DEFAULT 0.5,
                    notes        TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS synthesis_defaults (
                    key          TEXT PRIMARY KEY,
                    value        TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS synthesis_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    synthesis_name  TEXT NOT NULL,
                    run_date        TEXT NOT NULL,
                    metadata_json   TEXT NOT NULL DEFAULT '{}'
                );
            """)
        # Migration: add density_g_ml to existing databases that predate this column
        try:
            conn.execute(
                "ALTER TABLE residue_mw ADD COLUMN density_g_ml REAL DEFAULT NULL"
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
    finally:
        conn.close()


# Auto-initialize on module import
_init_db()


class SQLiteRepository(DatabaseRepository):
    """SQLite-backed implementation of DatabaseRepository.

    Uses ~/.spps_assistant/spps_database.db by default.
    """

    def __init__(self, db_path: Path = _DB_PATH):
        """Initialise the repository and ensure the schema exists."""
        self._db_path = Path(db_path)
        _init_db(self._db_path)

    def _conn(self) -> sqlite3.Connection:
        """Return a fresh database connection for this repository instance."""
        return _get_connection(self._db_path)

    # ------------------------------------------------------------------ #
    # Residue MW operations                                                #
    # ------------------------------------------------------------------ #

    def save_residue(
        self,
        token: str,
        base_code: str,
        protection: str,
        fmoc_mw: float,
        free_mw: float,
        stock_conc: float = 0.5,
        notes: str = '',
        density_g_ml: Optional[float] = None,
    ) -> None:
        """Upsert a residue MW record."""
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO residue_mw
                        (token, base_code, protection, fmoc_mw, free_mw,
                         stock_conc, notes, density_g_ml)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(token) DO UPDATE SET
                        base_code    = excluded.base_code,
                        protection   = excluded.protection,
                        fmoc_mw      = excluded.fmoc_mw,
                        free_mw      = excluded.free_mw,
                        stock_conc   = excluded.stock_conc,
                        notes        = excluded.notes,
                        density_g_ml = excluded.density_g_ml
                    """,
                    (token, base_code, protection, fmoc_mw, free_mw,
                     stock_conc, notes, density_g_ml),
                )
        finally:
            conn.close()

    def get_residue(self, token: str) -> Optional[ResidueInfo]:
        """Retrieve ResidueInfo by exact token match."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM residue_mw WHERE token = ?", (token,)
            ).fetchone()
            if row is None:
                return None
            return ResidueInfo(
                token=row['token'],
                base_code=row['base_code'],
                protection=row['protection'],
                fmoc_mw=row['fmoc_mw'],
                free_mw=row['free_mw'],
                stock_conc=row['stock_conc'],
            )
        finally:
            conn.close()

    def list_residues(self) -> List[Dict[str, Any]]:
        """Return all residue records as list of dicts."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM residue_mw ORDER BY token"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Defaults                                                             #
    # ------------------------------------------------------------------ #

    def save_default(self, key: str, value: str) -> None:
        """Upsert a key/value synthesis default."""
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO synthesis_defaults (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, str(value)),
                )
        finally:
            conn.close()

    def get_default(self, key: str) -> Optional[str]:
        """Retrieve a synthesis default value by key, or None if absent."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT value FROM synthesis_defaults WHERE key = ?", (key,)
            ).fetchone()
            return row['value'] if row else None
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Synthesis log                                                        #
    # ------------------------------------------------------------------ #

    def log_synthesis(self, synthesis_name: str, metadata: Dict[str, Any]) -> None:
        """Append a synthesis run record with today's date and JSON metadata."""
        today = date.today().isoformat()
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO synthesis_log (synthesis_name, run_date, metadata_json)
                    VALUES (?, ?, ?)
                    """,
                    (synthesis_name, today, json.dumps(metadata)),
                )
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Import / Export                                                      #
    # ------------------------------------------------------------------ #

    def export_csv(self, path: Path) -> None:
        """Export residue library to CSV."""
        path = Path(path)
        rows = self.list_residues()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['token', 'base_code', 'protection', 'fmoc_mw',
                            'free_mw', 'stock_conc', 'density_g_ml', 'notes'],
            )
            writer.writeheader()
            writer.writerows(rows)

    def import_csv(self, path: Path) -> int:
        """Import residue library from a CSV or XLSX file. Returns number of rows imported."""
        from spps_assistant.infrastructure.materials_parser import load_materials_file
        path = Path(path)
        records = load_materials_file(path)
        count = 0
        for rec in records:
            self.save_residue(
                token=rec['token'],
                base_code=rec['base_code'],
                protection=rec['protection'],
                fmoc_mw=rec['fmoc_mw'],
                free_mw=rec['free_mw'],
                stock_conc=rec.get('stock_conc', 0.5),
                notes=rec.get('notes', ''),
                density_g_ml=rec.get('density_g_ml'),
            )
            count += 1
        return count

    # ------------------------------------------------------------------ #
    # Reset                                                                #
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Drop all tables and recreate (destructive)."""
        conn = self._conn()
        try:
            with conn:
                conn.executescript("""
                    DROP TABLE IF EXISTS residue_mw;
                    DROP TABLE IF EXISTS synthesis_defaults;
                    DROP TABLE IF EXISTS synthesis_log;
                """)
        finally:
            conn.close()
        _init_db(self._db_path)
