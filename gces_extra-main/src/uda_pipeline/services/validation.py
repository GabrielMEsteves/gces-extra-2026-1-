from __future__ import annotations

from dataclasses import dataclass

from uda_pipeline.domain.models import ExtractedMetric, ExtractionResult


NON_PERCENT_METRICS = {
    "lancamentos",
    "vendas_liquidas",
    "estoque",
    "receita",
    "unidades",
    "repasses",
    "distratos",
}


@dataclass
class ValidationIssue:
    code: str
    message: str


def validate_result(result: ExtractionResult) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not result.company:
        issues.append(ValidationIssue(code="missing_company", message="company obrigatorio"))
    if result.reference_quarter is not None and result.reference_year is None:
        issues.append(ValidationIssue(code="quarter_without_year", message="quarter sem ano de referencia"))
    for metric in result.metrics:
        issues.extend(validate_metric(metric, result))
    return issues


def validate_metric(metric: ExtractedMetric, result: ExtractionResult) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if metric.quarter is not None and metric.year is None and result.reference_year is None:
        issues.append(ValidationIssue(code="metric_period_incomplete", message=f"{metric.metric_code} sem ano"))
    if not metric.source_excerpt:
        issues.append(ValidationIssue(code="missing_excerpt", message=f"{metric.metric_code} sem evidencia textual"))
    if metric.value is None:
        return issues
    excerpt = (metric.source_excerpt or "").lower()
    if metric.metric_code in NON_PERCENT_METRICS and _looks_like_percentage(metric.value, excerpt):
        issues.append(
            ValidationIssue(
                code="percentage_selected_as_absolute",
                message=f"{metric.metric_code} aparenta ser percentual e nao valor absoluto",
            )
        )
    return issues


def sanitize_result(result: ExtractionResult) -> ExtractionResult:
    deduped: dict[tuple[str, int | None, int | None], ExtractedMetric] = {}
    for metric in result.metrics:
        metric.year = metric.year or result.reference_year
        metric.quarter = metric.quarter or result.reference_quarter
        key = (metric.metric_code, metric.year, metric.quarter)
        current = deduped.get(key)
        if current is None or metric.confidence > current.confidence:
            deduped[key] = metric

    result.metrics = list(deduped.values())

    issues = validate_result(result)
    if issues:
        issue_codes = {issue.code for issue in issues}
        filtered: list[ExtractedMetric] = []
        for metric in result.metrics:
            drop_metric = False
            if metric.metric_code in NON_PERCENT_METRICS:
                excerpt = (metric.source_excerpt or "").lower()
                if _looks_like_percentage(metric.value, excerpt):
                    drop_metric = True
            if not drop_metric:
                filtered.append(metric)
        result.metrics = filtered
        result.warnings.extend(sorted({issue.message for issue in issues}))
        if "quarter_without_year" in issue_codes:
            result.reference_quarter = None
    return result


def build_validation_feedback(issues: list[ValidationIssue]) -> str:
    messages = "\n".join(f"- {issue.code}: {issue.message}" for issue in issues)
    return (
        "A resposta anterior violou o contrato semantico. Corrija mantendo apenas fatos sustentados pelo texto.\n"
        f"{messages}\n"
        "Se nao houver evidencia suficiente, retorne null ou remova a metrica."
    )


def _looks_like_percentage(value: float | None, excerpt: str) -> bool:
    if value is None:
        return False
    if "%" not in excerpt:
        return False
    return abs(value) <= 100
