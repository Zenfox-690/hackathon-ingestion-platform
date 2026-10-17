import pytest

import db.store as store


@pytest.fixture(autouse=True)
def isolate_database_for_tests(tmp_path, monkeypatch):
    """
    Ensure every test operates on an isolated temporary SQLite database,
    preventing any test from reading, writing, or creating the production hackathons.db.
    """
    temp_db_path = str(tmp_path / "test_isolated_hackathons.db")
    monkeypatch.setenv("HACKATHON_DB_PATH", temp_db_path)
    store.reset_connection()

    # Pre-initialize schema on temporary database
    test_conn = store.get_connection(temp_db_path)

    yield test_conn

    store.reset_connection()
