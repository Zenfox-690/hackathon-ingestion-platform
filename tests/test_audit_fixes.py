import datetime
from datetime import timezone

from exporter import (
    build_catalog_payload,
    merge_hackathon_records,
    validate_catalog_payload,
)
from fetcher.base import BaseFetcher
from fetcher.unstop import parse_unstop_cards_from_html
from filters.benefits import extract_special_benefits
from pipeline import IngestionPipeline
from utils.dates import (
    evaluate_hackathon_status,
    normalize_date,
    parse_date_range,
)

# ==============================================================================
# Phase 1: Merging, Deduplication, and Catalog Validation
# ==============================================================================


def test_organiser_extending_deadline():
    """Verify that an organizer extending an existing deadline updates the record."""
    baseline = [
        {
            "id": "fp_original",
            "fingerprint": "fp_original",
            "name": "Global AI Challenge",
            "link": "https://devpost.com/software/global-ai",
            "source": "Devpost",
            "deadline": "2026-10-01T23:59:59",
            "prize": "$10,000",
            "status": "open",
        }
    ]

    # Incoming scrape shows extended deadline
    incoming = [
        {
            "id": "fp_new_extended",
            "fingerprint": "fp_new_extended",
            "name": "Global AI Challenge",
            "link": "https://devpost.com/software/global-ai",
            "source": "Devpost",
            "deadline": "2026-10-25T23:59:59",
            "prize": "$10,000",
        }
    ]

    merged = merge_hackathon_records(baseline, incoming)
    assert len(merged) == 1
    assert merged[0]["deadline"] == "2026-10-25T23:59:59"


def test_duplicate_link_with_changed_fingerprint_merges_cleanly():
    """Verify that records with identical canonical link merge even if fingerprints differ."""
    baseline = [
        {
            "id": "fp_111111",
            "fingerprint": "fp_111111",
            "name": "HackCBS 7.0",
            "link": "https://devfolio.co/hackcbs7?ref=newsletter",
            "source": "Devfolio",
            "deadline": "2026-11-01T00:00:00",
        }
    ]

    incoming = [
        {
            "id": "fp_222222",
            "fingerprint": "fp_222222",
            "name": "HackCBS 7.0 - The Annual Hackathon",
            "link": "https://devfolio.co/hackcbs7/",
            "source": "Devfolio",
            "deadline": "2026-11-05T00:00:00",
        }
    ]

    merged = merge_hackathon_records(baseline, incoming)
    assert len(merged) == 1
    assert merged[0]["link"] == "https://devfolio.co/hackcbs7"
    assert merged[0]["deadline"] == "2026-11-05T00:00:00"


def test_empty_incoming_values_do_not_overwrite_good_existing_data():
    """Verify that empty or Unknown incoming fields do not blank out good baseline data."""
    baseline = [
        {
            "id": "fp_rich",
            "fingerprint": "fp_rich",
            "name": "Rich Data Hackathon",
            "link": "https://devpost.com/rich-hack",
            "source": "Devpost",
            "deadline": "2026-10-15T00:00:00",
            "prize": "$50,000",
            "description": "Comprehensive event description.",
            "location": "In-Person",
        }
    ]

    # Incoming scrape returns missing/empty fields
    incoming = [
        {
            "id": "fp_rich",
            "fingerprint": "fp_rich",
            "name": "Rich Data Hackathon",
            "link": "https://devpost.com/rich-hack",
            "source": "Devpost",
            "deadline": "2026-10-15T00:00:00",
            "prize": "Unknown",
            "description": "",
            "location": "Unknown",
        }
    ]

    merged = merge_hackathon_records(baseline, incoming)
    assert len(merged) == 1
    rec = merged[0]
    assert rec["prize"] == "$50,000"
    assert rec["description"] == "Comprehensive event description."
    assert rec["location"] == "In-Person"


def test_stale_benefits_cleared_when_source_shows_no_benefits():
    """Do not retain stale benefits indefinitely when fresh check establishes claims are no longer supported."""
    baseline = [
        {
            "id": "fp_perk",
            "fingerprint": "fp_perk",
            "name": "Perk Hackathon",
            "link": "https://devpost.com/perk-hack",
            "source": "Devpost",
            "deadline": "2026-11-15T00:00:00",
            "benefits": [{"name": "Old Expired Credits", "confidence": "verified"}],
        }
    ]

    # Fresh incoming scrape with explicit empty benefits list
    incoming = [
        {
            "id": "fp_perk",
            "fingerprint": "fp_perk",
            "name": "Perk Hackathon",
            "link": "https://devpost.com/perk-hack",
            "source": "Devpost",
            "deadline": "2026-11-15T00:00:00",
            "benefits": [],
        }
    ]

    merged = merge_hackathon_records(baseline, incoming)
    assert len(merged) == 1
    assert merged[0]["benefits"] == []


