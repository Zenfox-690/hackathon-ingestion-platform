import json
import sqlite3

import pytest

import db.store as store
from db.migrations import apply_migrations, get_existing_columns
from models.hackathon import Hackathon, HackathonStatus


def test_model_normalization_and_validation():
    # Valid hackathon with messy URL, date, and tags
    h = Hackathon(
        name="  AI Future Hackathon  ",
        link="https://ai-future.devpost.com/?utm_source=twitter&ref=123#about",
        source="Devpost",
        deadline="Jun 15, 2026",
        tags="ai, web3, ai, python",
        prize="  $25,000 USD  ",
    )

    assert h.name == "AI Future Hackathon"
    assert h.title == "AI Future Hackathon"
    assert h.link == "https://ai-future.devpost.com"
    assert h.url == "https://ai-future.devpost.com"
    assert h.deadline == "2026-06-15T00:00:00"
    assert h.tags == ["ai", "python", "web3"]
    assert h.prize == "$25,000 USD"
    assert h.location == "Online"
    assert len(h.fingerprint) == 64
    assert h.id == h.fingerprint
    assert h.status in (HackathonStatus.OPEN, HackathonStatus.UPCOMING, HackathonStatus.ENDED)


def test_model_invalid_inputs():
    with pytest.raises(ValueError):
        Hackathon(name="", link="https://devpost.com", source="Devpost")

    with pytest.raises(ValueError):
        Hackathon(name="Hack", link="", source="Devpost")


def test_migration_from_legacy_to_v2():
    # Setup legacy schema with rows
    mem_conn = sqlite3.connect(":memory:")
    c = mem_conn.cursor()
    c.execute("""
    CREATE TABLE hackathons (
        fingerprint TEXT PRIMARY KEY,
        name TEXT,
        deadline TEXT,
        source TEXT,
        link TEXT
    )
    """)
    c.execute("""
    INSERT INTO hackathons VALUES (
        'fp-legacy-1', 'Legacy Hack', 'May 05 - Jun 11, 2026', 'Devpost', 'https://legacy.devpost.com'
    )
    """)
    mem_conn.commit()

    # Verify initial columns
    initial_cols = get_existing_columns(c, "hackathons")
    assert "description" not in initial_cols
    assert "prize" not in initial_cols

    # Apply migration
    success = apply_migrations(mem_conn)
    assert success is True

    # Verify upgraded columns exist
    upgraded_cols = get_existing_columns(c, "hackathons")
    assert "description" in upgraded_cols
    assert "tags" in upgraded_cols
    assert "prize" in upgraded_cols
    assert "location" in upgraded_cols
    assert "created_at" in upgraded_cols
    assert "updated_at" in upgraded_cols
    assert "raw_data" in upgraded_cols

    # Verify legacy row is preserved intact
    row = c.execute(
        "SELECT fingerprint, name, deadline, source, link, prize FROM hackathons WHERE fingerprint = 'fp-legacy-1'"
    ).fetchone()
    assert row[0] == "fp-legacy-1"
    assert row[1] == "Legacy Hack"
    assert row[2] == "May 05 - Jun 11, 2026"
    assert row[3] == "Devpost"
    assert row[4] == "https://legacy.devpost.com"
    assert row[5] == "Unknown"  # Default value applied

    # Migration is idempotent
    success2 = apply_migrations(mem_conn)
    assert success2 is True
    mem_conn.close()


def test_metadata_enrichment_on_duplicate_ingestion(monkeypatch):
    mem_conn = sqlite3.connect(":memory:")
    apply_migrations(mem_conn)
    mem_cursor = mem_conn.cursor()

    monkeypatch.setattr(store, "conn", mem_conn)
    monkeypatch.setattr(store, "cursor", mem_cursor)

    # Initial ingestion with missing prize and description
    h1 = [
        {
            "name": "Enrichment Challenge",
            "deadline": "2026-07-01T00:00:00",
            "source": "Devpost",
            "link": "https://enrich.devpost.com",
            "prize": "Unknown",
            "description": "",
        }
    ]

    new1 = store.get_new_hackathons(h1)
    assert len(new1) == 1

    # Second ingestion discovers prize and description
    h2 = [
        {
            "name": "Enrichment Challenge",
            "deadline": "2026-07-01T00:00:00",
            "source": "Devpost",
            "link": "https://enrich.devpost.com",
            "prize": "$50,000",
            "description": "Build next-gen AI systems",
        }
    ]

    new2 = store.get_new_hackathons(h2)
    # Must NOT report as new (no new notification spam)
    assert len(new2) == 0

    # But database record MUST be enriched
    row = mem_cursor.execute(
        "SELECT prize, description FROM hackathons WHERE link = 'https://enrich.devpost.com'"
    ).fetchone()
    assert row[0] == "$50,000"
    assert row[1] == "Build next-gen AI systems"

    mem_conn.close()


def test_public_boundary_excludes_private_bot_data(monkeypatch):
    mem_conn = sqlite3.connect(":memory:")
    apply_migrations(mem_conn)
    mem_cursor = mem_conn.cursor()

    monkeypatch.setattr(store, "conn", mem_conn)
    monkeypatch.setattr(store, "cursor", mem_cursor)

    # Insert private bot data
    store.add_user("chat_id_secret_999")
    store.add_filter("chat_id_secret_999", "secret_filter")
    store.mark_notified("chat_id_secret_999", "secret_fp_123")

    # Insert public hackathon
    store.get_new_hackathons(
        [
            {
                "name": "Public Event",
                "deadline": "2026-08-01T00:00:00",
                "source": "Unstop",
                "link": "https://unstop.com/hackathons/public-event",
            }
        ]
    )

    public_records = store.get_all_public_hackathons()
    assert len(public_records) == 1
    record = public_records[0]

    # Verify no private keys or data are present
    assert "chat_id" not in record
    assert "keyword" not in record
    assert "users" not in record
    assert "filters" not in record

    # Check serialized JSON
    catalog_json = json.dumps(public_records)
    assert "chat_id_secret_999" not in catalog_json
    assert "secret_filter" not in catalog_json

    mem_conn.close()
