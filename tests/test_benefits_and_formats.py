import json
import sqlite3

from api.adapter import HackathonDataAdapter
from db.migrations import apply_migrations
from exporter import build_catalog_payload, merge_hackathon_records
from filters.benefits import extract_special_benefits
from models.hackathon import Hackathon
from utils.format import normalize_participation_format


def test_format_normalization_online():
    assert normalize_participation_format("Online") == "Online"
    assert normalize_participation_format("Virtual Event") == "Online"
    assert normalize_participation_format("", "Join us online via Discord") == "Online"
    assert normalize_participation_format("remote worldwide") == "Online"


def test_format_normalization_in_person():
    assert normalize_participation_format("San Francisco, CA, USA") == "In-Person"
    assert normalize_participation_format("In-Person") == "In-Person"
    assert normalize_participation_format("Offline") == "In-Person"
    assert normalize_participation_format("Campus Auditorium, IIT Delhi") == "In-Person"
    assert normalize_participation_format("", "Venue: Bangalore Tech Center") == "In-Person"


def test_format_normalization_hybrid():
    assert normalize_participation_format("Hybrid (Online + London)") == "Hybrid"
    assert normalize_participation_format("Hybrid") == "Hybrid"
    assert (
        normalize_participation_format("", "This is a hybrid event with both in-person and virtual tracks") == "Hybrid"
    )


def test_format_normalization_unknown():
    assert normalize_participation_format("") == "Unknown"
    assert normalize_participation_format("TBD") == "Unknown"
    assert normalize_participation_format("To Be Announced") == "Unknown"
    assert normalize_participation_format("N/A") == "Unknown"
    # An online platform listing with no location hint must NOT silently assume Online
    assert normalize_participation_format(None, "Hackathon without format mentions") == "Unknown"


def test_benefit_extraction_aws_with_separate_form():
    text = (
        "All accepted teams receive $5,000 AWS Activate credits. "
        "Apply for your AWS credits voucher using this form: https://forms.gle/aws-voucher-2026. "
        "Separate credits application deadline is November 15, 2026."
    )
    benefits = extract_special_benefits(
        text=text,
        event_name="AWS Cloud Hackathon",
        source_url="https://devpost.com/hackathons/aws-hack",
        hackathon_deadline="2026-12-01T00:00:00Z",
    )

    assert len(benefits) == 1
    b = benefits[0]
    assert b.name == "AWS Cloud Credits"
    assert b.category in ("Cloud Credits", "cloud_credits")
    assert "$5,000" in b.description
    assert b.requires_separate_application is True
    assert b.application_url == "https://forms.gle/aws-voucher-2026"
    assert b.source_url == "https://devpost.com/hackathons/aws-hack"
    # Verified deadline from text, distinct from hackathon deadline
    assert b.application_deadline is not None
    assert "2026-11-15" in b.application_deadline
    assert b.application_deadline != "2026-12-01T00:00:00Z"
    assert b.confidence == "verified"


def test_benefit_extraction_google_cloud_and_unknown_deadline():
    text = (
        "Google Cloud is providing Gemini API and Vertex AI credits to all builders. "
        "No separate application required, vouchers will be sent on Discord."
    )
    benefits = extract_special_benefits(
        text=text,
        event_name="AI Builders Sprint",
        source_url="https://devpost.com/hackathons/ai-sprint",
        hackathon_deadline="2026-11-01T00:00:00Z",
    )

    assert len(benefits) == 1
    b = benefits[0]
    assert b.name == "Google Cloud Credits"
    assert b.category in ("Cloud Credits", "cloud_credits")
    assert b.requires_separate_application is False
    # Main hackathon deadline must NEVER be copied into application_deadline
    assert b.application_deadline is None
    assert b.application_url is None
    assert b.source_url == "https://devpost.com/hackathons/ai-sprint"


def test_benefit_extraction_multi_provider():
    text = (
        "Sponsors provide $1,000 AWS credits for cloud hosting, "
        "plus $500 OpenAI API credits for top 20 teams, and GitHub Student Developer Pack perks."
    )
    benefits = extract_special_benefits(
        text=text,
        event_name="Mega Hack 2026",
        source_url="https://devfolio.co/megahack",
    )

    assert len(benefits) >= 3
    names = [b.name for b in benefits]
    assert any("AWS" in n for n in names)
    assert any("OpenAI" in n for n in names)
    assert any("GitHub" in n for n in names)


def test_benefit_extraction_no_benefits_found():
    text = "Join us for a 24-hour coding competition with great mentoring and free pizza."
    benefits = extract_special_benefits(
        text=text,
        event_name="Local Hack",
        source_url="https://unstop.com/hackathons/local-hack",
    )
    # Must return empty list, not hallucinated benefits
    assert benefits == []


