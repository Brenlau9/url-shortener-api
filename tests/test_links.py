def test_create_link(client):
    resp = client.post(
        "/api/v1/links",
        json={"url": "https://example.com"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "code" in body
    assert isinstance(body["code"], str)
    assert len(body["code"]) > 0


def test_get_link_stats(client):
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


def test_get_link_stats_not_found(client):
    resp = client.get("/api/v1/links/NOTAREALCODE123")
    assert resp.status_code == 404


def test_redirect_not_found(client):
    resp = client.get("/nope")
    assert resp.status_code == 404


def test_redirect_rate_limited(client):
    # Create a link
    create = client.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    # REDIRECT_LIMIT is set to 3 in conftest.py, so the 4th request should be 429
    for _ in range(4):
        last = client.get(f"/{code}", follow_redirects=False)

    assert last.status_code == 429
