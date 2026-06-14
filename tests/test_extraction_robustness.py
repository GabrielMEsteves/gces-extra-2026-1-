from pathlib import Path
import json

from uda_pipeline.domain.models import DocumentAnalysis, DocumentPage
from uda_pipeline.services.chunking import SemanticChunker
from uda_pipeline.services.extraction import UdaExtractionService
from uda_pipeline.services.llm import MockLlmClient
from uda_pipeline.services.ocr import OcrAvailability
from uda_pipeline.services.ocr import OcrExtractor
from uda_pipeline.services.periods import extract_reference_period
from uda_pipeline.services.pdf_parser import PdfParser
from tests.helpers import cleanup_test_dir, make_test_dir


class FakePdfParser(PdfParser):
    def __init__(self, pages: list[DocumentPage], parser_strategy: str = "text") -> None:
        self._analysis = DocumentAnalysis(
            pages=pages,
            recommended_mode="chunking" if sum(page.char_count for page in pages) > 120 else "full_scan",
            parser_strategy=parser_strategy,
        )

    def analyze(self, pdf_path: Path) -> DocumentAnalysis:  # noqa: ARG002
        return self._analysis


def test_extract_reference_period_handles_multiple_formats():
    assert extract_reference_period("Boletim 3T25") == (2025, 3)
    assert extract_reference_period("MRV Previa Operacional 1T2026") == (2026, 1)
    assert extract_reference_period("Resultados do primeiro trimestre de 2026") == (2026, 1)


def test_mock_extractor_prefers_absolute_over_percentage():
    client = MockLlmClient()
    result = client.extract(
        "MRV",
        "Previa Operacional 1T26. Lancamentos cresceram 15% e totalizaram 1.234 unidades. VSO 12,4%.",
    )
    metrics = {metric.metric_code: metric for metric in result.metrics}
    assert metrics["lancamentos"].value == 1234.0
    assert metrics["vso"].value == 12.4


def test_pipeline_handles_table_layout():
    parser = FakePdfParser(
        pages=[
            DocumentPage(page_number=1, text="Tabela 3T25 Lancamentos 1.200 Vendas Liquidas 980 Estoque 4.500", char_count=70),
        ],
        parser_strategy="text",
    )
    service = UdaExtractionService(
        parser=parser,
        chunker=SemanticChunker(),
        llm_client=MockLlmClient(),
        max_full_scan_chars=18000,
        max_llm_retries=1,
    )
    result = service.extract("Cury", Path("dummy.pdf"))
    metrics = {metric.metric_code: metric.value for metric in result.metrics}
    assert result.reference_year == 2025
    assert result.reference_quarter == 3
    assert metrics["lancamentos"] == 1200.0
    assert metrics["vendas_liquidas"] == 980.0


def test_pipeline_handles_slide_layout_with_hybrid_strategy():
    parser = FakePdfParser(
        pages=[
            DocumentPage(
                page_number=1,
                text="Slide 1 Previa Operacional MRV 1T26 VSO 12,4% Lancamentos 1.234 unidades Estoque 5.678 unidades",
                extraction_mode="multimodal",
                char_count=105,
            ),
        ],
        parser_strategy="hybrid",
    )
    service = UdaExtractionService(
        parser=parser,
        chunker=SemanticChunker(),
        llm_client=MockLlmClient(),
        max_full_scan_chars=18000,
        max_llm_retries=1,
    )
    result = service.extract("MRV", Path("dummy.pdf"))
    metrics = {metric.metric_code: metric.value for metric in result.metrics}
    assert result.parser_strategy == "hybrid"
    assert metrics["lancamentos"] == 1234.0
    assert metrics["estoque"] == 5678.0


class FakeOcrExtractor(OcrExtractor):
    def extract_pages(self, pdf_path: Path) -> list[str]:  # noqa: ARG002
        return ["OCR 1T26 Lancamentos 999 Estoque 888"]

    def availability(self):
        return OcrAvailability(enabled=True, reason=None)


def test_pdf_parser_uses_ocr_fallback_when_available():
    test_dir = make_test_dir()
    try:
        pdf_path = test_dir / "dummy.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%stub")
        parser = PdfParser(enable_ocr_fallback=True, ocr_extractor=FakeOcrExtractor())
        merged = parser._merge_text_and_ocr([DocumentPage(page_number=1, text="", char_count=0)], ["OCR 1T26 Lancamentos 999"])
        assert merged[0].extraction_mode == "ocr"
        assert "999" in merged[0].text
    finally:
        cleanup_test_dir(test_dir)


def test_real_pdf_mrv_is_classified_as_hybrid_and_period_is_found():
    path = Path("data/fixtures/real_pdfs/mrv_previa_1t26.pdf")
    parser = PdfParser(enable_ocr_fallback=False)
    analysis = parser.analyze(path)
    service = UdaExtractionService(
        parser=parser,
        chunker=SemanticChunker(),
        llm_client=MockLlmClient(),
        max_full_scan_chars=18000,
        max_llm_retries=1,
    )
    result = service.extract("MRV", path)
    assert analysis.parser_strategy == "hybrid"
    assert result.reference_year == 2026
    assert result.reference_quarter == 1


def test_real_pdf_mrv_extracts_expected_metrics_with_ocr():
    manifest = json.loads(Path("data/fixtures/real_pdfs/manifest.json").read_text(encoding="utf-8"))
    expected = next(item for item in manifest if item["company"] == "MRV")["expected_metrics"]
    service = UdaExtractionService(
        parser=PdfParser(enable_ocr_fallback=True),
        chunker=SemanticChunker(),
        llm_client=MockLlmClient(),
        max_full_scan_chars=18000,
        max_llm_retries=1,
    )
    result = service.extract("MRV", Path("data/fixtures/real_pdfs/mrv_previa_1t26.pdf"))
    metrics = {metric.metric_code: metric.value for metric in result.metrics}
    assert result.parser_strategy == "hybrid"
    for key, value in expected.items():
        assert metrics[key] == value


def test_real_pdf_direcional_extracts_expected_metrics():
    manifest = json.loads(Path("data/fixtures/real_pdfs/manifest.json").read_text(encoding="utf-8"))
    expected = next(item for item in manifest if item["company"] == "Direcional")["expected_metrics"]
    service = UdaExtractionService(
        parser=PdfParser(enable_ocr_fallback=False),
        chunker=SemanticChunker(),
        llm_client=MockLlmClient(),
        max_full_scan_chars=18000,
        max_llm_retries=1,
    )
    result = service.extract("Direcional", Path("data/fixtures/real_pdfs/direcional_previa_1t26.pdf"))
    metrics = {metric.metric_code: metric.value for metric in result.metrics}
    assert result.reference_year == 2026
    assert result.reference_quarter == 1
    for key, value in expected.items():
        assert metrics[key] == value
