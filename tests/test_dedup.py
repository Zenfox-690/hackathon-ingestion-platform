import hashlib
import sqlite3

import pytest

import db.store as store


@pytest.fixture
def temp_db(monkeypatch):
    """Provide an isolated in-memory SQLite database for deduplication testing."""
    mem_conn = sqlite3.connect(":memory:")
    mem_cursor = mem_conn.cursor()

    mem_cursor.execute("""
    CREATE TABLE hackathons (
        fingerprint TEXT PRIMARY KEY,
        name TEXT,
        deadline TEXT,
        source TEXT,
        link TEXT
    )
    """)
    mem_conn.commit()

    # Monkeypatch module-level conn and cursor
    monkeypatch.setattr(store, "conn", mem_conn)
    monkeypatch.setattr(store, "cursor", mem_cursor)

    yield mem_conn, mem_cursor

    mem_conn.close()


def test_repeated_ingestion_creates_zero_duplicates(temp_db):
    mem_conn, mem_cursor = temp_db

    hackathons = [
        {
            "name": "Global AI Hackathon",
            "deadline": "2026-07-01T00:00:00",
            "source": "Devpost",
            "link": "https://global-ai.devpost.com",
        },
        {
            "name": "Campus Codefest",
            "deadline": "2026-08-15T00:00:00",
            "source": "Unstop",
            "link": "https://unstop.com/hackathons/campus-codefest-12345",
        },
    ]

    # First ingestion run: both should be detected as new
    first_run = store.get_new_hackathons(hackathons)
    assert len(first_run) == 2

    count = mem_cursor.execute("SELECT COUNT(*) FROM hackathons").fetchone()[0]
    assert count == 2

    # Second ingestion run with exact same data: should return 0 new
    second_run = store.get_new_hackathons(hackathons)
    assert len(second_run) == 0

    count_after = mem_cursor.execute("SELECT COUNT(*) FROM hackathons").fetchone()[0]
    assert count_after == 2


def test_canonical_url_variations_do_not_duplicate(temp_db):
    mem_conn, mem_cursor = temp_db

    item_with_slash = [
        {"name": "Devfolio Hack", "deadline": "Unknown", "source": "Devfolio", "link": "https://myhack.devfolio.co/"}
    ]

    run1 = store.get_new_hackathons(item_with_slash)
    assert len(run1) == 1

    # Second run without slash and with tracking param
    item_with_query = [
        {
            "name": "Devfolio Hack",
            "deadline": "Unknown",
            "source": "Devfolio",
            "link": "https://myhack.devfolio.co?utm_source=telegram",
        }
    ]

    run2 = store.get_new_hackathons(item_with_query)
    assert len(run2) == 0

    total_rows = mem_cursor.execute("SELECT COUNT(*) FROM hackathons").fetchone()[0]
    assert total_rows == 1


def test_legacy_record_recognized_without_duplication(temp_db):
    mem_conn, mem_cursor = temp_db

    # Insert an old-style record where deadline is unparsed string and fingerprint was name+deadline
    name = "Old Hackathon"
    old_deadline = "May 05 - Jun 11, 2026"
    link = "https://oldhack.devpost.com/"
    legacy_fp = hashlib.sha256((name.lower().strip() + old_deadline.lower().strip()).encode()).hexdigest()

    mem_cursor.execute(
        "INSERT INTO hackathons VALUES (?, ?, ?, ?, ?)", (legacy_fp, name, old_deadline, "Devpost", link)
    )
    mem_conn.commit()

    # Now run ingestion for the same event with normalized deadline and canonical link
    new_version = [
        {"name": name, "deadline": "2026-06-11T00:00:00", "source": "Devpost", "link": "https://oldhack.devpost.com"}
    ]

    new_items = store.get_new_hackathons(new_version)
    assert len(new_items) == 0

    total = mem_cursor.execute("SELECT COUNT(*) FROM hackathons").fetchone()[0]
    assert total == 1
