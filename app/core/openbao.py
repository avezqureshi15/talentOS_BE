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


def _secret_path(key: str) -> str:
    mount = os.environ.get("BAO_KV_MOUNT", "secret").strip().strip("/")
    folder = os.environ.get("BAO_KV_PATH", "talentos").strip().strip("/")
    return f"/v1/{mount}/data/{folder}/{key}"


def read_secret(client: httpx.Client, key: str) -> str | None:
    """Return the ``value`` field of ``secret/data/talentos/<key>`` or None."""
    try:
        resp = client.get(_secret_path(key))
    except httpx.HTTPError as exc:
        logger.warning("OpenBao read %s failed: %s", key, exc)
        return None
    if resp.status_code != 200:
        logger.warning("OpenBao read %s -> HTTP %s", key, resp.status_code)
        return None
    data = resp.json().get("data", {}).get("data", {})
    value = data.get("value")
    return value if isinstance(value, str) else None


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
            else:
                logger.warning("Secret %s not found in OpenBao — will use env value", key)
        if found:
            source = "openbao"
        return found
    finally:
        client.close()
