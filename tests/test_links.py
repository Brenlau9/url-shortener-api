from fastapi.testclient import TestClient
from urlshortenerapi.main import app

client = TestClient(app)

def test_create_link():
    resp = client.post(
        "api/v1/links",
        json={"url":"https://example.com"}
    )
    assert resp.status_code == 201
    assert "code" in resp.json()

def test_redirect_not_found():
    resp = client.get("/nope")
    assert resp.status_code == 404