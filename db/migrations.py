import datetime
import sqlite3
from typing import Optional

MIGRATIONS = [
    {
        "version": 1,
        "description": "Base schema (hackathons, users, filters, notified)",
        "sql": """
        CREATE TABLE IF NOT EXISTS hackathons (
            fingerprint TEXT PRIMARY KEY,
            name TEXT,
            deadline TEXT,
            source TEXT,
            link TEXT
        );
        CREATE TABLE IF NOT EXISTS users (
            chat_id TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS filters (
            chat_id TEXT,
            keyword TEXT
        );
        CREATE TABLE IF NOT EXISTS notified (
            chat_id TEXT,
            fingerprint TEXT,
            PRIMARY KEY (chat_id, fingerprint)
        );
        """,
    },
    {
        "version": 2,
        "description": "Add metadata columns (description, tags, prize, location, created_at, updated_at, raw_data) and indices",
        "sql": None,
    },
    {
        "version": 3,
        "description": "Add date granularity (reg_starts_at, reg_ends_at, starts_at, ends_at, source_status, is_section_link)",
        "sql": None,
    },
    {
        "version": 4,
        "description": "Add benefits column for credit and perk discovery (SpecialBenefit JSON array)",
        "sql": None,
    },
]


def get_existing_columns(cursor, table_name: str) -> set:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def apply_migrations(conn: Optional[sqlite3.Connection] = None):
    """
    Applies explicit, repeatable schema migrations non-destructively.
    Preserves all existing tables, rows, and columns without data loss.
    """
    if conn is None:
        import db.store as store

        conn = store.conn

    cursor = conn.cursor()

    # Migration tracker table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT,
        description TEXT
    )
    """)
    conn.commit()

    # Check applied versions
    cursor.execute("SELECT version FROM schema_migrations")
    applied_versions = {row[0] for row in cursor.fetchall()}

    # Migration 1: Base schema
    if 1 not in applied_versions:
        cursor.executescript(MIGRATIONS[0]["sql"])
        cursor.execute(
            "INSERT INTO schema_migrations VALUES (?, ?, ?)",
            (1, datetime.datetime.now(datetime.timezone.utc).isoformat(), MIGRATIONS[0]["description"]),
        )
        conn.commit()

    # Migration 2: Metadata columns on hackathons table
    if 2 not in applied_versions:
        cols = get_existing_columns(cursor, "hackathons")
        new_columns = [
            ("description", "TEXT DEFAULT ''"),
            ("tags", "TEXT DEFAULT '[]'"),
            ("prize", "TEXT DEFAULT 'Unknown'"),
            ("location", "TEXT DEFAULT 'Online'"),
            ("created_at", "TEXT DEFAULT ''"),
            ("updated_at", "TEXT DEFAULT ''"),
            ("raw_data", "TEXT DEFAULT '{}'"),
        ]
        for col_name, col_type in new_columns:
            if col_name not in cols:
                cursor.execute(f"ALTER TABLE hackathons ADD COLUMN {col_name} {col_type}")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hackathons_link ON hackathons(link)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hackathons_source ON hackathons(source)")

        cursor.execute(
            "INSERT INTO schema_migrations VALUES (?, ?, ?)",
            (2, datetime.datetime.now(datetime.timezone.utc).isoformat(), MIGRATIONS[1]["description"]),
        )
        conn.commit()

    # Migration 3: Granular date boundaries and section navigation distinction
    if 3 not in applied_versions:
        cols = get_existing_columns(cursor, "hackathons")
        v3_columns = [
            ("reg_starts_at", "TEXT DEFAULT ''"),
            ("reg_ends_at", "TEXT DEFAULT ''"),
            ("starts_at", "TEXT DEFAULT ''"),
            ("ends_at", "TEXT DEFAULT ''"),
            ("source_status", "TEXT DEFAULT ''"),
            ("is_section_link", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in v3_columns:
            if col_name not in cols:
                cursor.execute(f"ALTER TABLE hackathons ADD COLUMN {col_name} {col_type}")

        # Mark historical Devfolio section navigation links non-destructively
        cursor.execute("""
        UPDATE hackathons
        SET is_section_link = 1
        WHERE source = 'Devfolio'
          AND (
            link LIKE '%/hackathons/applied%'
            OR link LIKE '%/hackathons/open%'
            OR link LIKE '%/hackathons/upcoming%'
            OR link LIKE '%/hackathons/past%'
            OR lower(name) IN ('your hackathons', 'all open hackathons', 'all upcoming hackathons', 'all past hackathons')
          )
        """)

        cursor.execute(
            "INSERT INTO schema_migrations VALUES (?, ?, ?)",
            (3, datetime.datetime.now(datetime.timezone.utc).isoformat(), MIGRATIONS[2]["description"]),
        )
        conn.commit()

    # Migration 4: Special benefits column
    if 4 not in applied_versions:
        cols = get_existing_columns(cursor, "hackathons")
        if "benefits" not in cols:
            cursor.execute("ALTER TABLE hackathons ADD COLUMN benefits TEXT DEFAULT '[]'")

        cursor.execute(
            "INSERT INTO schema_migrations VALUES (?, ?, ?)",
            (4, datetime.datetime.now(datetime.timezone.utc).isoformat(), MIGRATIONS[3]["description"]),
        )
        conn.commit()

    return True
