import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fetcher.base import BaseFetcher
from pipeline import IngestionPipeline


class MockTestPollutionSource(BaseFetcher):
    name = "MockPollutionSource"

    def fetch(self):
        return [
            {
                "name": "Pollution Canary Hackathon",
                "link": "https://pollution-canary.devpost.com",
                "source": "MockPollutionSource",
                "deadline": "2026-11-01T00:00:00",
            }
        ]


def test_module_import_does_not_create_or_touch_database():
    """
    Verify that importing db.store, pipeline, exporter, or main in a clean directory
    never creates or connects to hackathons.db at import time.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        code = (
            "import os, sys\n"
            "sys.path.insert(0, os.getcwd())\n"
            "import db.store\n"
            "import pipeline\n"
            "import exporter\n"
            "import main\n"
            "import api.adapter\n"
            "assert not os.path.exists('hackathons.db'), 'hackathons.db was created at import time!'\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=tmpdir,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Import test failed:\n{result.stderr}\n{result.stdout}"
        assert not os.path.exists(os.path.join(tmpdir, "hackathons.db"))


def test_test_pipeline_never_modifies_real_database():
    """
    Verify that running an IngestionPipeline during testing uses the isolated database
    and never inserts mock sources into the real hackathons.db.
    """
    pipeline = IngestionPipeline(
        fetchers=[MockTestPollutionSource()],
        notify_telegram=False,
        auto_export=False,
    )
    summary = pipeline.run()
    assert summary.total_accepted == 1

    # Verify that the real hackathons.db does not contain the canary
    real_db = Path("hackathons.db")
    if real_db.exists():
        import sqlite3

        real_conn = sqlite3.connect(str(real_db))
        count = real_conn.execute(
            "SELECT count(*) FROM hackathons WHERE source = 'MockPollutionSource' OR name LIKE '%Pollution Canary%'"
        ).fetchone()[0]
        real_conn.close()
        assert count == 0, "Mock record leaked into real production hackathons.db!"


def test_test_exporter_never_modifies_frontend_public_catalog(tmp_path):
    """
    Verify that exporting to a custom output path during testing
    never touches the frontend's public catalog copies.
    """
    from exporter import export_public_catalog

    fe_catalog = Path("frontend/public/data/hackathons.json")
    original_mtime = fe_catalog.stat().st_mtime if fe_catalog.exists() else None
    original_content = fe_catalog.read_text(encoding="utf-8") if fe_catalog.exists() else None

    tmp_export = tmp_path / "custom_test_export.json"
    mock_records = [
        {
            "id": "mock_id_999",
            "name": "Pollution Canary Hackathon",
            "link": "https://pollution-canary.devpost.com",
            "source": "Devpost",
            "deadline": "2026-11-01T00:00:00",
            "location": "Online",
            "status": "open",
        }
    ]
    export_public_catalog(output_path=tmp_export, incoming_records=mock_records)

    assert tmp_export.exists()
    if fe_catalog.exists():
        assert fe_catalog.read_text(encoding="utf-8") == original_content
        assert fe_catalog.stat().st_mtime == original_mtime
