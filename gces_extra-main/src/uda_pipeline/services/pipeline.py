from __future__ import annotations

from dataclasses import dataclass

import httpx

from uda_pipeline.db import Database
from uda_pipeline.domain.models import IngestionSummary
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


class IngestionPipeline:
    def __init__(self, sources_file, deps: PipelineDependencies) -> None:
        self.sources_file = sources_file
        self.deps = deps

    def run_once(self) -> IngestionSummary:
        sources = load_sources(self.sources_file)
        discovered = 0
        downloaded = 0
        skipped_duplicates = 0
        processed = 0

        with httpx.Client(follow_redirects=True) as client:
            for source in sources:
                for candidate in self.deps.polling.discover(source, client):
                    discovered += 1
                    url_hash = hash_text(str(candidate.pdf_url))
                    if self.deps.db.document_exists_by_url_hash(url_hash):
                        skipped_duplicates += 1
                        continue
                    document_id = self.deps.db.insert_discovered_document(candidate, url_hash)
                    filename_hint = f"{candidate.company}_{url_hash[:12]}.pdf"
                    try:
                        local_path = self.deps.fetcher.download(str(candidate.pdf_url), filename_hint, client)
                        file_hash = hash_file(local_path)
                        if self.deps.db.document_exists_by_file_hash(file_hash):
                            self.deps.db.mark_duplicate(document_id, file_hash)
                            skipped_duplicates += 1
                            continue
                        self.deps.db.mark_downloaded(document_id, file_hash, local_path)
                        downloaded += 1
                        result = self.deps.extractor.extract(candidate.company, local_path)
                        self.deps.db.mark_processed(document_id, result)
                        processed += 1
                    except Exception as exc:  # noqa: BLE001
                        self.deps.db.mark_failed(document_id, str(exc))
        return IngestionSummary(
            discovered=discovered,
            downloaded=downloaded,
            skipped_duplicates=skipped_duplicates,
            processed=processed,
        )
