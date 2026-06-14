from __future__ import annotations

from pathlib import Path

from uda_pipeline.domain.models import ExtractionResult
from uda_pipeline.services.chunking import SemanticChunker
from uda_pipeline.services.llm import BaseLlmClient
from uda_pipeline.services.pdf_parser import PdfParser
from uda_pipeline.services.validation import build_validation_feedback, validate_result


class UdaExtractionService:
    def __init__(
        self,
        parser: PdfParser,
        chunker: SemanticChunker,
        llm_client: BaseLlmClient,
        max_full_scan_chars: int,
        max_llm_retries: int,
    ) -> None:
        self.parser = parser
        self.chunker = chunker
        self.llm_client = llm_client
        self.max_full_scan_chars = max_full_scan_chars
        self.max_llm_retries = max_llm_retries

    def extract(self, company: str, pdf_path: Path) -> ExtractionResult:
        analysis = self.parser.analyze(pdf_path)
        pages = [page.text for page in analysis.pages]
        joined = "\n\n".join(f"[PAGE {index}] {page}" for index, page in enumerate(pages, start=1))
        if analysis.recommended_mode == "full_scan" and len(joined) <= self.max_full_scan_chars:
            result = self._extract_with_validation(company, joined)
            result.extraction_strategy = "full_scan"
        else:
            chunks = self.chunker.chunk_pages(pages)
            relevant = self.chunker.select_relevant_chunks(chunks)
            merged = "\n\n".join(
                f"[CHUNK {chunk.index}] {chunk.title_hint or ''}\n{chunk.text}"
                for chunk in relevant
            )
            result = self._extract_with_validation(company, merged)
            result.extraction_strategy = "chunking"
            if not result.warnings:
                result.warnings.append("Extracao realizada por chunking semantico.")
        result.parser_strategy = analysis.parser_strategy
        result.warnings.extend(analysis.warnings)
        return result

    def _extract_with_validation(self, company: str, text: str) -> ExtractionResult:
        feedback: str | None = None
        last_result: ExtractionResult | None = None
        for _ in range(self.max_llm_retries + 1):
            last_result = self.llm_client.extract(company, text, feedback=feedback)
            issues = validate_result(last_result)
            if not issues:
                return last_result
            feedback = build_validation_feedback(issues)
        assert last_result is not None
        last_result.warnings.append("Resposta retornada com pendencias apos tentativas de reparo.")
        return last_result
