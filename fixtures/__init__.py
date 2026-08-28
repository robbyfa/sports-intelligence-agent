"""Fixture loader helpers for test and demo match data."""

from __future__ import annotations

import json
from pathlib import Path
from models.events import MatchFeed

FIXTURES_DIR = Path(__file__).parent


def load_fixture(name: str) -> MatchFeed:
    """Load a match fixture JSON file by name (without extension).

    Example:
        feed = load_fixture("match_001")
    """
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return MatchFeed.model_validate(data)


def list_fixtures() -> list[str]:
    """Return names of all available fixture files."""
    return [p.stem for p in FIXTURES_DIR.glob("*.json")]
