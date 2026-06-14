from __future__ import annotations

from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from uda_pipeline.domain.models import DocumentCandidate, SourceConfig


class RiPollingService:
    def discover(self, source: SourceConfig, client: httpx.Client) -> list[DocumentCandidate]:
        if source.listing_strategy == "rss":
            return []
        response = client.get(str(source.results_url), timeout=30.0)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        candidates: list[DocumentCandidate] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            absolute_url = urljoin(str(source.base_url), href)
            title = anchor.get_text(" ", strip=True) or absolute_url.rsplit("/", 1)[-1]
            lowered = f"{title} {absolute_url}".lower()
            if ".pdf" not in absolute_url.lower():
                continue
            if source.allowed_pdf_keywords and not any(keyword.lower() in lowered for keyword in source.allowed_pdf_keywords):
                continue
            published_at = self._parse_date_near_anchor(anchor)
            candidates.append(
                DocumentCandidate(
                    company=source.company,
                    source_page_url=str(source.results_url),
                    pdf_url=absolute_url,
                    title=title,
                    published_at=published_at,
                )
            )
        return self._deduplicate(candidates)

    @staticmethod
    def _deduplicate(candidates: list[DocumentCandidate]) -> list[DocumentCandidate]:
        seen: set[str] = set()
        unique: list[DocumentCandidate] = []
        for item in candidates:
            key = str(item.pdf_url)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    @staticmethod
    def _parse_date_near_anchor(anchor: object):
        parent = getattr(anchor, "parent", None)
        if parent is None:
            return None
        text = parent.get_text(" ", strip=True)
        try:
            return date_parser.parse(text, dayfirst=True, fuzzy=True)
        except (ValueError, TypeError, OverflowError):
            return None
