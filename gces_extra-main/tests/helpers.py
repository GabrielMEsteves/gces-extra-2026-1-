from __future__ import annotations

import shutil
import uuid
from pathlib import Path


def make_test_dir() -> Path:
    root = Path("data/test_runtime")
    root.mkdir(parents=True, exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_test_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
