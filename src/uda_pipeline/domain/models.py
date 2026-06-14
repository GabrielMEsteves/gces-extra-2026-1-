from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class SourceConfig(BaseModel):
    company: str
    base_url: HttpUrl
    results_url: HttpUrl
    listing_strategy: Literal["html_links", "rss"] = "html_links"
    allowed_pdf_keywords: list[str] = Field(default_factory=list)


class DocumentCandidate(BaseModel):
    company: str
    source_page_url: HttpUrl
    pdf_url: HttpUrl
    title: str
    published_at: datetime | None = None


class Chunk(BaseModel):
    index: int
    title_hint: str | None = None
    text: str
    relevance_score: float = 0.0


class DocumentPage(BaseModel):
    page_number: int
    text: str
    extraction_mode: Literal["text", "ocr", "multimodal"] = "text"
    char_count: int = 0
    block_count: int = 0


class DocumentAnalysis(BaseModel):
    pages: list[DocumentPage] = Field(default_factory=list)
    recommended_mode: Literal["full_scan", "chunking"] = "chunking"
    parser_strategy: Literal["text", "ocr_fallback", "hybrid"] = "text"
    warnings: list[str] = Field(default_factory=list)


class ExtractedMetric(BaseModel):
    metric_code: str
    metric_label: str
    unit: str | None = None
    value: float | None = None
    year: int | None = None
    quarter: int | None = Field(default=None, ge=1, le=4)
    company: str
    source_page: int | None = None
    source_excerpt: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    company: str
    document_type: str | None = None
    reference_year: int | None = None
    reference_quarter: int | None = Field(default=None, ge=1, le=4)
    currency: str | None = None
    parser_strategy: Literal["text", "ocr_fallback", "hybrid"] | None = None
    extraction_strategy: Literal["full_scan", "chunking"] | None = None
    metrics: list[ExtractedMetric] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConjunturaRecord(BaseModel):
    company: str
    metric_code: str
    metric_label: str
    value: float | None = None
    unit: str | None = None
    year: int | None = None
    quarter: int | None = None
    source_document_url: str
    source_page_url: str
    source_excerpt: str | None = None
    document_title: str
    processed_at: datetime | None = None


class DocumentRecord(BaseModel):
    id: int
    company: str
    title: str
    source_page_url: str
    pdf_url: str
    url_hash: str
    file_hash: str | None = None
    published_at: str | None = None
    discovered_at: str
    local_path: str | None = None
    status: str
    reference_year: int | None = None
    reference_quarter: int | None = None
    extraction_json: str | None = None
    processed_at: str | None = None


class IngestionSummary(BaseModel):
    discovered: int
    downloaded: int
    skipped_duplicates: int
    processed: int


class HealthResponse(BaseModel):
    status: str


class DocumentsResponse(BaseModel):
    items: list[DocumentRecord]


class MetricCatalogResponse(BaseModel):
    metrics: dict[str, str]


class ConjunturaResponse(BaseModel):
    items: list[ConjunturaRecord]
