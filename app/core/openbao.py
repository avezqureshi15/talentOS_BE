"""Minimal OpenBao (Vault-compatible) KV v2 client.

Used at startup by ``app.core.config`` to pull secrets so a deployed backend
reads credentials from OpenBao instead of ``.env``.

IMPORTANT: this module must stay free of imports of the app's own packages
(no ``app.core.config`` / ``app.core.logger``) — it is imported from
``app.core.config`` during module import and a package-level import would
create a circular import.
"""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

# Resolved after the startup fetch; surfaced via /health so an operator can
# confirm secrets came from OpenBao rather than the environment.
source = "env"


def _read_token() -> str:
    token = os.environ.get("BAO_TOKEN", "").strip()
    if token:
        return token
    token_file = os.environ.get("BAO_TOKEN_FILE", "").strip()
    if token_file:
        try:
            with open(token_file, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError as exc:
            logger.warning("Could not read BAO_TOKEN_FILE=%s: %s", token_file, exc)
    return ""


def _client() -> httpx.Client | None:
    addr = os.environ.get("BAO_ADDR", "").strip().rstrip("/")
    if not addr:
        return None
    token = _read_token()
    if not token:
        logger.warning("BAO_ADDR is set but no token found (BAO_TOKEN / BAO_TOKEN_FILE)")
        return None
    return httpx.Client(
        base_url=addr,
        headers={"X-Vault-Token": token},
        timeout=10.0,
    )


# Last non-200 status from read_secret; fetch_secrets uses 403 to abort early.
_last_status = 0


def _secret_path(key: str) -> str:
    mount = os.environ.get("BAO_KV_MOUNT", "secret").strip().strip("/")
    folder = os.environ.get("BAO_KV_PATH", "talentos").strip().strip("/")
    return f"/v1/{mount}/data/{folder}/{key}"


def _status_hint(resp: httpx.Response) -> str:
    """Short, secret-free hint so 403 nginx-deny vs Vault-deny is obvious."""
    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip()
    body = (resp.text or "").strip().replace("\n", " ")[:80]
    return f"{resp.status_code} {ctype} {body}".strip()


def read_secret(client: httpx.Client, key: str) -> str | None:
    """Return the ``value`` field of ``secret/data/talentos/<key>`` or None."""
    global _last_status
    path = _secret_path(key)
    last_hint = ""
    _last_status = 0
    for attempt in range(3):
        try:
            resp = client.get(path)
        except httpx.HTTPError as exc:
            logger.warning("OpenBao read %s failed: %s", key, exc)
            return None
        _last_status = resp.status_code
        if resp.status_code == 200:
            data = resp.json().get("data", {}).get("data", {})
            value = data.get("value")
            return value if isinstance(value, str) else None
        last_hint = _status_hint(resp)
        # 403 is commonly nginx IP-deny or a brief burst from --reload.
        if resp.status_code == 403 and attempt < 2:
            time.sleep(0.4 * (attempt + 1))
            continue
        break
    logger.warning("OpenBao read %s -> HTTP %s", key, last_hint)
    return None


def fetch_secrets(keys: list[str]) -> dict[str, str]:
    """Fetch ``{key: value}`` for *keys* from OpenBao.

    Only keys actually found are returned; missing ones are skipped so the
    caller can fall back to environment values.
    """
    global source
    client = _client()
    if client is None:
        return {}
    try:
        found: dict[str, str] = {}
        for key in keys:
            value = read_secret(client, key)
            if value is not None:
                found[key] = value
                continue
            logger.warning("Secret %s not found in OpenBao — will use env value", key)
            if _last_status == 403:
                logger.warning("OpenBao returned 403 — skipping remaining secret reads")
                break
        if found:
            source = "openbao"
        return found
    finally:
        client.close()
