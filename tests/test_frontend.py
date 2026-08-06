import pytest

from app.core import frontend
from app.core.frontend import (
    _valid_base,
    build_frontend_link,
    frontend_base_url,
    set_last_origin,
)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(frontend, "_last_origin", "")
    monkeypatch.setattr(frontend.settings, "FRONTEND_BASE_URL", "")
    yield


@pytest.mark.parametrize(
    "url, expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("http://", None),
        ("https://", None),
        ("http:/book-slot/x", None),
        ("ftp://example.com", None),
        ("example.com", None),
        ("https://talentos.webknot-dev.in", "https://talentos.webknot-dev.in"),
        ("https://talentos.webknot-dev.in/path/", "https://talentos.webknot-dev.in"),
        ("http://localhost:5173", "http://localhost:5173"),
    ],
)
def test_valid_base(url, expected):
    assert _valid_base(url) == expected


def test_set_last_origin_ignores_invalid():
    set_last_origin("http://")
    assert frontend_base_url() == ""


def test_set_last_origin_captures_valid():
    set_last_origin("https://talentos.webknot-dev.in/some/path")
    assert frontend_base_url() == "https://talentos.webknot-dev.in"


def test_configured_wins_over_captured():
    set_last_origin("https://captured.example.com")
    frontend.settings.FRONTEND_BASE_URL = "https://configured.example.com/"
    assert frontend_base_url() == "https://configured.example.com"


def test_invalid_configured_falls_back_to_captured():
    set_last_origin("https://captured.example.com")
    frontend.settings.FRONTEND_BASE_URL = "http://"
    assert frontend_base_url() == "https://captured.example.com"


def test_nothing_known_returns_relative_path():
    assert build_frontend_link("/book-slot/abc") == "/book-slot/abc"


def test_build_link_uses_captured_origin():
    set_last_origin("https://talentos.webknot-dev.in")
    assert build_frontend_link("/book-slot/abc") == "https://talentos.webknot-dev.in/book-slot/abc"


def test_build_link_never_emits_empty_host():
    frontend.settings.FRONTEND_BASE_URL = "http://"
    link = build_frontend_link("/book-slot/abc")
    assert "http:///" not in link
    assert link == "/book-slot/abc"
