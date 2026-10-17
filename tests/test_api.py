import pytest
from fastapi.testclient import TestClient

from api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Hackathon Ingestion Platform API"
    assert "/docs" in data["docs"]


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database_connected"] is True
    assert "total_hackathons" in data
    assert "active_hackathons" in data


def test_list_hackathons_default(client):
    response = client.get("/api/v1/hackathons")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert "page" in data
    assert data["page"] == 1
    assert data["limit"] == 20
    assert isinstance(data["items"], list)

    # Invariant: No internal bot data exposed
    for item in data["items"]:
        assert "chat_id" not in item
        assert "users" not in item
        assert "filters" not in item
        assert "password" not in item
        assert "token" not in item
        assert "id" in item
        assert "name" in item
        assert "link" in item


def test_list_hackathons_pagination(client):
    response = client.get("/api/v1/hackathons?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 2
    assert len(data["items"]) <= 2


def test_list_hackathons_filtering_by_source(client):
    response = client.get("/api/v1/hackathons?source=Devpost")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["source"].lower() == "devpost"


def test_list_hackathons_search_query(client):
    # Find an existing hackathon title or test with search
    all_res = client.get("/api/v1/hackathons?limit=1").json()
    if all_res["items"]:
        query_term = all_res["items"][0]["name"][:4]
        res = client.get(f"/api/v1/hackathons?q={query_term}")
        assert res.status_code == 200
        for item in res.json()["items"]:
            assert query_term.lower() in item["name"].lower() or query_term.lower() in item["description"].lower()


def test_get_hackathon_by_id_success_and_404(client):
    all_res = client.get("/api/v1/hackathons?limit=1").json()
    if all_res["items"]:
        item_id = all_res["items"][0]["id"]
        res = client.get(f"/api/v1/hackathons/{item_id}")
        assert res.status_code == 200
        assert res.json()["id"] == item_id

    # Non-existent ID returns 404
    res_404 = client.get("/api/v1/hackathons/non_existent_fingerprint_12345")
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()


def test_validation_errors(client):
    # Limit out of bounds (> 100)
    res = client.get("/api/v1/hackathons?limit=999")
    assert res.status_code == 422

    # Page out of bounds (< 1)
    res2 = client.get("/api/v1/hackathons?page=0")
    assert res2.status_code == 422

    # Invalid status
    res3 = client.get("/api/v1/hackathons?status=invalid_status_type")
    assert res3.status_code == 422
