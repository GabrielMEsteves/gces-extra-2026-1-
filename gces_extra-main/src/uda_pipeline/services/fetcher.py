from __future__ import annotations

from pathlib import Path

import httpx


class PdfFetcher:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir

    def download(self, url: str, filename_hint: str, client: httpx.Client) -> Path:
        safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in filename_hint)
        if not safe_name.lower().endswith(".pdf"):
            safe_name += ".pdf"
        target = self.storage_dir / safe_name
        response = client.get(url, timeout=60.0)
        response.raise_for_status()
        target.write_bytes(response.content)
        return target
