"""Frontend link building.

Resolves the public frontend origin with this precedence:
    1. ``FRONTEND_BASE_URL`` when set to a valid http(s) URL
    2. the last valid origin seen on an incoming request (captured by
       ``OriginCaptureMiddleware``) — works for background mail tasks and
       cron jobs that run in the same process without a request context
    3. relative paths (never emit ``http:///...`` style broken URLs)
"""

import threading
from urllib.parse import urlsplit

from app.core.config import settings

_origin_lock = threading.Lock()
_last_origin: str = ""


def _valid_base(url: str | None) -> str | None:
    """Normalize ``url`` to ``scheme://netloc`` or return None if invalid."""
    if not url:
        return None
    stripped = url.strip().rstrip("/")
    if not stripped:
        return None
    parts = urlsplit(stripped)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def set_last_origin(url: str | None) -> None:
    """Cache the latest valid origin observed on an incoming request."""
    value = _valid_base(url)
    if not value:
        return
    with _origin_lock:
        global _last_origin
        _last_origin = value


def frontend_base_url() -> str:
    """Configured base URL if valid, else the last request-derived origin."""
    configured = _valid_base(settings.FRONTEND_BASE_URL)
    if configured:
        return configured
    with _origin_lock:
        return _last_origin


def build_frontend_link(path: str) -> str:
    """Absolute frontend link when an origin is known, else a relative path."""
    base = frontend_base_url()
    return f"{base}{path}" if base else path
