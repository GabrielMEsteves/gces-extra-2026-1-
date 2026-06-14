from __future__ import annotations

import json
from pathlib import Path

from uda_pipeline.domain.models import SourceConfig


def load_sources(path: Path) -> list[SourceConfig]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [SourceConfig.model_validate(item) for item in data]
