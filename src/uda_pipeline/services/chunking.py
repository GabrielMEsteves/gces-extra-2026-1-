from __future__ import annotations

import re

from uda_pipeline.domain.models import Chunk


RELEVANCE_TERMS = {
    "vso",
    "vendas",
    "lancamentos",
    "estoque",
    "receita",
    "operacional",
    "unidades",
    "rgv",
    "adicoes",
    "repasse",
}


class SemanticChunker:
    def chunk_pages(self, pages: list[str], max_chars: int = 6000) -> list[Chunk]:
        chunks: list[Chunk] = []
        buffer = ""
        start_index = 0
        for page_index, page in enumerate(pages, start=1):
            normalized = re.sub(r"\s+", " ", page).strip()
            if not normalized:
                continue
            if len(buffer) + len(normalized) > max_chars and buffer:
                chunks.append(self._build_chunk(start_index, buffer))
                buffer = normalized
                start_index = page_index
            else:
                if not buffer:
                    start_index = page_index
                buffer = f"{buffer}\n\n{normalized}".strip()
        if buffer:
            chunks.append(self._build_chunk(start_index, buffer))
        return chunks

    def select_relevant_chunks(self, chunks: list[Chunk], limit: int = 4) -> list[Chunk]:
        ranked = sorted(chunks, key=lambda chunk: chunk.relevance_score, reverse=True)
        selected = [chunk for chunk in ranked if chunk.relevance_score > 0][:limit]
        return selected or ranked[: min(limit, len(ranked))]

    def _build_chunk(self, index: int, text: str) -> Chunk:
        lowered = text.lower()
        score = sum(lowered.count(term) for term in RELEVANCE_TERMS)
        title_hint = text.split("\n", 1)[0][:120]
        return Chunk(index=index, title_hint=title_hint, text=text, relevance_score=float(score))
