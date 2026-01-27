from fastapi.testclient import TestClient
from urlshortenerapi.main import app

client = TestClient(app)


def test_create_link():
    resp = client.post(
        "/api/v1/links",
        json={"url": "https://example.com"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "code" in body
    assert isinstance(body["code"], str)
    assert len(body["code"]) > 0


def test_get_link_stats():
    # Create a link first
    create = client.post(
        "/api/v1/links",
        json={"url": "https://example.com"},
    )
    assert create.status_code == 201
    code = create.json()["code"]

    # Fetch analytics/stats
    stats = client.get(f"/api/v1/links/{code}")
    assert stats.status_code == 200
    data = stats.json()

    assert data["code"] == code
    assert data["long_url"].startswith("https://example.com")
    assert "created_at" in data
    assert "expires_at" in data
    assert data["is_active"] is True
    assert isinstance(data["click_count"], int)


def test_get_link_stats_not_found():
    resp = client.get("/api/v1/links/NOTAREALCODE123")
    assert resp.status_code == 404


def test_redirect_not_found():
    resp = client.get("/nope")
    assert resp.status_code == 404

def test_redirect_rate_limited():
    # Create a link
    create = client.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    # Hit redirect more than limit
    # NOTE: This depends on your configured REDIRECT_LIMIT (set to 60 above).
    # For tests, you'd ideally set REDIRECT_LIMIT to something small via env.
    for _ in range(4):
        last = client.get(f"/{code}", follow_redirects=False)

    assert last.status_code == 429