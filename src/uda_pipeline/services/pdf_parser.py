from __future__ import annotations

import importlib
from pathlib import Path

from pypdf import PdfReader

from uda_pipeline.domain.models import DocumentAnalysis, DocumentPage
from uda_pipeline.services.ocr import OcrExtractor


class PdfParser:
    def __init__(self, enable_ocr_fallback: bool = True, ocr_extractor: OcrExtractor | None = None) -> None:
        self.enable_ocr_fallback = enable_ocr_fallback
        self.ocr_extractor = ocr_extractor or OcrExtractor()
        self._fitz = self._safe_import("fitz")

    def analyze(self, pdf_path: Path) -> DocumentAnalysis:
        pages = self._extract_pages(pdf_path)
        sparse_pages = [
            page
            for page in pages
            if page.char_count < 500 or page.block_count <= 6
        ]
        parser_strategy = "hybrid" if pages and len(sparse_pages) >= max(1, len(pages) // 3) else "text"
        warnings: list[str] = []
        if parser_strategy == "hybrid":
            warnings.append("PDF com baixo volume textual; OCR/multimodal recomendado.")
            if self.enable_ocr_fallback:
                ocr_pages = self.ocr_extractor.extract_pages(pdf_path)
                if ocr_pages:
                    pages = self._merge_text_and_ocr(pages, ocr_pages)
                    warnings.append("OCR fallback aplicado nas paginas com baixo texto.")
                else:
                    availability = self.ocr_extractor.availability()
                    if availability.reason:
                        warnings.append(f"OCR indisponivel: {availability.reason}.")
        total_chars = sum(page.char_count for page in pages)
        recommended_mode = "full_scan" if total_chars and total_chars <= 18000 else "chunking"
        return DocumentAnalysis(
            pages=pages,
            recommended_mode=recommended_mode,
            parser_strategy=parser_strategy,
            warnings=warnings,
        )

    def extract_pages(self, pdf_path: Path) -> list[str]:
        return [page.text for page in self.analyze(pdf_path).pages]

    @staticmethod
    def _merge_text_and_ocr(pages: list[DocumentPage], ocr_pages: list[str]) -> list[DocumentPage]:
        merged: list[DocumentPage] = []
        for index, page in enumerate(pages):
            ocr_text = ocr_pages[index] if index < len(ocr_pages) else ""
            if page.char_count < 80 and ocr_text.strip():
                merged.append(
                    DocumentPage(
                        page_number=page.page_number,
                        text=ocr_text,
                        extraction_mode="ocr",
                        char_count=len(ocr_text.strip()),
                        block_count=page.block_count,
                    )
                )
            elif ocr_text.strip():
                merged.append(
                    DocumentPage(
                        page_number=page.page_number,
                        text=f"{page.text}\n{ocr_text}".strip(),
                        extraction_mode="multimodal",
                        char_count=len(f'{page.text}\n{ocr_text}'.strip()),
                        block_count=page.block_count,
                    )
                )
            else:
                merged.append(page)
        return merged

    def _extract_pages(self, pdf_path: Path) -> list[DocumentPage]:
        if self._fitz is not None:
            pages = self._extract_with_fitz(pdf_path)
            if pages:
                return pages
        return self._extract_with_pypdf(pdf_path)

    def _extract_with_fitz(self, pdf_path: Path) -> list[DocumentPage]:
        fitz = self._fitz
        if fitz is None:
            return []
        document = fitz.open(str(pdf_path))
        pages: list[DocumentPage] = []
        try:
            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text") or ""
                blocks = [block for block in page.get_text("blocks") if str(block[4]).strip()]
                pages.append(
                    DocumentPage(
                        page_number=page_number,
                        text=text,
                        extraction_mode="text",
                        char_count=len(text.strip()),
                        block_count=len(blocks),
                    )
                )
        finally:
            document.close()
        return pages

    @staticmethod
    def _extract_with_pypdf(pdf_path: Path) -> list[DocumentPage]:
        reader = PdfReader(str(pdf_path))
        pages: list[DocumentPage] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(
                DocumentPage(
                    page_number=page_number,
                    text=text,
                    extraction_mode="text",
                    char_count=len(text.strip()),
                    block_count=0,
                )
            )
        return pages

    @staticmethod
    def _safe_import(module_name: str):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            return None