def test_catalog_validation_detects_forbidden_sources_and_multiline_titles():
    """Verify deterministic catalogue validator rejects malformed entries."""
    invalid_payload = {
        "metadata": {
            "version": "1.0.0",
            "generated_at": "2026-10-17T00:00:00Z",
            "total_count": 2,
            "sources": {"Devpost": 1, "MockSuccessSource": 1},
            "formats": {"Online": 2},
        },
        "hackathons": [
            {
                "id": "h1",
                "name": "Multiline Title\nWith Newline",
                "link": "https://devpost.com/h1",
                "source": "Devpost",
                "status": "open",
                "location": "Online",
            },
            {
                "id": "h2",
                "name": "Reliable AI Hackathon",
                "link": "https://devpost.com/h2",
                "source": "MockSuccessSource",
                "status": "open",
                "location": "Online",
            },
        ],
    }

    errors = validate_catalog_payload(invalid_payload)
    assert any("Forbidden source" in e for e in errors)
    assert any("multiline title" in e for e in errors)
    assert any("test fixture" in e for e in errors)


# ==============================================================================
# Phase 2: Date Handling, Status Freshness, and Unstop Extraction
# ==============================================================================


def test_date_only_deadlines_are_treated_as_end_of_day():
    """Date-only deadline like 2026-10-15 must not expire at 00:00:01 on October 15."""
    # Reference clock: October 15, 2026 at 12:00:00 UTC (middle of the deadline day)
    midday = datetime.datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    status_midday = evaluate_hackathon_status(deadline="2026-10-15", as_of=midday)
    assert status_midday == "open", "Date-only deadline must remain OPEN throughout the deadline day"

    # Reference clock: October 16, 2026 at 00:00:01 UTC (day after deadline)
    next_day = datetime.datetime(2026, 10, 16, 0, 0, 1, tzinfo=timezone.utc)
    status_next_day = evaluate_hackathon_status(deadline="2026-10-15", as_of=next_day)
    assert status_next_day == "ended", "Date-only deadline must be ENDED on the following day"


def test_cross_year_date_range_rollover():
    """Dec 20 - Jan 15, 2027 must parse start as 2026-12-20 and end as 2027-01-15."""
    start_iso, end_iso = parse_date_range("Dec 20 - Jan 15, 2027")
    assert start_iso is not None
    assert end_iso is not None
    assert start_iso.startswith("2026-12-20")
    assert end_iso.startswith("2027-01-15")


def test_relative_countdown_strings_rejected_as_calendar_dates():
    """Text like '26 days left' or '13 hours left' must not be parsed into bogus calendar dates."""
    assert normalize_date("26 days left") is None
    assert normalize_date("13 hours left") is None
    assert normalize_date("1 day to go") is None

    start, end = parse_date_range("26 days left")
    assert start is None and end is None


def test_unstop_parser_rejects_category_navigation_links():
    """Verify navigation slugs like /hackathons/online and /hackathons/all are rejected."""
    html_content = """
    <a href="/hackathons/online">
        <h3>Online Hackathons</h3>
    </a>
    <a href="/hackathons/all">
        <h3>All Hackathons</h3>
    </a>
    <a href="/hackathons/real-college-hackathon-1694845">
        <h3>Real College Hackathon</h3>
        <div>Deadline: Nov 20, 2026</div>
    </a>
    """
    hackathons = parse_unstop_cards_from_html(html_content)
    assert len(hackathons) == 1
    assert hackathons[0]["name"] == "Real College Hackathon"
    assert "1694845" in hackathons[0]["link"]


