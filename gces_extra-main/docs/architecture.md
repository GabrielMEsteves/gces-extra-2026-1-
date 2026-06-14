# Arquitetura

## Objetivo

Este documento descreve a arquitetura do pipeline de UDA, os principais componentes e as decisoes tecnicas adotadas para resistir a variacoes de layout em PDFs corporativos de RI.

## Principios de projeto

- evitar dependencia de layout fixo
- privilegiar idempotencia e rastreabilidade
- separar coleta, extracao e servico
- manter o contrato semantico como fronteira de qualidade
- permitir operacao com LLM real ou extrator local de desenvolvimento

## Camadas

### 1. Coleta e ingestao

Arquivos relevantes:

- [ri_polling.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/ri_polling.py)
- [fetcher.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/fetcher.py)
- [pipeline.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/pipeline.py)

Responsabilidades:

- descobrir links de PDF nas centrais de resultados
- aplicar filtro por palavras-chave
- baixar apenas arquivos novos
- impedir reprocessamento pelo catalogo de hashes

### 2. Parsing e analise documental

Arquivos relevantes:

- [pdf_parser.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/pdf_parser.py)
- [ocr.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/ocr.py)
- [chunking.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/chunking.py)

Responsabilidades:

- extrair texto de PDFs com `PyMuPDF` ou `pypdf`
- classificar documentos de baixa densidade textual como `hybrid`
- aplicar OCR nas paginas pobres em texto
- decidir entre `full scan` e `chunking`

### 3. Extracao semantica

Arquivos relevantes:

- [extraction.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/extraction.py)
- [llm.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/llm.py)
- [periods.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/periods.py)

Responsabilidades:

- enviar texto integral ou trechos relevantes para o extrator
- usar LLM compativel com `JSON Schema` ou extrator mock local
- extrair periodo de referencia
- consolidar metricas sem depender de coordenadas do PDF

### 4. Contrato semantico e validacao

Arquivos relevantes:

- [models.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/domain/models.py)
- [contract.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/contract.py)
- [validation.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/validation.py)

Responsabilidades:

- definir a forma exata da resposta
- normalizar metricas canonicas
- remover ambiguidades
- exigir evidencia textual
- impedir contaminacao do banco por percentuais indevidos

### 5. Persistencia e API

Arquivos relevantes:

- [db.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/db.py)
- [api.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/api.py)

Responsabilidades:

- persistir documentos, hashes, status e payloads
- persistir metricas com periodo e confianca
- expor consultas estruturadas por empresa e periodo

## Idempotencia

O pipeline usa dois niveis de idempotencia:

- `url_hash`
  - evita processar novamente a mesma URL
- `file_hash`
  - evita custo duplicado quando a mesma URL muda ou quando URLs diferentes apontam para o mesmo PDF

## Linhagem

Cada metrica persistida preserva:

- empresa
- periodo
- URL do PDF original
- URL da pagina de resultados
- trecho de evidencia textual
- data de processamento

## Decisao entre Full Scan e Chunking

- documentos curtos ou suficientemente compactos seguem por `full scan`
- documentos longos seguem por `chunking`
- o chunking e orientado por termos de relevancia como `vso`, `vendas`, `estoque`, `lancamentos`, `receita`, `unidades`

## Validacao real da arquitetura

Casos confirmados:

- Direcional 1T26: extraido diretamente em layout tabular textual
- MRV 1T26: classificado como `hybrid` e extraido via OCR fallback em quadro operacional
