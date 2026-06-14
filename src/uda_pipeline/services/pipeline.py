from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from uda_pipeline.db import Database
from uda_pipeline.domain.models import DocumentCandidate, IngestionSummary
from uda_pipeline.services.catalog import hash_file, hash_text
from uda_pipeline.services.extraction import UdaExtractionService
from uda_pipeline.services.fetcher import PdfFetcher
from uda_pipeline.services.ri_polling import RiPollingService
from uda_pipeline.services.sources import load_sources


@dataclass
class PipelineDependencies:
    db: Database
    polling: RiPollingService
    fetcher: PdfFetcher
    extractor: UdaExtractionService


@dataclass
class IngestionCounters:
    discovered: int = 0
    downloaded: int = 0
    skipped_duplicates: int = 0
    processed: int = 0

    def to_summary(self) -> IngestionSummary:
        return IngestionSummary(
            discovered=self.discovered,
            downloaded=self.downloaded,
            skipped_duplicates=self.skipped_duplicates,
            processed=self.processed,
        )


class IngestionPipeline:
    def __init__(self, sources_file, deps: PipelineDependencies) -> None:
        self.sources_file = sources_file
        self.deps = deps

    def run_once(self) -> IngestionSummary:
        sources = load_sources(self.sources_file)
        counters = IngestionCounters()

        with httpx.Client(follow_redirects=True) as client:
            for source in sources:
                for candidate in self.deps.polling.discover(source, client):
                    self._process_candidate(candidate, client, counters)
        return counters.to_summary()

    def _process_candidate(
        self,
        candidate: DocumentCandidate,
        client: httpx.Client,
        counters: IngestionCounters,
    ) -> None:
        counters.discovered += 1
        url_hash = hash_text(str(candidate.pdf_url))
        if self.deps.db.document_exists_by_url_hash(url_hash):
            counters.skipped_duplicates += 1
            return

        document_id = self.deps.db.insert_discovered_document(candidate, url_hash)
        try:
            local_path = self._download_candidate_pdf(candidate, url_hash, client)
            file_hash = hash_file(local_path)
            if self.deps.db.document_exists_by_file_hash(file_hash):
                self.deps.db.mark_duplicate(document_id, file_hash)
                counters.skipped_duplicates += 1
                return

            self.deps.db.mark_downloaded(document_id, file_hash, local_path)
            counters.downloaded += 1

            result = self.deps.extractor.extract(candidate.company, local_path)
            self.deps.db.mark_processed(document_id, result)
            counters.processed += 1
        except Exception as exc:  # noqa: BLE001
            self.deps.db.mark_failed(document_id, str(exc))

    def _download_candidate_pdf(self, candidate: DocumentCandidate, url_hash: str, client: httpx.Client) -> Path:
        filename_hint = f"{candidate.company}_{url_hash[:12]}.pdf"
        return self.deps.fetcher.download(str(candidate.pdf_url), filename_hint, client)