def test_unstop_parser_extracts_clean_title_without_badges_or_newlines():
    """Verify badges, countdown timers, and organizer noise are stripped from title."""
    html_content = """
    <a href="/hackathons/super-ai-challenge-1699999">
        <div>
            <span class="badge">Featured</span>
            <span class="badge">Hot</span>
            <h3>
                Super AI Challenge 2026
                14 days left
                Posted Oct 10
            </h3>
        </div>
        <div>Deadline: Dec 15, 2026</div>
    </a>
    """
    hackathons = parse_unstop_cards_from_html(html_content)
    assert len(hackathons) == 1
    assert hackathons[0]["name"] == "Super AI Challenge 2026"
    assert "\n" not in hackathons[0]["name"]


# ==============================================================================
# Phase 3: Honest Benefit Evidence
# ==============================================================================


def test_title_only_provider_mention_does_not_create_benefit():
    """Title mention like 'AWS Community Hackathon' without credit evidence must not extract benefits."""
    benefits = extract_special_benefits(
        event_name="AWS Community Day Hackathon",
        text="A community event for developers to meet and collaborate on open source.",
        source_url="https://devpost.com/aws-day",
    )
    assert len(benefits) == 0


def test_generic_sponsor_prize_does_not_create_credits_benefit():
    """Generic sponsor cash prizes must not be falsely converted into cloud credit perks."""
    text = "Grand Prize: $10,000 cash sponsored by Google Cloud."
    benefits = extract_special_benefits(
        event_name="Fintech Hack",
        text=text,
        source_url="https://devpost.com/fintech",
    )
    assert len(benefits) == 0


def test_generic_registration_form_not_associated_with_credits():
    """Event registration form must not be treated as a separate credits application form."""
    text = "Join us for a weekend of hacking! Register your team here: https://forms.gle/event-registration-2026."
    benefits = extract_special_benefits(
        event_name="Open Hack",
        text=text,
        source_url="https://devpost.com/open-hack",
    )
    assert len(benefits) == 0


def test_early_bird_deadline_not_interpreted_as_benefit_deadline():
    """Early-bird registration deadline must not be copied as benefit application deadline."""
    text = (
        "All participants receive $1,000 in AWS Activate credits. Early-bird registration deadline is October 20, 2026."
    )
    benefits = extract_special_benefits(
        event_name="Cloud Sprint",
        text=text,
        source_url="https://devpost.com/cloud-sprint",
    )
    assert len(benefits) == 1
    assert benefits[0].application_deadline is None


def test_credit_amount_not_cross_attributed_to_other_providers():
    """$5,000 AWS credits must not be assigned to Google Cloud."""
    text = "Teams get $5,000 in AWS credits to host their projects. Google Cloud is also a proud sponsor of this event."
    benefits = extract_special_benefits(
        event_name="Multi Sponsor Hack",
        text=text,
        source_url="https://devpost.com/multi-hack",
    )
    # Only AWS should have credits extracted
    assert len(benefits) == 1
    assert "AWS" in benefits[0].name
    assert "$5,000" in benefits[0].description


# ==============================================================================
# Phase 4: Pipeline Failure Isolation and Catalog Protection
# ==============================================================================


class OutageFailingFetcher(BaseFetcher):
    name = "MockOutageSource"

    def fetch(self):
        raise ConnectionRefusedError("Platform is unreachable")


def test_all_sources_outage_does_not_publish_or_advance_catalog(tmp_path):
    """Verify that when all sources fail, the pipeline halts export and preserves the existing catalog."""
    test_catalog_path = tmp_path / "hackathons.json"

    # Baseline known-good catalog
    initial_records = [
        {
            "name": "Known Good Hackathon",
            "link": "https://devpost.com/known-good",
            "source": "Devpost",
            "deadline": "2026-11-01T00:00:00",
            "status": "open",
        }
    ]
    payload = build_catalog_payload(initial_records)
    original_timestamp = payload["metadata"]["generated_at"]

    with open(test_catalog_path, "w", encoding="utf-8") as f:
        import json

        json.dump(payload, f, indent=2)

    # Run pipeline where all sources fail
    pipeline = IngestionPipeline(
        fetchers=[OutageFailingFetcher()],
        notify_telegram=False,
        auto_export=True,
    )
    summary = pipeline.run()

    # Invariant: Pipeline must fail success criteria and export must be halted
    assert summary.is_success is False
    assert summary.export_successful is False

    # Invariant: Catalog on disk must be completely preserved
    import json

    with open(test_catalog_path, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert saved_data["metadata"]["generated_at"] == original_timestamp
    assert saved_data["metadata"]["total_count"] == 1
    assert saved_data["hackathons"][0]["name"] == "Known Good Hackathon"
