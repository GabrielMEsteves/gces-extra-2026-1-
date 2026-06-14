# Operacao e Runbook

## Objetivo

Este documento descreve como operar o pipeline localmente, como executar a validacao real e como diagnosticar problemas comuns.

## Subir o sistema

### 1. Instalar dependencias

```bash
pip install -e .[dev]
```

### 2. Configurar ambiente

```bash
copy .env.example .env
```

### 3. Subir a API

```bash
uvicorn uda_pipeline.api:app --reload
```

### 4. Rodar o worker

```bash
python -m uda_pipeline.worker
```

## Rotinas principais

### Executar um ciclo manual de ingestao

```bash
curl -X POST http://127.0.0.1:8000/api/ingestion/run
```

### Consultar dados estruturados

```bash
curl "http://127.0.0.1:8000/api/conjuntura?empresa=Direcional&ano=2026&trimestre=1"
```

### Rodar os testes

```bash
pytest
```

### Rodar a validacao real

```bash
python scripts/run_real_fixture_validation.py
```

## Diagnostico

### Sintoma: OCR indisponivel

Verifique:

- se `tesseract.exe` esta instalado
- se `pytesseract` esta instalado
- se `Pillow` esta instalado
- se existe `eng.traineddata` ou `por.traineddata` em `tessdata`

### Sintoma: documento novo nao processa

Verifique:

- se a URL da fonte esta em `config/sources.json`
- se o HTML ainda contem links de PDF compatíveis com o filtro
- se o documento ja nao existe no banco por `url_hash` ou `file_hash`

### Sintoma: poucas metricas extraidas

Verifique:

- se o documento caiu em `full_scan` ou `chunking`
- se o layout exige OCR
- se a metrica existe no catalogo canonico
- se o trecho extraido e narrativo demais ou tabular demais para a heuristica atual

## Arquivos de evidencia

- Configuracao real das fontes: [config/sources.json](C:/Users/keita/Desktop/gces-extra/config/sources.json)
- Manifesto dos PDFs reais: [data/fixtures/real_pdfs/manifest.json](C:/Users/keita/Desktop/gces-extra/data/fixtures/real_pdfs/manifest.json)
- Resultado consolidado da validacao: [data/fixtures/real_pdfs/validation_output.json](C:/Users/keita/Desktop/gces-extra/data/fixtures/real_pdfs/validation_output.json)

## Artefatos esperados apos execucao

- banco SQLite em `data/uda.db`
- PDFs baixados em `data/storage`
- fixtures reais em `data/fixtures/real_pdfs`

## Limites atuais

- o OCR opera com fallback `eng` se `por.traineddata` nao estiver disponivel
- a API ainda nao tem versionamento explicito
- o banco padrao e SQLite, suficiente para o desafio e para validacao local
