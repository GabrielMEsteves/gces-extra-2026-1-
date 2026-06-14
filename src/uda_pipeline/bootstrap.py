from __future__ import annotations

from uda_pipeline.config import get_settings
from uda_pipeline.db import Database
from uda_pipeline.services.chunking import SemanticChunker
from uda_pipeline.services.extraction import UdaExtractionService
from uda_pipeline.services.fetcher import PdfFetcher
from uda_pipeline.services.llm import build_llm_client
from uda_pipeline.services.pdf_parser import PdfParser
from uda_pipeline.services.pipeline import IngestionPipeline, PipelineDependencies
from uda_pipeline.services.ri_polling import RiPollingService


def build_pipeline() -> tuple[Database, IngestionPipeline]:
    settings = get_settings()
    db = Database(settings.db_path)
    llm_client = build_llm_client(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
    extractor = UdaExtractionService(
        parser=PdfParser(enable_ocr_fallback=settings.enable_ocr_fallback),
        chunker=SemanticChunker(),
        llm_client=llm_client,
        max_full_scan_chars=settings.max_full_scan_chars,
        max_llm_retries=settings.max_llm_retries,
    )
    pipeline = IngestionPipeline(
        sources_file=settings.sources_file,
        deps=PipelineDependencies(
            db=db,
            polling=RiPollingService(),
            fetcher=PdfFetcher(settings.storage_dir),
            extractor=extractor,
        ),
    )
    return db, pipeline
