"""Guardrails for the permission catalogue.

Checks that the runtime permission metadata stays consistent:
- every ``Permission`` member is documented in ``PERMISSION_ENDPOINTS``
- every ``PERMISSION_ENDPOINTS`` entry maps back to a known permission

Runnable with pytest (``test_*``) or directly: ``python tests/test_permissions_metadata.py``.
"""

from __future__ import annotations

from app.core.permissions import PERMISSION_ENDPOINTS, Permission


def test_every_permission_has_endpoint_reference() -> None:
    missing = [p.value for p in Permission if p.value not in PERMISSION_ENDPOINTS]
    assert not missing, (
        f"Permissions missing from PERMISSION_ENDPOINTS (add a representative endpoint): {missing}"
    )


def test_every_endpoint_reference_is_a_permission() -> None:
    known = {p.value for p in Permission}
    unknown = set(PERMISSION_ENDPOINTS) - known
    assert not unknown, f"PERMISSION_ENDPOINTS references unknown permissions: {unknown}"


if __name__ == "__main__":
    test_every_permission_has_endpoint_reference()
    test_every_endpoint_reference_is_a_permission()
    print("permissions metadata OK")