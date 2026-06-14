from pathlib import Path

from uda_pipeline.db import Database
from uda_pipeline.domain.models import DocumentCandidate, ExtractionResult, ExtractedMetric
from tests.helpers import cleanup_test_dir, make_test_dir


def test_document_idempotence_and_query():
    test_dir = make_test_dir()
    try:
        db = Database(test_dir / "test.db")
        candidate = DocumentCandidate(
            company="MRV",
            source_page_url="https://ri.example.com/resultados",
            pdf_url="https://ri.example.com/mrv_1t26.pdf",
            title="MRV Previa Operacional 1T26",
        )
        document_id = db.insert_discovered_document(candidate, "urlhash")
        db.mark_downloaded(document_id, "filehash", test_dir / "mrv.pdf")
        db.mark_processed(
            document_id,
            ExtractionResult(
                company="MRV",
                reference_year=2026,
                reference_quarter=1,
                metrics=[
                    ExtractedMetric(
                        metric_code="vso",
                        metric_label="VSO",
                        value=12.4,
                        company="MRV",
                        year=2026,
                        quarter=1,
                        confidence=0.9,
                    )
                ],
            ),
        )

        assert db.document_exists_by_url_hash("urlhash")
        assert db.document_exists_by_file_hash("filehash")
        records = db.query_conjuntura(company="MRV", year=2026, quarter=1)
        assert len(records) == 1
        assert records[0].metric_code == "vso"
        assert records[0].quarter == 1
    finally:
        cleanup_test_dir(test_dir)
