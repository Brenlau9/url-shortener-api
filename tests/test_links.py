def test_create_link_owner_a(client_a):
    resp = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert resp.status_code == 201
    body = resp.json()
    assert "code" in body
    assert isinstance(body["code"], str)
    assert len(body["code"]) > 0


def test_get_link_stats_owner_only(client_a, client_b):
    # A creates a link
    create = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    # A can read stats
    stats_a = client_a.get(f"/api/v1/links/{code}")
    assert stats_a.status_code == 200
    data = stats_a.json()
    assert data["code"] == code
    assert data["long_url"].startswith("https://example.com")
    assert "created_at" in data
    assert "expires_at" in data
    assert data["is_active"] is True
    assert isinstance(data["click_count"], int)

    # B cannot read A's link (404 to avoid leaking existence)
    stats_b = client_b.get(f"/api/v1/links/{code}")
    assert stats_b.status_code == 404


def test_get_link_stats_not_found(client_a):
    resp = client_a.get("/api/v1/links/NOTAREALCODE123")
    assert resp.status_code == 404


def test_redirect_not_found_public(client_a):
    # Redirect is public; sending X-API-Key is harmless
    resp = client_a.get("/nope")
    assert resp.status_code == 404


def test_redirect_rate_limited(client_a):
    # Create a link
    create = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    # REDIRECT_LIMIT is set to 3 in conftest.py, so 4th request should be 429
    for _ in range(4):
        last = client_a.get(f"/{code}", follow_redirects=False)

    assert last.status_code == 429
