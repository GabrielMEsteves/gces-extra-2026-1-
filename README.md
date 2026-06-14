# Pipeline UDA de Relatorios de RI

Pipeline em Python para localizar, baixar, processar e consultar dados de
relatorios de relacoes com investidores. O projeto foi pensado para o setor
habitacional, com foco em previas operacionais de incorporadoras.

A aplicacao transforma PDFs em metricas estruturadas, mantendo o vinculo com a
fonte original. O resultado pode ser acessado por uma API FastAPI ou consultado
diretamente no catalogo SQLite.

## O que o sistema entrega

- Monitoramento de paginas de RI configuradas em JSON.
- Download de PDFs novos, com controle de duplicidade por hash.
- Extracao de texto com `PyMuPDF`, fallback por `pypdf` e OCR opcional.
- Escolha automatica entre leitura integral e chunking semantico.
- Extracao de metricas com contrato `Pydantic`.
- Validacao para reduzir ambiguidades, metricas fora do catalogo e uso indevido
  de percentuais.
- Persistencia de documentos, metricas, periodo de referencia e evidencia
  textual.
- API para ingestao, listagem de documentos, consulta de conjuntura e catalogo
  de metricas.

## Sumario

- [Comeco rapido](#comeco-rapido)
- [Configuracao](#configuracao)
- [Como o pipeline funciona](#como-o-pipeline-funciona)
- [Arquitetura](#arquitetura)
- [API](#api)
- [Contrato dos dados](#contrato-dos-dados)
- [Validacao com dados reais](#validacao-com-dados-reais)
- [Organizacao do codigo](#organizacao-do-codigo)
- [Documentacao adicional](#documentacao-adicional)

## Comeco rapido

Requisitos:

- Python 3.11 ou superior.
- PowerShell no Windows.
- Opcional para OCR real: `tesseract`, `pytesseract`, `Pillow` e `PyMuPDF`.

Instale o projeto com as dependencias de desenvolvimento:

```bash
pip install -e .[dev]
```

Crie o arquivo local de variaveis:

```bash
copy .env.example .env
```

Suba a API:

```bash
uvicorn uda_pipeline.api:app --reload
```

Rode um ciclo continuo de ingestao:

```bash
python -m uda_pipeline.worker
```

Execute a suite de testes:

```bash
pytest
```

## Configuracao

As fontes de RI ficam em `config/sources.json`. Cada entrada define a empresa,
a pagina monitorada e as regras basicas para aceitar links de PDF.

As variaveis de ambiente ficam em `.env.example`:

- `UDA_DB_PATH`: caminho do banco SQLite.
- `UDA_STORAGE_DIR`: pasta usada para armazenar PDFs baixados.
- `UDA_SOURCES_FILE`: arquivo JSON com as fontes monitoradas.
- `UDA_POLL_INTERVAL_SECONDS`: intervalo do worker continuo.
- `UDA_LLM_PROVIDER`: `mock` ou `openai_compatible`.
- `UDA_LLM_MODEL`: modelo usado na extracao por LLM.
- `UDA_LLM_API_KEY`: chave do provedor externo.
- `UDA_LLM_BASE_URL`: URL de uma API compativel com OpenAI.
- `UDA_MAX_FULL_SCAN_CHARS`: limite para extracao em leitura integral.
- `UDA_MAX_LLM_RETRIES`: quantidade de tentativas de reparo semantico.
- `UDA_ENABLE_OCR_FALLBACK`: ativa OCR em paginas com pouco texto.

Por padrao, o projeto pode funcionar com o extrator `mock`, util para testes e
validacoes locais sem custo de API externa.

## Como o pipeline funciona

O fluxo principal segue esta ordem:

1. Carrega as fontes configuradas.
2. Descobre candidatos a documento nas paginas de RI.
3. Calcula o hash da URL e ignora documentos ja descobertos.
4. Baixa o PDF e calcula o hash do arquivo.
5. Marca arquivos repetidos como duplicados.
6. Analisa o PDF para extrair texto e diagnosticar o layout.
7. Usa OCR quando habilitado e quando o ambiente possui suporte.
8. Decide entre `full_scan` e `chunking`.
9. Envia o texto relevante para o extrator.
10. Normaliza metricas, aliases, periodo e evidencias.
11. Valida o resultado antes de persistir.
12. Grava documento e metricas no SQLite.

Esse desenho evita depender de coordenadas fixas do PDF. Em vez disso, a
extracao usa texto, densidade de caracteres, blocos de conteudo e termos
semanticos ligados a indicadores operacionais.

## Arquitetura

```text
Paginas de RI
    |
    v
Descoberta de links
    |
    v
Controle por url_hash
    |
    v
Download do PDF
    |
    v
Controle por file_hash
    |
    v
Parser de PDF + OCR opcional
    |
    +--> full_scan
    |
    +--> chunking semantico
    |
    v
Extrator mock ou LLM compativel
    |
    v
Contrato semantico
    |
    v
Validacao e saneamento
    |
    v
Catalogo SQLite
    |
    v
API FastAPI
```

## API

Endpoints disponiveis:

- `GET /health`: verifica se o servico esta ativo.
- `POST /api/ingestion/run`: executa um ciclo de ingestao sob demanda.
- `GET /api/documents`: lista documentos descobertos e processados.
- `GET /api/conjuntura`: consulta metricas por empresa, ano e trimestre.
- `GET /api/metrics/catalog`: lista o catalogo de metricas suportadas.

Exemplo de consulta:

```bash
curl "http://127.0.0.1:8000/api/conjuntura?empresa=MRV&ano=2026&trimestre=1"
```

## Contrato dos dados

As metricas extraidas passam por normalizacao e validacao antes de serem
persistidas. O contrato garante que:

- apenas metricas conhecidas no catalogo sejam mantidas;
- aliases sejam convertidos para codigos canonicos;
- cada metrica carregue periodo, empresa, valor e confianca quando possivel;
- evidencias textuais sejam associadas ao valor extraido;
- valores percentuais nao substituam metricas absolutas;
- duplicidades no mesmo periodo sejam consolidadas pela maior confianca.

Metricas canonicas atualmente tratadas:

- `lancamentos`
- `vendas_liquidas`
- `vso`
- `estoque`
- `receita`
- `unidades`
- `repasses`
- `distratos`

## Validacao com dados reais

O diretorio `data/fixtures/real_pdfs` contem PDFs reais usados para validar
comportamentos importantes do pipeline.

Arquivos principais:

- `manifest.json`: valores esperados para cada fixture.
- `mrv_previa_1t26.pdf`: PDF com apresentacao em formato de slides.
- `direcional_previa_1t26.pdf`: PDF com conteudo tabular.
- `validation_output.json`: saida consolidada da validacao.

Para executar a validacao:

```bash
python scripts/run_real_fixture_validation.py
```

Cobertura de comportamento:

- MRV 1T26: layout hibrido, VSO, lancamentos, vendas liquidas e unidades.
- Direcional 1T26: layout textual/tabular, lancamentos, vendas liquidas, VSO,
  unidades e estoque.

## Organizacao do codigo

```text
config/
  sources.json
  sources.example.json
data/
  fixtures/
    real_pdfs/
docs/
scripts/
  run_real_fixture_validation.py
src/
  uda_pipeline/
    api.py
    bootstrap.py
    config.py
    db.py
    worker.py
    domain/
    services/
tests/
```

Modulos principais:

- `api.py`: definicao dos endpoints HTTP.
- `bootstrap.py`: montagem das dependencias da aplicacao.
- `db.py`: schema e operacoes SQLite.
- `worker.py`: loop de execucao continua.
- `services/ri_polling.py`: descoberta de documentos.
- `services/pipeline.py`: orquestracao da ingestao.
- `services/pdf_parser.py`: leitura e diagnostico dos PDFs.
- `services/chunking.py`: selecao de trechos relevantes.
- `services/extraction.py`: coordenacao da extracao.
- `services/llm.py`: extrator mock e cliente LLM compativel.
- `services/contract.py`: catalogo e normalizacao.
- `services/validation.py`: validacoes semanticas.

## Documentacao adicional

- [Arquitetura detalhada](docs/architecture.md)
- [Operacao e runbook](docs/operations.md)
- [Matriz de avaliacao](docs/evaluation_matrix.md)
- [Relatorio de validacao](docs/validation_report.md)
