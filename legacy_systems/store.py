"""File-backed data access shared by the mock legacy services."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def data_dir() -> Path:
    return Path(os.environ.get("LEGACY_DATA_DIR", DEFAULT_DATA_DIR))


@lru_cache(maxsize=None)
def _load(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())


def policies() -> list[dict]:
    return _load(str(data_dir() / "policies.json"))


def claims() -> list[dict]:
    return _load(str(data_dir() / "claims.json"))
