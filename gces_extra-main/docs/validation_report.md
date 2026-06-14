# Validacao Final com PDFs Reais

## Fontes reais cadastradas

- MRV: `https://ri.mrv.com.br/informacoes-financeiras/central-de-resultados/`
- Direcional: `https://ri.direcional.com.br/informacoes-financeiras/central-de-resultados/`

## PDFs reais validados

1. MRV - Previa Operacional 1T26
   - PDF: `data/fixtures/real_pdfs/mrv_previa_1t26.pdf`
   - URL original: `https://api.mziq.com/mzfilemanager/v2/d/4b56353d-d5d9-435f-bf63-dcbf0a6c25d5/9d9c8de1-c30a-0260-a69f-5c1c06219644?origin=2`
   - Layout observado: slides com baixa densidade textual em varias paginas.
   - Resultado validado com OCR fallback:
     - `lancamentos = 2915.0`
     - `vendas_liquidas = 2469.0`
     - `unidades = 9747.0`
     - `vso = 21.5`
   - O parser classifica o documento como `hybrid` e aplica OCR nas paginas com baixo texto.

2. Direcional - Previa Operacional 1T26
   - PDF: `data/fixtures/real_pdfs/direcional_previa_1t26.pdf`
   - URL original: `https://api.mziq.com/mzfilemanager/v2/d/ada9bc2c-f7d0-4359-9eaf-851b679ab788/b9e3e792-da8b-5e49-f50f-4c097cf08623?origin=2`
   - Layout observado: tabela textual com comparativos trimestrais.
   - Valores usados na validacao:
     - `lancamentos = 1005.8`
     - `vendas_liquidas = 1582.0`
     - `vso = 24.0`
     - `estoque = 5178.0`
     - `unidades = 4848.0`

## Conclusao

- O pipeline agora possui evidencia reprodutivel com dois PDFs reais de empresas diferentes.
- O layout tabular da Direcional e validado por metrica.
- O layout em slides da MRV agora tambem possui extracao real via OCR fallback com `tesseract`.
