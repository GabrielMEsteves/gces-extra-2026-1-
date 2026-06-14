from __future__ import annotations

import json
from pathlib import Path

from uda_pipeline.services.chunking import SemanticChunker
from uda_pipeline.services.extraction import UdaExtractionService
from uda_pipeline.services.llm import MockLlmClient
from uda_pipeline.services.pdf_parser import PdfParser


def main() -> None:
    manifest_path = Path("data/fixtures/real_pdfs/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    service = UdaExtractionService(
        parser=PdfParser(enable_ocr_fallback=True),
        chunker=SemanticChunker(),
        llm_client=MockLlmClient(),
        max_full_scan_chars=18000,
        max_llm_retries=1,
    )
    outputs: list[dict] = []
    for item in manifest:
        result = service.extract(item["company"], Path(item["local_path"]))
        outputs.append(
            {
                "company": item["company"],
                "document_title": item["document_title"],
                "pdf_url": item["pdf_url"],
                "parser_strategy": result.parser_strategy,
                "extraction_strategy": result.extraction_strategy,
                "reference_year": result.reference_year,
                "reference_quarter": result.reference_quarter,
                "metrics": {metric.metric_code: metric.value for metric in result.metrics},
                "warnings": result.warnings,
            }
        )
    Path("data/fixtures/real_pdfs/validation_output.json").write_text(
        json.dumps(outputs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
