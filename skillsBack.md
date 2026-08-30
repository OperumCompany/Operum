---
name: skillsBack
description: Guia de execucao para IA contribuir no backend do Operum com Python, FastAPI, persistencia local, ingestao de noticias e motores de IA financeira.
updated_at: 2026-06-01
---

# Skills Back - Operum

## 1. Stack real do backend

- Python 3.11+
- FastAPI
- Pydantic v2
- Persistencia local em JSON + Parquet
- yfinance para precos
- Noticias por RSS e listagens abertas oficiais/editoriais
- scikit-learn, XGBoost, LightGBM
- pytest

Regras:
- nao introduzir banco relacional sem pedido explicito
- nao espalhar IO direto fora do `LocalStorageService`
- nao introduzir LLM externa por padrao

## 2. Estrutura de pastas

```text
app/
  api/
  core/
  schemas/
  services/
data/
  assets/
  news/
  portfolios/
  market/
  cache/
  datasets/
  models/
  logs/
tests/
```

## 3. Checklist antes de codar

1. Ler `docs/compendium.md`
2. Ler `docs/spec.md`
3. Conferir `app/schemas/`
4. Conferir `app/services/local_storage_service.py`
5. Respeitar fluxo `api -> services -> storage/schemas`

## 4. Camadas

### API
- routers FastAPI
- sem regra de negocio relevante

### Schemas
- modelos Pydantic de request/response
- manter compatibilidade de contrato

### Services
- regra de negocio real
- podem se compor entre si
- nao dependem de FastAPI

### Persistencia
- tudo passa por `LocalStorageService`
- JSON para entidades pequenas
- Parquet para series e datasets

## 5. Noticias: estado atual

### Arquitetura

O `NewsIngestionService` nao trabalha mais com uma lista plana unica. Ele usa um catalogo de fontes com metadados:

- `source_id`
- `source_name`
- `source_type`
- `enabled`
- `base_url`
- `feed_url` ou `listing_url`
- `is_official`
- `source_category`

Tipos praticos hoje:
- `rss`
- `official_listing`
- `official_notice_feed`
- `editorial_listing`
- `api_proxy`

### Fontes oficiais

- CVM
  - `cvm_decisoes`
  - `cvm_legislacao`
  - `cvm_audiencias`
  - `cvm_sancionadores`
  - `cvm_despachos`
  - `cvm_informativos`
- B3
  - `b3_comunicados`
- Tesouro
  - `tesouro_noticias`
- BCB
  - `bcb_copom`
  - `bcb_noticias`
  - cobertura parcial por limitacao do portal publico

### Fontes editoriais

- `folha_mercado`
- `infomoney`
- `investing_br`

### Regras importantes

- fontes oficiais tem maior confianca factual
- fontes editoriais entram como contexto complementar
- `yfinance` continua apenas como complemento temporario
- filtros editoriais existem para remover ruido obvio

### Persistencia de noticias

- `data/news/raw/archive.json`
- `data/news/raw/latest.json`
- `data/news/raw/meta.json`

### Backfill

- `POST /api/news/backfill`
- aceita `start_date`
- aceita `source_id` opcional
- manter backfill seletivo quando a fonte suportar historico sem autenticacao

## 6. `NewsItem` atual

Campos que precisam ser preservados:

- `source_id`
- `source_type`
- `is_official`
- `source_category`

Esses campos alimentam ranking e transparencia da analise.

## 7. IA interna

### Servicos principais

| Servico | Arquivo | Papel |
|---------|---------|-------|
| Scoring de noticias | `news_scoring_service.py` | relevancia, impacto e sentimento |
| Resumo | `news_summary_service.py` | resumo local em 2 paragrafos |
| Clustering | `news_clustering_service.py` | K-Means sobre TF-IDF |
| Forecast | `forecast_service.py` | previsao tabular por ativo |
| Analise por ativo | `asset_analysis_service.py` | ranking + templates + contexto |
| Opiniao da carteira | `portfolio_opinion_service.py` | sintese geral da composicao |

### `AssetAnalysisService`

Regras atuais:
- analise e recalculada no clique
- nao reutilizar cache antigo como resposta ativa
- separar noticias em `asset`, `sector` e `macro`
- priorizar `preco + noticias`
- se preco for fraco, usar noticias historicas do periodo

Campos relevantes no retorno:
- `analysis_sections`
- `historical_window`
- `used_news_count`
- `source_groups`
- `recomputed_at`

### Ranking de noticias

O ranking hoje leva em conta:
- `match_score`
- `impact_score`
- `relevance_score`
- `source_confidence_weight`
- `macro_context_weight`
- prioridade de contexto

Confianca por tipo de fonte:
- official_notice_feed: mais alta
- official_listing: muito alta
- rss/editorial: intermediaria
- api_proxy: menor

### Topicos dominantes

Cobertura atual:
- juros
- inflacao
- cambio
- commodities
- fiscal/politica
- geopolitica
- dividendos
- resultados

## 8. PortfolioOpinionService

O endpoint `GET /api/models/opinion/{portfolio_id}` nao retorna mais apenas `opinion`.

Estrutura atual relevante:
- `score`
- `components`
- `headline`
- `composition_grade`
- `composition_summary`
- `strengths`
- `overlaps`
- `block_reviews`
- `final_diagnosis`
- `conclusion`
- `sources`
- `source_groups`

## 9. Carteiras

Estado atual importante para backend:
- limite de 50 carteiras
- exclusao em lote suportada por `POST /api/portfolios/bulk-delete`
- testes devem usar storage isolado para nao poluir `data/portfolios`

## 10. Testes

- usar `pytest`
- API com cliente ASGI
- preferir storage temporario ou `OPERUM_DATA_DIR` para isolamento

Checks minimos:
- `python -m pytest -q`
- contratos novos de noticias e opiniao preservados

## 11. O que nao fazer

- nao remover campos de contrato sem ajustar frontend e docs
- nao misturar regra de ranking com camada HTTP
- nao tratar fontes editoriais como equivalentes factuais as oficiais
- nao deixar testes escreverem em `data/` principal se houver alternativa

## 12. Documento vivo

Sempre atualizar este arquivo quando houver mudancas em:
- catalogo de fontes
- contratos de `NewsItem`
- endpoints de noticias
- analise por ativo
- opiniao da carteira
- persistencia de portfolios ou noticias
