from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

import httpx
from pydantic import TypeAdapter

from uda_pipeline.domain.models import ExtractedMetric, ExtractionResult
from uda_pipeline.services.contract import METRIC_CATALOG
from uda_pipeline.services.contract import normalize_result
from uda_pipeline.services.periods import extract_reference_period


SYSTEM_PROMPT = """
Voce extrai exclusivamente dados estruturados de relatorios operacionais de incorporadoras.
Regras obrigatorias:
- Retorne apenas JSON valido.
- Nunca invente valores.
- Quando nao houver evidencia suficiente, use null.
- Prefira valores absolutos e ignore percentuais de variacao quando ambos aparecerem.
- Extraia trimestre e ano de referencia do documento.
- Inclua somente metricas observadas no texto.
- Cada metrica precisa carregar um trecho curto de evidencia em source_excerpt.
- Se houver numero percentual e numero absoluto proximos do mesmo rotulo, escolha o absoluto.
""".strip()

EXTRACTION_RESULT_ADAPTER = TypeAdapter(ExtractionResult)


class BaseLlmClient(ABC):
    @abstractmethod
    def extract(self, company: str, document_text: str, feedback: str | None = None) -> ExtractionResult:
        raise NotImplementedError


class MockLlmClient(BaseLlmClient):
    METRICS = {
        "lancamentos": {"label": "Lancamentos", "allow_percent": False},
        "vendas liquidas": {"label": "Vendas Liquidas", "allow_percent": False},
        "vso": {"label": "VSO", "allow_percent": True},
        "estoque": {"label": "Estoque", "allow_percent": False},
        "unidades": {"label": "Unidades", "allow_percent": False},
    }

    def extract(self, company: str, document_text: str, feedback: str | None = None) -> ExtractionResult:
        year, quarter = extract_reference_period(document_text)
        metrics: list[ExtractedMetric] = []
        normalized = re.sub(r"\s+", " ", document_text)
        table_metrics = self._extract_table_like_metrics(company, document_text, year, quarter)
        metrics.extend(table_metrics)
        for token, metadata in self.METRICS.items():
            if any(metric.metric_code == token.replace(" ", "_") for metric in metrics):
                continue
            evidence = self._find_metric_evidence(normalized, token, metadata["allow_percent"])
            if evidence is None:
                continue
            metrics.append(
                ExtractedMetric(
                    metric_code=token.replace(" ", "_"),
                    metric_label=metadata["label"],
                    value=evidence["value"],
                    unit=None,
                    year=year,
                    quarter=quarter,
                    company=company,
                    source_excerpt=evidence["excerpt"],
                    confidence=evidence["confidence"],
                )
            )
        warnings: list[str] = []
        if feedback:
            warnings.append("Extracao ajustada apos validacao semantica.")
        if not metrics:
            warnings.append("Nenhuma metrica reconhecida pelo extrator mock.")
        result = ExtractionResult(
            company=company,
            document_type="previa_operacional",
            reference_year=year,
            reference_quarter=quarter,
            metrics=metrics,
            warnings=warnings,
        )
        return normalize_result(result)

    def _extract_table_like_metrics(
        self,
        company: str,
        document_text: str,
        year: int | None,
        quarter: int | None,
    ) -> list[ExtractedMetric]:
        metrics: list[ExtractedMetric] = []
        lines = [line.strip() for line in document_text.splitlines() if line.strip()]
        joined = "\n".join(lines)
        if company.upper() == "MRV":
            metrics.extend(self._extract_mrv_operational_metrics(company, joined, year, quarter))
            if metrics:
                return metrics
        extractors = [
            ("lancamentos", re.compile(r"VGV Lançado \(VGV 100%\)\s+([\d\.,]+)", flags=re.IGNORECASE), 1),
            ("vendas_liquidas", re.compile(r"VGV Líquido Contratado \(VGV 100%\)\s+([\d\.,]+)", flags=re.IGNORECASE), 1),
            ("vso", re.compile(r"VSO \(Vendas Sobre Oferta\) em VGV 100%\s+([\d\.,]+)%", flags=re.IGNORECASE), 1),
            ("unidades", re.compile(r"Unidades Contratadas\s+([\d\.,]+)", flags=re.IGNORECASE), 1),
            (
                "estoque",
                re.compile(
                    r"Total \(R\$ milhões\)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)",
                    flags=re.IGNORECASE,
                ),
                3,
            ),
        ]

        for metric_code, pattern, group_index in extractors:
            match = pattern.search(joined)
            if not match:
                continue
            value = self._parse_numeric_token(match.group(group_index))
            metrics.append(
                ExtractedMetric(
                    metric_code=metric_code,
                    metric_label=METRIC_CATALOG[metric_code],
                    value=value,
                    unit=None,
                    year=year,
                    quarter=quarter,
                    company=company,
                    source_excerpt=match.group(0)[:240],
                    confidence=0.9,
                )
            )

        if metrics:
            return metrics

        narrative_patterns = {
            "lancamentos": re.compile(r"VGV lançado somou R\$ ([\d\.,]+)\s+bilhão", flags=re.IGNORECASE),
            "vendas_liquidas": re.compile(r"Vendas Líquidas.*?R\$ ([\d\.,]+)\s+bilhão", flags=re.IGNORECASE),
            "vso": re.compile(r"VSO CONSOLIDADA.*?(\d[\d\.,]*)%", flags=re.IGNORECASE),
        }
        for metric_code, pattern in narrative_patterns.items():
            match = pattern.search(joined)
            if not match:
                continue
            multiplier = 1000.0 if metric_code in {"lancamentos", "vendas_liquidas"} else 1.0
            value = self._parse_numeric_token(match.group(1)) * multiplier
            metrics.append(
                ExtractedMetric(
                    metric_code=metric_code,
                    metric_label=METRIC_CATALOG[metric_code],
                    value=value,
                    unit=None,
                    year=year,
                    quarter=quarter,
                    company=company,
                    source_excerpt=match.group(0)[:240],
                    confidence=0.8,
                )
            )
        return metrics

    def _extract_mrv_operational_metrics(
        self,
        company: str,
        text: str,
        year: int | None,
        quarter: int | None,
    ) -> list[ExtractedMetric]:
        specs = [
            (
                "lancamentos",
                re.compile(
                    r"LANGAMENTOS\.?\s+TOTAL INCORPORAGAO(?:.|\n){0,120}?VGV \(R\$ milh\w+\)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)",
                    flags=re.IGNORECASE | re.DOTALL,
                ),
            ),
            (
                "vendas_liquidas",
                re.compile(
                    r"VENDAS L[IÍ]QUIDAS\s+[@‘an\s]*TOTAL INCORPORAGAO(?:.|\n){0,120}?VGV \(R\$ milh\w+\)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)",
                    flags=re.IGNORECASE | re.DOTALL,
                ),
            ),
            (
                "unidades",
                re.compile(
                    r"PRODUGAO\s+Unidades\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)",
                    flags=re.IGNORECASE,
                ),
            ),
            (
                "repasses",
                re.compile(
                    r"REPASSES\s+Unidades\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)",
                    flags=re.IGNORECASE,
                ),
            ),
            (
                "vso",
                re.compile(
                    r"Vso L[IÍ]QUIDA.*?([\d\.,]+)%\s+([\d\.,]+)%\s+([\d\.,]+)%",
                    flags=re.IGNORECASE | re.DOTALL,
                ),
            ),
        ]
        metrics: list[ExtractedMetric] = []
        for metric_code, pattern in specs:
            match = pattern.search(text)
            if not match:
                continue
            value = self._parse_numeric_token(match.group(1))
            label = METRIC_CATALOG.get(metric_code, metric_code)
            metrics.append(
                ExtractedMetric(
                    metric_code=metric_code,
                    metric_label=label,
                    value=value,
                    unit=None,
                    year=year,
                    quarter=quarter,
                    company=company,
                    source_excerpt=match.group(0)[:240],
                    confidence=0.88,
                )
            )
        return metrics

    @staticmethod
    def _extract_first_absolute_value(line: str, allow_percent: bool) -> float | None:
        candidates = MockLlmClient._extract_numeric_candidates(line)
        selected = MockLlmClient._select_best_candidate(candidates, allow_percent=allow_percent)
        if selected is None:
            return None
        return float(selected["value"])

    @staticmethod
    def _parse_numeric_token(token: str) -> float:
        return float(token.replace(".", "").replace(",", "."))

    def _find_metric_evidence(self, text: str, token: str, allow_percent: bool) -> dict[str, float | str] | None:
        pattern = re.compile(rf"{re.escape(token)}", flags=re.IGNORECASE)
        for match in pattern.finditer(text):
            excerpt = self._slice_metric_window(text, match.start(), token)
            candidates = self._extract_numeric_candidates(excerpt)
            if not candidates:
                continue
            selected = self._select_best_candidate(candidates, allow_percent=allow_percent)
            if selected is None:
                continue
            return {
                "value": selected["value"],
                "excerpt": excerpt[:240],
                "confidence": selected["confidence"],
            }
        return None

    def _slice_metric_window(self, text: str, start_index: int, token: str) -> str:
        window_end = min(len(text), start_index + 140)
        excerpt = text[start_index:window_end]
        next_indexes: list[int] = []
        for other_token in self.METRICS:
            if other_token == token:
                continue
            next_match = re.search(re.escape(other_token), text[start_index + len(token):window_end], flags=re.IGNORECASE)
            if next_match:
                next_indexes.append(start_index + len(token) + next_match.start())
        if next_indexes:
            excerpt = text[start_index:min(next_indexes)]
        return excerpt

    @staticmethod
    def _extract_numeric_candidates(excerpt: str) -> list[dict[str, float | bool]]:
        candidates: list[dict[str, float | bool]] = []
        for match in re.finditer(r"(\d[\d\.\,]*)\s*(%|mil|milhoes|milhao|mm)?", excerpt, flags=re.IGNORECASE):
            raw = match.group(1)
            suffix = (match.group(2) or "").lower()
            value = float(raw.replace(".", "").replace(",", "."))
            is_percent = suffix == "%" or "%" in excerpt[max(0, match.start() - 2): match.end() + 2]
            if suffix in {"milhoes", "milhao", "mm"}:
                value *= 1_000_000
            elif suffix == "mil":
                value *= 1_000
            candidates.append({"value": value, "is_percent": is_percent})
        return candidates

    @staticmethod
    def _select_best_candidate(
        candidates: list[dict[str, float | bool]],
        allow_percent: bool,
    ) -> dict[str, float] | None:
        non_percent = [item for item in candidates if not item["is_percent"]]
        percent = [item for item in candidates if item["is_percent"]]
        if allow_percent:
            pool = percent or non_percent
            if not pool:
                return None
            chosen = pool[0]
            return {"value": float(chosen["value"]), "confidence": 0.7 if chosen["is_percent"] else 0.55}
        if non_percent:
            chosen = max(non_percent, key=lambda item: float(item["value"]))
            return {"value": float(chosen["value"]), "confidence": 0.72}
        return None


class OpenAICompatibleLlmClient(BaseLlmClient):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def extract(self, company: str, document_text: str, feedback: str | None = None) -> ExtractionResult:
        schema = EXTRACTION_RESULT_ADAPTER.json_schema()
        user_prompt = (
            f"Empresa: {company}\n"
            "Extraia os dados seguindo rigorosamente o schema JSON informado.\n"
            "Nao preencha campos sem evidencia no texto.\n"
        )
        if feedback:
            user_prompt += f"\nFeedback de validacao:\n{feedback}\n"
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "temperature": 0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "extraction_result",
                        "schema": schema,
                        "strict": True,
                    },
                },
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"{user_prompt}\n"
                            f"Schema:\n{json.dumps(schema, ensure_ascii=True)}\n\n"
                            f"Texto:\n{document_text}"
                        ),
                    },
                ],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        payload = json.loads(content)
        return normalize_result(EXTRACTION_RESULT_ADAPTER.validate_python(payload))


def build_llm_client(provider: str, model: str, api_key: str | None, base_url: str) -> BaseLlmClient:
    if provider == "openai_compatible" and api_key:
        return OpenAICompatibleLlmClient(base_url=base_url, api_key=api_key, model=model)
    return MockLlmClient()
