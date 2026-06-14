# Matriz de Aderencia aos Criterios

## Escopo

Esta matriz relaciona os criterios de avaliacao do desafio com os componentes implementados no projeto e com as evidencias disponiveis.

## 1. Qualidade do Contrato Semantico

Status: atendido

Implementacao:

- `Pydantic` para schema tipado
- `JSON Schema` para provedores compativeis de LLM
- validacao semantica posterior
- normalizacao de metricas canonicas
- exigencia de evidencia textual

Arquivos:

- [models.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/domain/models.py)
- [contract.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/contract.py)
- [validation.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/validation.py)

Evidencia:

- testes automatizados
- descarte de metricas ambiguas
- `9 passed`

## 2. Resiliencia contra Variacoes de Layout

Status: atendido

Implementacao:

- parser textual com `PyMuPDF`
- classificacao `hybrid` para documentos com baixa densidade textual
- OCR fallback com `tesseract`
- extracao para caso tabular e para caso em slides

Arquivos:

- [pdf_parser.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/pdf_parser.py)
- [ocr.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/ocr.py)
- [llm.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/llm.py)

Evidencia:

- Direcional 1T26
- MRV 1T26
- [validation_report.md](C:/Users/keita/Desktop/gces-extra/docs/validation_report.md)

## 3. Extracao de Valores Absolutos

Status: atendido

Implementacao:

- regra semantica para preferir valor absoluto
- validacao posterior para rejeitar percentuais em metricas nao percentuais
- extracao da primeira coluna operacional quando o quadro compara periodos

Arquivos:

- [llm.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/llm.py)
- [validation.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/validation.py)

Evidencia:

- teste de percentuais versus absolutos
- Direcional extraida com valores absolutos
- MRV extraida do quadro operacional OCR

## 4. Modelagem Temporal e API

Status: atendido

Implementacao:

- `reference_year` e `reference_quarter` no documento
- `year` e `quarter` por metrica
- filtros na API por empresa, ano e trimestre
- catalogo de documentos e metadados de linhagem

Arquivos:

- [db.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/db.py)
- [api.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/api.py)
- [periods.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/periods.py)

Evidencia:

- endpoints implementados
- testes passando

## 5. Extracao Automatizada e Continua

Status: atendido

Implementacao:

- worker continuo
- polling configuravel
- descoberta de PDFs em paginas de resultados
- deduplicacao por hash

Arquivos:

- [worker.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/worker.py)
- [ri_polling.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/ri_polling.py)
- [pipeline.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/services/pipeline.py)
- [db.py](C:/Users/keita/Desktop/gces-extra/src/uda_pipeline/db.py)

## Conclusao

No estado atual, os criterios tecnicos do desafio estao cobertos por implementacao, testes e evidencia real com dois PDFs de empresas diferentes.
