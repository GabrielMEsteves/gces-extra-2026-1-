# Pipeline de UDA para Relatorios de RI

Pipeline de engenharia e analise de dados para coletar, processar e servir dados estruturados a partir de PDFs de previas operacionais e relatorios de RI de incorporadoras do setor habitacional.

O projeto foi construído para o desafio de UDA com quatro objetivos centrais:

1. Observar continuamente as centrais de resultados das empresas.
2. Coletar apenas documentos novos, evitando custo duplicado de LLM.
3. Extrair metricas sob uma otica semantica, sem depender de coordenadas fixas de PDF.
4. Servir os dados por API com modelagem temporal e linhagem.

## Sumario

- [Visao Geral](#visao-geral)
- [Arquitetura](#arquitetura)
- [Fluxo Ponta a Ponta](#fluxo-ponta-a-ponta)
- [Componentes do Projeto](#componentes-do-projeto)
- [Contrato Semantico](#contrato-semantico)
- [Resiliencia de Layout](#resiliencia-de-layout)
- [API](#api)
- [Instalacao e Execucao](#instalacao-e-execucao)
- [Configuracao](#configuracao)
- [Validacao Real](#validacao-real)
- [Mapeamento dos Criterios do Desafio](#mapeamento-dos-criterios-do-desafio)
- [Estrutura de Diretorios](#estrutura-de-diretorios)
- [Proximos Passos](#proximos-passos)

## Visao Geral

O pipeline possui tres camadas obrigatorias do desafio:

1. Camada de extracao de dados
   - polling das fontes de RI
   - download de PDFs
   - parsing textual com `PyMuPDF` e `pypdf`
   - OCR fallback com `tesseract` quando necessario
   - `full scan` ou `chunking` semantico conforme o documento
2. Contrato semantico dos dados
   - schema rigido com `Pydantic`
   - resposta estruturada via `JSON Schema` para LLM compativel
   - validacao semantica posterior para remover ambiguidades
3. Catalogo de dados e linhagem
   - catalogo SQLite de documentos e metricas
   - idempotencia por hash
   - trilha de origem ate a URL do PDF e a evidência textual extraida

## Arquitetura

Visao em alto nivel:

```text
RI Pages / Result Centers
        |
        v
RiPollingService
        |
        v
DocumentCandidate + url_hash
        |
        v
PdfFetcher -> file_hash -> Database(idempotencia)
        |
        v
PdfParser -> OCR fallback -> DocumentAnalysis
        |
        v
UdaExtractionService
  |             |
  |             +-> Full Scan
  |
  +-> Semantic Chunking
        |
        v
LLM / Mock Extractor
        |
        v
Semantic Contract + Validation Layer
        |
        v
SQLite Catalog + Lineage
        |
        v
FastAPI
```

Documentacao complementar:

- Arquitetura detalhada: [docs/architecture.md](C:/Users/keita/Desktop/gces-extra/docs/architecture.md)
- Operacao e runbook: [docs/operations.md](C:/Users/keita/Desktop/gces-extra/docs/operations.md)
- Matriz de aderencia aos criterios: [docs/evaluation_matrix.md](C:/Users/keita/Desktop/gces-extra/docs/evaluation_matrix.md)
- Validacao real com PDFs: [docs/validation_report.md](C:/Users/keita/Desktop/gces-extra/docs/validation_report.md)

## Fluxo Ponta a Ponta

1. O worker consulta as paginas de resultados configuradas em `config/sources.json`.
2. Cada link de PDF encontrado gera um `url_hash`.
3. Se o `url_hash` ja existir no catalogo, o documento e ignorado.
4. Caso contrario, o PDF e baixado e recebe um `file_hash`.
5. Se o `file_hash` ja existir, o documento e marcado como duplicado.
6. Se for novo, o PDF segue para o parser.
7. O parser escolhe estrategia textual normal ou `hybrid` com OCR fallback.
8. O extrator decide entre `full scan` e `chunking`.
9. O resultado passa por contrato semantico e validacao posterior.
10. Documentos e metricas sao persistidos com periodo, confianca e linhagem.
11. A API expõe os dados por empresa, ano e trimestre.

## Componentes do Projeto

Pontos principais do codigo:

- API: [src/uda_pipeline/api.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/api.py)
- Bootstrap e composicao de dependencias: [src/uda_pipeline/bootstrap.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/bootstrap.py)
- Worker continuo: [src/uda_pipeline/worker.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/worker.py)
- Banco e catalogo: [src/uda_pipeline/db.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/db.py)
- Polling das fontes: [src/uda_pipeline/services/ri_polling.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/ri_polling.py)
- Pipeline de ingestao: [src/uda_pipeline/services/pipeline.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/pipeline.py)
- Parser de PDF: [src/uda_pipeline/services/pdf_parser.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/pdf_parser.py)
- OCR fallback: [src/uda_pipeline/services/ocr.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/ocr.py)
- Chunking semantico: [src/uda_pipeline/services/chunking.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/chunking.py)
- Extracao UDA: [src/uda_pipeline/services/extraction.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/extraction.py)
- Cliente LLM e extrator mock: [src/uda_pipeline/services/llm.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/llm.py)
- Contrato e normalizacao: [src/uda_pipeline/services/contract.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/contract.py)
- Validacao semantica: [src/uda_pipeline/services/validation.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/validation.py)
- Normalizacao temporal: [src/uda_pipeline/services/periods.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/periods.py)

## Contrato Semantico

O contrato semantico e o principal mecanismo de blindagem contra alucinacao.

Ele combina:

1. Schema tipado em `Pydantic`
2. Saida estruturada via `JSON Schema` para LLM compativel
3. Validacao posterior das respostas
4. Normalizacao de metricas canonicas
5. Descarte de metricas ambiguas ou percentuais indevidos

Garantias implementadas:

- campos ausentes viram `null`
- metricas fora do catalogo sao descartadas
- metricas nao percentuais nao podem sobreviver com cara de percentual
- toda metrica precisa ter evidencia textual curta
- periodo de referencia e validado
- metricas duplicadas no mesmo periodo sao consolidadas pela maior confianca

## Resiliencia de Layout

O pipeline nao depende de coordenadas fixas de pixels.

Estratégias aplicadas:

- `full scan` para documentos curtos e textualizados
- `chunking` semantico para documentos longos
- parser `hybrid` para PDFs com baixa densidade textual
- OCR fallback com `tesseract` em paginas pobres em texto
- extracao tabular semantica para casos reais como Direcional
- extracao OCR de quadro operacional para slides como MRV

Casos reais validados:

- Direcional 1T26, layout tabular
- MRV 1T26, layout em slides

## API

Endpoints disponiveis:

- `GET /health`
- `POST /api/ingestion/run`
- `GET /api/documents`
- `GET /api/conjuntura?empresa=MRV&ano=2025&trimestre=3`
- `GET /api/metrics/catalog`

Contratos:

- `GET /health`
  - resposta: status simples do servico
- `POST /api/ingestion/run`
  - executa um ciclo de descoberta, download e processamento
- `GET /api/documents`
  - lista documentos catalogados, status e periodo de referencia
- `GET /api/conjuntura`
  - retorna metricas estruturadas com filtros por empresa e periodo
- `GET /api/metrics/catalog`
  - retorna o catalogo de metricas canonicas

## Instalacao e Execucao

### Requisitos

- Python 3.11+
- Windows com PowerShell
- opcional para OCR real:
  - `tesseract`
  - `pytesseract`
  - `Pillow`
  - `PyMuPDF`

### Instalar dependencias

```bash
pip install -e .[dev]
```

### Configurar ambiente

```bash
copy .env.example .env
```

O repositorio ja inclui [config/sources.json](C:/Users/keita/Desktop/gces-extra/config/sources.json) com fontes reais iniciais de MRV e Direcional.

### Subir a API

```bash
uvicorn uda_pipeline.api:app --reload
```

### Rodar o worker continuo

```bash
python -m uda_pipeline.worker
```

### Executar os testes

```bash
pytest
```

### Rodar a validacao real com PDFs

```bash
python scripts/run_real_fixture_validation.py
```

## Configuracao

Variaveis em [.env.example](C:/Users/keita/Desktop/gces-extra/.env.example):

- `UDA_DB_PATH`: caminho do banco SQLite
- `UDA_STORAGE_DIR`: diretorio de armazenamento de PDFs
- `UDA_SOURCES_FILE`: arquivo JSON de fontes
- `UDA_POLL_INTERVAL_SECONDS`: intervalo do polling
- `UDA_LLM_PROVIDER`: `mock` ou `openai_compatible`
- `UDA_LLM_MODEL`: modelo do provedor
- `UDA_LLM_API_KEY`: chave da API
- `UDA_LLM_BASE_URL`: base URL do provedor compativel
- `UDA_MAX_FULL_SCAN_CHARS`: limite para `full scan`
- `UDA_MAX_LLM_RETRIES`: tentativas de reparo semantico
- `UDA_ENABLE_OCR_FALLBACK`: habilita OCR nas paginas de baixo texto

## Validacao Real

Artefatos de evidencia:

- PDFs reais: [data/fixtures/real_pdfs](C:/Users/keita/Desktop/gces-extra/data/fixtures/real_pdfs)
- Manifesto: [data/fixtures/real_pdfs/manifest.json](C:/Users/keita/Desktop/gces-extra/data/fixtures/real_pdfs/manifest.json)
- Saida consolidada: [data/fixtures/real_pdfs/validation_output.json](C:/Users/keita/Desktop/gces-extra/data/fixtures/real_pdfs/validation_output.json)
- Relatorio detalhado: [docs/validation_report.md](C:/Users/keita/Desktop/gces-extra/docs/validation_report.md)

Resumo dos resultados reais:

- MRV 1T26
  - `parser_strategy=hybrid`
  - `lancamentos=2915.0`
  - `vendas_liquidas=2469.0`
  - `unidades=9747.0`
  - `vso=21.5`
- Direcional 1T26
  - `parser_strategy=text`
  - `lancamentos=1005.8`
  - `vendas_liquidas=1582.0`
  - `vso=24.0`
  - `unidades=4848.0`
  - `estoque=5178.0`

## Mapeamento dos Criterios do Desafio

O projeto atende os criterios tecnicos da seguinte forma:

1. Qualidade do contrato semantico
   - schema tipado
   - validacao posterior
   - descarte de percentuais indevidos
   - exigencia de evidencia textual
2. Resiliencia contra variacoes de layout
   - validacao real com MRV em slides
   - validacao real com Direcional em tabela
3. Extracao de valores absolutos
   - validacao para privilegiar valor bruto sobre variacao percentual
   - testes automatizados para esse comportamento
4. Modelagem temporal e API
   - periodo persistido em documentos e metricas
   - API com filtros por empresa, ano e trimestre

Matriz detalhada: [docs/evaluation_matrix.md](C:/Users/keita/Desktop/gces-extra/docs/evaluation_matrix.md)

## Estrutura de Diretorios

```text
config/
  sources.json
data/
  fixtures/
    real_pdfs/
docs/
scripts/
src/
  uda_pipeline/
tests/
```

## Proximos Passos

Melhorias nao obrigatorias para a entrega atual:

- instalar `por.traineddata` para OCR em portugues nativo
- ampliar o catalogo de metricas para mais indicadores do boletim
- adicionar versionamento de API
- migrar de SQLite para Postgres se o volume crescer
- adicionar observabilidade com logs estruturados e metricas de execucao
