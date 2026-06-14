from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from uda_pipeline.domain.models import ConjunturaRecord, DocumentCandidate, ExtractionResult


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    source_page_url TEXT NOT NULL,
    pdf_url TEXT NOT NULL,
    url_hash TEXT NOT NULL UNIQUE,
    file_hash TEXT UNIQUE,
    published_at TEXT,
    discovered_at TEXT NOT NULL,
    local_path TEXT,
    status TEXT NOT NULL,
    reference_year INTEGER,
    reference_quarter INTEGER,
    extraction_json TEXT,
    processed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_company_period
ON documents (company, reference_year, reference_quarter);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    company TEXT NOT NULL,
    metric_code TEXT NOT NULL,
    metric_label TEXT NOT NULL,
    unit TEXT,
    value REAL,
    year INTEGER,
    quarter INTEGER,
    source_page INTEGER,
    source_excerpt TEXT,
    confidence REAL NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_metrics_lookup
ON metrics (company, year, quarter, metric_code);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)

    def document_exists_by_url_hash(self, url_hash: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM documents WHERE url_hash = ?",
                (url_hash,),
            ).fetchone()
        return row is not None

    def document_exists_by_file_hash(self, file_hash: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM documents WHERE file_hash = ?",
                (file_hash,),
            ).fetchone()
        return row is not None

    def insert_discovered_document(self, candidate: DocumentCandidate, url_hash: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO documents (
                    company, title, source_page_url, pdf_url, url_hash, published_at, discovered_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.company,
                    candidate.title,
                    str(candidate.source_page_url),
                    str(candidate.pdf_url),
                    url_hash,
                    candidate.published_at.isoformat() if candidate.published_at else None,
                    datetime.now(UTC).isoformat(),
                    "discovered",
                ),
            )
            return int(cursor.lastrowid)

    def mark_downloaded(self, document_id: int, file_hash: str, local_path: Path) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE documents
                SET file_hash = ?, local_path = ?, status = ?
                WHERE id = ?
                """,
                (file_hash, str(local_path), "downloaded", document_id),
            )

    def mark_duplicate(self, document_id: int, file_hash: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE documents
                SET file_hash = COALESCE(?, file_hash), status = ?
                WHERE id = ?
                """,
                (file_hash, "duplicate", document_id),
            )

    def mark_processed(self, document_id: int, result: ExtractionResult) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM metrics WHERE document_id = ?", (document_id,))
            connection.execute(
                """
                UPDATE documents
                SET status = ?, reference_year = ?, reference_quarter = ?, extraction_json = ?, processed_at = ?
                WHERE id = ?
                """,
                (
                    "processed",
                    result.reference_year,
                    result.reference_quarter,
                    result.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                    document_id,
                ),
            )
            for metric in result.metrics:
                connection.execute(
                    """
                    INSERT INTO metrics (
                        document_id, company, metric_code, metric_label, unit, value, year, quarter,
                        source_page, source_excerpt, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        metric.company,
                        metric.metric_code,
                        metric.metric_label,
                        metric.unit,
                        metric.value,
                        metric.year or result.reference_year,
                        metric.quarter or result.reference_quarter,
                        metric.source_page,
                        metric.source_excerpt,
                        metric.confidence,
                    ),
                )

    def mark_failed(self, document_id: int, reason: str) -> None:
        payload = json.dumps({"error": reason}, ensure_ascii=True)
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE documents
                SET status = ?, extraction_json = ?
                WHERE id = ?
                """,
                ("failed", payload, document_id),
            )

    def list_documents(self, company: str | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM documents"
        params: list[object] = []
        if company:
            query += " WHERE company = ?"
            params.append(company)
        query += " ORDER BY discovered_at DESC"
        with self.connect() as connection:
            return list(connection.execute(query, params).fetchall())

    def query_conjuntura(
        self,
        company: str | None = None,
        year: int | None = None,
        quarter: int | None = None,
    ) -> list[ConjunturaRecord]:
        query = """
        SELECT
            m.company,
            m.metric_code,
            m.metric_label,
            m.value,
            m.unit,
            m.year,
            m.quarter,
            d.pdf_url AS source_document_url,
            d.source_page_url,
            m.source_excerpt,
            d.title AS document_title,
            d.processed_at
        FROM metrics m
        JOIN documents d ON d.id = m.document_id
        WHERE 1 = 1
        """
        params: list[object] = []
        if company:
            query += " AND m.company = ?"
            params.append(company)
        if year:
            query += " AND m.year = ?"
            params.append(year)
        if quarter:
            query += " AND m.quarter = ?"
            params.append(quarter)
        query += " ORDER BY m.company, m.year DESC, m.quarter DESC, m.metric_code"

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [ConjunturaRecord.model_validate(dict(row)) for row in rows]
