import datetime
import json
import sqlite3
from datetime import timezone

import db.store as store
from db.migrations import apply_migrations
from exporter import export_public_catalog
from fetcher.devfolio import parse_devfolio_cards_from_html
from utils.dates import evaluate_hackathon_status, parse_iso_to_utc


def test_devfolio_extraction_from_next_data():
    """Verify that Devfolio Next.js __NEXT_DATA__ JSON script extracts real hackathon listings

    and excludes section navigation links.
    """
    next_data_payload = {
        "props": {
            "pageProps": {
                "dehydratedState": {
                    "queries": [
                        {
                            "queryKey": ["fetchAllHackathonTypes"],
                            "state": {
                                "data": {
                                    "open_hackathons": [
                                        {
                                            "name": "HackCBS 7.0",
                                            "slug": "hackcbs7",
                                            "hackathon_setting": {"is_online": False},
                                            "starts_at": "2026-11-05T09:00:00+05:30",
                                            "ends_at": "2026-11-06T18:00:00+05:30",
                                            "reg_starts_at": "2026-10-01T00:00:00+05:30",
                                            "reg_ends_at": "2026-10-25T23:59:59+05:30",
                                            "participants_count": 1200,
                                            "themes": ["Web3", "AI", "Open Innovation"],
                                        }
                                    ],
                                    "upcoming_hackathons": [
                                        {
                                            "name": "Future Builders 2026",
                                            "slug": "futurebuilders",
                                            "hackathon_setting": {"is_online": True},
                                            "starts_at": "2026-12-01T00:00:00Z",
                                            "ends_at": "2026-12-03T00:00:00Z",
                                            "reg_starts_at": "2026-11-01T00:00:00Z",
                                            "reg_ends_at": "2026-11-28T00:00:00Z",
                                            "participants_count": 450,
                                            "themes": ["FinTech"],
                                        }
                                    ],
                                    "past_hackathons": [
                                        {
                                            "name": "Past Summer Hack",
                                            "slug": "pastsummer",
                                            "hackathon_setting": {"is_online": True},
                                            "starts_at": "2026-06-01T00:00:00Z",
                                            "ends_at": "2026-06-03T00:00:00Z",
                                            "reg_starts_at": "2026-05-01T00:00:00Z",
                                            "reg_ends_at": "2026-05-28T00:00:00Z",
                                            "participants_count": 800,
                                            "themes": [],
                                        }
                                    ],
                                }
                            },
                        }
                    ]
                }
            }
        }
    }

    synthetic_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script id="__NEXT_DATA__" type="application/json">
        {json.dumps(next_data_payload)}
        </script>
    </head>
    <body>
        <a href="/hackathons/applied"><h3>Your hackathons</h3></a>
        <a href="/hackathons/upcoming"><h3>All upcoming hackathons</h3></a>
    </body>
    </html>
    """

    extracted = parse_devfolio_cards_from_html(synthetic_html)
    assert len(extracted) == 3

    names = [h["name"] for h in extracted]
    links = [h["link"] for h in extracted]

    # Real listings must be present
    assert "HackCBS 7.0" in names
    assert "Future Builders 2026" in names
    assert "Past Summer Hack" in names

    # Section links must NOT be treated as hackathon items
    assert "Your hackathons" not in names
    assert "All upcoming hackathons" not in names

    # Verified proper link generation
    assert "https://hackcbs7.devfolio.co" in links
    assert "https://futurebuilders.devfolio.co" in links

    # Metadata validation
    h1 = next(h for h in extracted if h["name"] == "HackCBS 7.0")
    assert h1["source"] == "Devfolio"
    assert h1["location"] == "In-Person"
    assert "web3" in h1["tags"]
    assert h1["reg_ends_at"] == "2026-10-25T23:59:59+05:30"
    assert parse_iso_to_utc(h1["reg_ends_at"]) == datetime.datetime(2026, 10, 25, 18, 29, 59, tzinfo=timezone.utc)


def test_date_boundary_and_status_evaluation():
    """Verify that evaluate_hackathon_status handles timezone offsets, date boundaries,

    active registration, future registration, expired deadlines, and unknown dates correctly.
    """
    now = datetime.datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Open: reg_ends_at is in the future, reg_starts_at in the past
    status_open = evaluate_hackathon_status(
        reg_ends_at="2026-10-20T00:00:00Z", reg_starts_at="2026-10-01T00:00:00Z", as_of=now
    )
    assert status_open == "open"

    # 2. Upcoming (registration has not started yet)
    status_upcoming = evaluate_hackathon_status(
        reg_ends_at="2026-11-20T00:00:00Z", reg_starts_at="2026-11-01T00:00:00Z", as_of=now
    )
    assert status_upcoming == "upcoming"

    # 3. Ended (registration ended 1 second ago)
    status_ended = evaluate_hackathon_status(reg_ends_at="2026-10-17T11:59:59Z", as_of=now)
    assert status_ended == "ended"

    # 4. Timezone offset test:
    # 2026-10-17 17:00:00+05:30 is 11:30:00 UTC (30 minutes in the past relative to 12:00 UTC) -> ended
    status_tz_ended = evaluate_hackathon_status(reg_ends_at="2026-10-17T17:00:00+05:30", as_of=now)
    assert status_tz_ended == "ended"

    # 2026-10-17 18:00:00+05:30 is 12:30:00 UTC (30 minutes in the future relative to 12:00 UTC) -> open
    status_tz_open = evaluate_hackathon_status(reg_ends_at="2026-10-17T18:00:00+05:30", as_of=now)
    assert status_tz_open == "open"

    # 5. Unknown dates: never falsely claim open or upcoming
    status_unknown = evaluate_hackathon_status(reg_ends_at=None, deadline="Unknown", as_of=now)
    assert status_unknown == "unknown"


def test_stale_records_reclassified_at_query_time(tmp_path):
    """Test that a record entered into SQLite earlier with a past deadline is evaluated

    dynamically as 'ended' at query/export time, preserving historical rows.
    """
    test_db = str(tmp_path / "test_stale.db")
    conn = sqlite3.connect(test_db)
    apply_migrations(conn)

    # Insert an expired record from June 2026 and an active record for November 2026
    expired_item = {
        "name": "Past Spring Hack 2026",
        "link": "https://past-spring.devpost.com",
        "source": "Devpost",
        "deadline": "2026-06-15T00:00:00Z",
        "reg_ends_at": "2026-06-15T00:00:00Z",
        "reg_starts_at": "2026-05-01T00:00:00Z",
        "starts_at": "2026-06-20T00:00:00Z",
        "ends_at": "2026-06-22T00:00:00Z",
        "description": "Historical event",
        "tags": ["AI"],
        "prize": "$10,000",
        "location": "Online",
    }

    active_item = {
        "name": "Active Autumn Hack 2026",
        "link": "https://active-autumn.devpost.com",
        "source": "Devpost",
        "deadline": "2026-11-15T00:00:00Z",
        "reg_ends_at": "2026-11-15T00:00:00Z",
        "reg_starts_at": "2026-10-01T00:00:00Z",
        "starts_at": "2026-11-20T00:00:00Z",
        "ends_at": "2026-11-22T00:00:00Z",
        "description": "Active event",
        "tags": ["Cloud"],
        "prize": "$20,000",
        "location": "Online",
    }

    # Store items
    store.get_new_hackathons([expired_item, active_item], conn_override=conn)

    # Query public hackathons as of October 17, 2026
    records = store.get_all_public_hackathons(conn_override=conn)
    assert len(records) == 2

    expired_record = next(r for r in records if r["name"] == "Past Spring Hack 2026")
    active_record = next(r for r in records if r["name"] == "Active Autumn Hack 2026")

    # Invariant: Expired record must be dynamically classified as 'ended'
    assert expired_record["status"] == "ended"
    # Invariant: Active record must be classified as 'open'
    assert active_record["status"] == "open"

    conn.close()


def test_section_links_segregated_from_public_listings(tmp_path):
    """Verify that section navigation links (e.g.

    'All open hackathons') are flagged as section links, excluded from standard hackathons, and
    exposed as supplementary_links.
    """
    test_db = str(tmp_path / "test_sections.db")
    conn = sqlite3.connect(test_db)
    apply_migrations(conn)

    section_nav = {
        "name": "All open hackathons",
        "link": "https://devfolio.co/hackathons/open",
        "source": "Devfolio",
        "deadline": "Unknown",
        "is_section_link": True,
    }
    real_hack = {
        "name": "Live Devfolio Hack",
        "link": "https://livedevfolio.devfolio.co",
        "source": "Devfolio",
        "deadline": "2026-11-01T00:00:00Z",
        "reg_ends_at": "2026-11-01T00:00:00Z",
        "is_section_link": False,
    }

    store.get_new_hackathons([section_nav, real_hack], conn_override=conn)

    # Standard public list should ONLY contain real_hack
    public_records = store.get_all_public_hackathons(conn_override=conn)
    assert len(public_records) == 1
    assert public_records[0]["name"] == "Live Devfolio Hack"

    # Supplementary links should return the navigation section
    supp_links = store.get_supplementary_links(conn_override=conn)
    assert len(supp_links) == 1
    assert supp_links[0]["name"] == "All open hackathons"
    assert supp_links[0]["url"] == "https://devfolio.co/hackathons/open"

    conn.close()


def test_export_catalog_with_dynamic_sorting(tmp_path, monkeypatch):
    """Verify that export_public_catalog exports both actionable and past hackathons,

    places actionable opportunities first, and includes supplementary portal links.
    """
    test_db = str(tmp_path / "test_export.db")
    conn = sqlite3.connect(test_db)
    apply_migrations(conn)

    # Seed 1 expired, 1 active, 1 section link
    items = [
        {
            "name": "Expired Hack",
            "link": "https://expired.devpost.com",
            "source": "Devpost",
            "deadline": "2026-06-01T00:00:00Z",
            "reg_ends_at": "2026-06-01T00:00:00Z",
        },
        {
            "name": "Actionable Hack",
            "link": "https://actionable.devfolio.co",
            "source": "Devfolio",
            "deadline": "2026-11-01T00:00:00Z",
            "reg_ends_at": "2026-11-01T00:00:00Z",
        },
        {
            "name": "All upcoming hackathons",
            "link": "https://devfolio.co/hackathons/upcoming",
            "source": "Devfolio",
            "deadline": "Unknown",
            "is_section_link": True,
        },
    ]
    store.get_new_hackathons(items, conn_override=conn)

    out_file = str(tmp_path / "catalog.json")

    catalog = export_public_catalog(output_path=out_file, conn_override=conn)

    assert catalog["metadata"]["total_count"] == 2  # section links excluded
    assert catalog["metadata"]["open_count"] == 1
    assert catalog["metadata"]["ended_count"] == 1
    assert len(catalog["metadata"]["supplementary_links"]) == 1

    # First hackathon must be actionable, not expired
    assert catalog["hackathons"][0]["name"] == "Actionable Hack"
    assert catalog["hackathons"][0]["status"] == "open"
    assert catalog["hackathons"][1]["name"] == "Expired Hack"
    assert catalog["hackathons"][1]["status"] == "ended"

    conn.close()
