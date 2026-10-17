import json

from exporter import export_public_catalog, merge_hackathon_records
from fetcher.base import BaseFetcher
from pipeline import IngestionPipeline


class FailingFetcher(BaseFetcher):
    name = "MockFailingSource"

    def fetch(self):
        raise ConnectionResetError("Remote server closed connection")


class SuccessfulFetcher(BaseFetcher):
    name = "MockSuccessSource"

    def fetch(self):
        return [
            {
                "name": "Reliable AI Hackathon",
                "link": "https://reliable.devpost.com",
                "deadline": "2026-09-01T00:00:00",
                "source": "MockSuccessSource",
                "prize": "$15,000",
                "description": "High reliability event",
            }
        ]


def test_merge_hackathon_records_preserves_baseline_on_source_failure():
    baseline = [
        {
            "id": "fp_devfolio_1",
            "fingerprint": "fp_devfolio_1",
            "name": "Existing Devfolio Hack",
            "link": "https://devfolio.co/hack1",
            "source": "Devfolio",
            "deadline": "2026-10-01T00:00:00",
            "status": "open",
        }
    ]

    # Incoming only has items from Unstop (Devfolio failed to fetch)
    incoming = [
        {
            "id": "fp_unstop_1",
            "fingerprint": "fp_unstop_1",
            "name": "New Unstop Hack",
            "link": "https://unstop.com/hack1",
            "source": "Unstop",
            "deadline": "2026-11-01T00:00:00",
            "status": "open",
        }
    ]

    merged = merge_hackathon_records(baseline, incoming)
    assert len(merged) == 2
    sources = {m["source"] for m in merged}
    assert "Devfolio" in sources
    assert "Unstop" in sources


def test_empty_incoming_preserves_baseline(tmp_path):
    test_catalog_path = tmp_path / "hackathons.json"

    # Step 1: Export initial catalog with 1 record
    initial_record = [
        {
            "name": "First Hack",
            "link": "https://first.devpost.com",
            "source": "Devpost",
            "deadline": "2026-08-01T00:00:00",
        }
    ]
    export_public_catalog(output_path=test_catalog_path, incoming_records=initial_record)

    with open(test_catalog_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["metadata"]["total_count"] == 1

    # Step 2: Attempt export with empty list (simulating scraping outage)
    export_public_catalog(output_path=test_catalog_path, incoming_records=[])

    # Invariant: Must NOT overwrite with empty catalog!
    with open(test_catalog_path, encoding="utf-8") as f:
        data_after = json.load(f)
    assert data_after["metadata"]["total_count"] == 1
    assert data_after["hackathons"][0]["name"] == "First Hack"


def test_pipeline_isolates_source_failure(monkeypatch, tmp_path):
    # Isolated test pipeline with 1 failing and 1 successful fetcher
    pipeline = IngestionPipeline(
        fetchers=[FailingFetcher(), SuccessfulFetcher()], notify_telegram=False, auto_export=False
    )

    summary = pipeline.run()

    # The pipeline must NOT crash on a single source failure
    assert summary.total_fetched == 1
    assert summary.total_accepted == 1
    assert "MockFailingSource" in summary.failed_sources
    assert summary.sources["MockFailingSource"].error is not None
    assert summary.sources["MockSuccessSource"].accepted == 1
