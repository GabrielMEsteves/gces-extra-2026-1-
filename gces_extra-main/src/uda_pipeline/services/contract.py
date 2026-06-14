from __future__ import annotations

from uda_pipeline.domain.models import ExtractedMetric, ExtractionResult
from uda_pipeline.services.validation import sanitize_result


METRIC_CATALOG: dict[str, str] = {
    "lancamentos": "Lancamentos",
    "vendas_liquidas": "Vendas Liquidas",
    "vso": "VSO",
    "estoque": "Estoque",
    "receita": "Receita",
    "unidades": "Unidades",
    "repasses": "Repasses",
    "distratos": "Distratos",
}

ALIASES: dict[str, str] = {
    "vendas liquidas": "vendas_liquidas",
    "vendas_liquidas": "vendas_liquidas",
    "vendas": "vendas_liquidas",
    "lancamentos": "lancamentos",
    "lancamento": "lancamentos",
    "vendas_líquidas": "vendas_liquidas",
}


def normalize_result(result: ExtractionResult) -> ExtractionResult:
    normalized_metrics: list[ExtractedMetric] = []
    warnings = list(result.warnings)

    for metric in result.metrics:
        raw_code = metric.metric_code.strip().lower()
        normalized_code = ALIASES.get(raw_code, raw_code)
        if normalized_code not in METRIC_CATALOG:
            warnings.append(f"Metrica descartada fora do catalogo: {metric.metric_code}")
            continue
        metric.metric_code = normalized_code
        metric.metric_label = METRIC_CATALOG[normalized_code]
        normalized_metrics.append(metric)

    result.metrics = normalized_metrics
    result.warnings = warnings
    return sanitize_result(result)
