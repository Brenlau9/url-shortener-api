import re
from urlshortenerapi.api.routes import _base62_code, _BASE62_ALPHABET

_BASE62_RE = re.compile(r"^[0-9a-zA-Z]+$")


def test_base62_code_has_only_base62_chars():
    code = _base62_code(7)
    assert _BASE62_RE.fullmatch(code)
    # also ensure alphabet matches what we expect
    assert set(code).issubset(set(_BASE62_ALPHABET))


def test_base62_code_length():
    assert len(_base62_code(6)) == 6
    assert len(_base62_code(8)) == 8
