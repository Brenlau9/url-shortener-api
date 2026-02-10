import pytest
from pydantic import ValidationError

from urlshortenerapi.schemas.links import CreateLinkRequest


@pytest.mark.parametrize(
    "bad_url",
    [
        "example.com",
        "ftp://example.com",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "://missing.scheme",
    ],
)
def test_create_link_request_rejects_non_http_https_urls(bad_url: str):
    with pytest.raises(ValidationError):
        CreateLinkRequest(url=bad_url)


@pytest.mark.parametrize(
    "good_url",
    [
        "http://example.com",
        "https://example.com/path?q=1",
    ],
)
def test_create_link_request_accepts_http_https_urls(good_url: str):
    req = CreateLinkRequest(url=good_url)
    assert str(req.url).startswith(("http://", "https://"))


@pytest.mark.parametrize("bad_alias", ["ab", "bad space", "x" * 33, "nope!"])
def test_custom_alias_validation_rejects_bad_alias(bad_alias: str):
    with pytest.raises(ValidationError):
        CreateLinkRequest(url="https://example.com", custom_alias=bad_alias)


def test_custom_alias_validation_accepts_valid_alias():
    req = CreateLinkRequest(url="https://example.com", custom_alias="brendan_123")
    assert req.custom_alias == "brendan_123"


@pytest.mark.parametrize("bad_expires", [0, -1, -100])
def test_expires_in_seconds_must_be_positive(bad_expires: int):
    with pytest.raises(ValidationError):
        CreateLinkRequest(url="https://example.com", expires_in_seconds=bad_expires)


@pytest.mark.parametrize("bad_max_clicks", [-1, -100])
def test_max_clicks_must_be_non_negative(bad_max_clicks: int):
    with pytest.raises(ValidationError):
        CreateLinkRequest(url="https://example.com", max_clicks=bad_max_clicks)


def test_max_clicks_none_normalizes_to_zero():
    # your validator turns None into 0
    req = CreateLinkRequest(url="https://example.com", max_clicks=None)
    assert req.max_clicks == 0
