"""Helpers for hiring-request location (list[str] JSON column)."""


def format_locations(locations: list[str] | str | None) -> str:
    """Join locations for display / external APIs that expect a single string."""
    if locations is None:
        return ""
    if isinstance(locations, str):
        return locations
    return ", ".join(loc for loc in locations if loc)