def test_canonical_model_with_benefits_and_format():
    h = Hackathon(
        id="test-benefit-id",
        name="Cloud Builders 2026",
        link="https://devpost.com/hackathons/cloud-builders",
        source="Devpost",
        location="Virtual / Zoom",
        description="Build on Azure with $1,000 Azure sponsorship credits.",
    )

    # location normalized to canonical 'Online'
    assert h.location == "Online"
    # benefits automatically extracted from description
    assert len(h.benefits) == 1
    assert "Azure" in h.benefits[0].name

    data = h.to_dict()
    assert data["location"] == "Online"
    assert len(data["benefits"]) == 1
    assert data["benefits"][0]["name"] == "Microsoft Azure Credits"


def test_database_migration_v4_and_persistence(tmp_path):
    db_file = str(tmp_path / "test_migration.db")
    conn = sqlite3.connect(db_file)
    apply_migrations(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT MAX(version) FROM schema_migrations")
    assert cursor.fetchone()[0] >= 4
    cursor.execute("PRAGMA table_info(hackathons)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "benefits" in columns

    # Insert a record with JSON benefits
    benefits_json = json.dumps(
        [
            {
                "id": "b-1",
                "name": "AWS Cloud Credits",
                "category": "cloud_credits",
                "description": "$5,000 AWS credits",
                "requires_separate_application": True,
                "application_deadline": "2026-11-15T00:00:00Z",
                "application_url": "https://forms.gle/test",
                "source_url": "https://devpost.com/test",
                "eligibility": "Students",
                "confidence": "verified",
            }
        ]
    )
    cursor.execute(
        """
        INSERT INTO hackathons (fingerprint, name, link, source, deadline, location, benefits)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mig-test-1",
            "Migration Test Hack",
            "https://devpost.com/mig",
            "Devpost",
            "2026-12-01",
            "Online",
            benefits_json,
        ),
    )
    conn.commit()

    # Query back
    cursor.execute("SELECT benefits FROM hackathons WHERE fingerprint = ?", ("mig-test-1",))
    row = cursor.fetchone()
    stored = json.loads(row[0])
    assert len(stored) == 1
    assert stored[0]["name"] == "AWS Cloud Credits"
    conn.close()


def test_exporter_formats_and_benefits_payload():
    records = [
        {
            "id": "exp-1",
            "name": "Online AI Hack",
            "link": "https://devpost.com/1",
            "source": "Devpost",
            "location": "Online",
            "status": "open",
            "benefits": [
                {
                    "name": "AWS Credits",
                    "category": "cloud_credits",
                    "description": "$2,000 credits",
                    "requires_separate_application": False,
                    "application_deadline": None,
                    "confidence": "verified",
                }
            ],
        },
        {
            "id": "exp-2",
            "name": "In-Person London Hack",
            "link": "https://devfolio.co/2",
            "source": "Devfolio",
            "location": "London, UK",  # Raw location to be normalized
            "status": "upcoming",
            "benefits": [],
        },
    ]

    payload = build_catalog_payload(records)
    meta = payload["metadata"]

    assert meta["total_count"] == 2
    assert meta["formats"]["Online"] == 1
    assert meta["formats"]["In-Person"] == 1
    assert meta["benefits_count"] == 1

    hacks = payload["hackathons"]
    assert hacks[0]["location"] == "Online"
    assert len(hacks[0]["benefits"]) == 1
    assert hacks[1]["location"] == "In-Person"
    assert len(hacks[1]["benefits"]) == 0


def test_merge_hackathon_records_preserves_benefits():
    baseline = [
        {
            "id": "m-1",
            "name": "Hack Baseline",
            "link": "https://devpost.com/m1",
            "source": "Devpost",
            "location": "Online",
            "status": "open",
            "benefits": [
                {
                    "name": "AWS Cloud Credits",
                    "category": "cloud_credits",
                    "description": "$5k credits",
                    "requires_separate_application": False,
                    "application_deadline": None,
                    "confidence": "verified",
                }
            ],
        }
    ]
    # Incoming record has no benefits field populated
    incoming = [
        {
            "id": "m-1",
            "name": "Hack Baseline Updated",
            "link": "https://devpost.com/m1",
            "source": "Devpost",
            "location": "Online",
            "status": "open",
        }
    ]

    merged = merge_hackathon_records(baseline, incoming)
    assert len(merged) == 1
    # Preserves baseline benefits rather than overwriting with empty
    assert len(merged[0]["benefits"]) == 1
    assert merged[0]["benefits"][0]["name"] == "AWS Cloud Credits"


def test_api_adapter_format_and_benefit_query():
    # Adapter query with format parameter
    total, _, items = HackathonDataAdapter.query(format="Online", limit=50)
    for it in items:
        assert it["location"] == "Online"

    total_ip, _, items_ip = HackathonDataAdapter.query(format="In-Person", limit=50)
    for it in items_ip:
        assert it["location"] == "In-Person"

    stats = HackathonDataAdapter.get_stats()
    assert "formats" in stats
    assert "total_benefits" in stats
    assert stats["formats"]["Online"] >= 0
