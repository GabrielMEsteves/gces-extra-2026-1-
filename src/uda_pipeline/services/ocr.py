from __future__ import annotations

import importlib
import io
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OcrAvailability:
    enabled: bool
    reason: str | None = None


class OcrExtractor:
    def __init__(self) -> None:
        self._fitz = self._safe_import("fitz")
        self._pytesseract = self._safe_import("pytesseract")
        self._image = self._safe_import("PIL.Image")
        self._resolved_tesseract_cmd = self._resolve_tesseract_cmd()
        self._resolved_tessdata_dir = self._resolve_tessdata_dir()

    def availability(self) -> OcrAvailability:
        if self._fitz is None:
            return OcrAvailability(enabled=False, reason="PyMuPDF ausente")
        if self._pytesseract is None or self._image is None:
            return OcrAvailability(enabled=False, reason="pytesseract/Pillow ausentes")
        if self._resolved_tesseract_cmd is None:
            return OcrAvailability(enabled=False, reason="binario tesseract ausente no PATH")
        if self._resolved_tessdata_dir is None:
            return OcrAvailability(enabled=False, reason="diretorio tessdata ausente")
        return OcrAvailability(enabled=True)

    def extract_pages(self, pdf_path: Path) -> list[str]:
        availability = self.availability()
        if not availability.enabled:
            return []
        fitz = self._fitz
        pil_image = self._image
        pytesseract = self._pytesseract
        pytesseract.pytesseract.tesseract_cmd = str(self._resolved_tesseract_cmd)
        os.environ["TESSDATA_PREFIX"] = str(self._resolved_tessdata_dir)
        language = self._pick_language()
        document = fitz.open(str(pdf_path))
        pages: list[str] = []
        try:
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = pil_image.open(io.BytesIO(pixmap.tobytes("png")))
                pages.append(pytesseract.image_to_string(image, lang=language))
        finally:
            document.close()
        return pages

    @staticmethod
    def _safe_import(module_name: str):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            return None

    @staticmethod
    def _resolve_tesseract_cmd() -> Path | None:
        on_path = shutil.which("tesseract")
        if on_path:
            return Path(on_path)
        candidates = [
            Path(os.environ.get("ProgramFiles", "")) / "Tesseract-OCR" / "tesseract.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Tesseract-OCR" / "tesseract.exe",
            Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _resolve_tessdata_dir(self) -> Path | None:
        if self._resolved_tesseract_cmd is None:
            return None
        candidate = self._resolved_tesseract_cmd.parent / "tessdata"
        return candidate if candidate.exists() else None

    def _pick_language(self) -> str:
        if self._resolved_tessdata_dir is None:
            return "eng"
        por = self._resolved_tessdata_dir / "por.traineddata"
        eng = self._resolved_tessdata_dir / "eng.traineddata"
        if por.exists():
            return "por"
        if eng.exists():
            return "eng"
        return "eng"
