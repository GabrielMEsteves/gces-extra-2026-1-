from __future__ import annotations

from fastapi import FastAPI, Query

from uda_pipeline.bootstrap import build_pipeline
from uda_pipeline.domain.models import ConjunturaResponse, DocumentRecord, DocumentsResponse, HealthResponse, IngestionSummary, MetricCatalogResponse
from uda_pipeline.services.contract import METRIC_CATALOG

app = FastAPI(title="UDA Pipeline API", version="0.1.0")
db, pipeline = build_pipeline()


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/api/ingestion/run", response_model=IngestionSummary)
def run_ingestion() -> IngestionSummary:
    summary = pipeline.run_once()
    return summary


@app.get("/api/documents", response_model=DocumentsResponse)
def list_documents(empresa: str | None = Query(default=None)) -> DocumentsResponse:
    rows = db.list_documents(company=empresa)
    return DocumentsResponse(items=[DocumentRecord.model_validate(dict(row)) for row in rows])


@app.get("/api/conjuntura", response_model=ConjunturaResponse)
def get_conjuntura(
    empresa: str | None = Query(default=None),
    ano: int | None = Query(default=None, ge=2000),
    trimestre: int | None = Query(default=None, ge=1, le=4),
) -> ConjunturaResponse:
    rows = db.query_conjuntura(company=empresa, year=ano, quarter=trimestre)
    return ConjunturaResponse(items=rows)


@app.get("/api/metrics/catalog", response_model=MetricCatalogResponse)
def get_metric_catalog() -> MetricCatalogResponse:
    return MetricCatalogResponse(metrics=METRIC_CATALOG)
