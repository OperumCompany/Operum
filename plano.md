# Plano de Implementação — Operum v2

> Documento vivo. Atualizar conforme o progresso das ondas.

---

## 🎯 Resumo

Evoluir o Operum de frontend React estático para aplicação full-stack com **FastAPI + React + persistência local em arquivos**, focando em **módulo de notícias**, **módulo de carteiras**, **motor financeiro clássico** e **3 motores de IA independentes**.

---

## 📋 Documentação

| Documento | Status | Descrição |
|-----------|--------|-----------|
| `docs/compendium.md` | ✅ Feito | Base de conhecimento consolidada |
| `docs/spec.md` | ✅ Feito | Especificação detalhada |
| `skillsFront.md` | ✅ Feito | Atualizado com regras de integração backend |
| `skillsBack.md` | ✅ Feito | Guia de contribuição backend Python |
| `README.md` | ✅ Feito | Atualizado descrição full-stack |
| `plano.md` | ✅ Feito | Este documento |

---

## 🌊 Ondas de Implementação

### Onda 1 — Fundação

**Objetivo:** Backend FastAPI rodando, persistência local, universo de ativos, CRUD de carteiras, frontend adaptado.

| Tarefa | Status |
|--------|--------|
| `requirements.txt` com dependências | ✅ Feito |
| `app/main.py` — FastAPI + CORS | ✅ Feito |
| `app/core/config.py` | ✅ Feito |
| `app/schemas/asset.py` | ✅ Feito |
| `app/schemas/portfolio.py` | ✅ Feito |
| `app/schemas/news.py` | ✅ Feito |
| `app/services/local_storage_service.py` | ✅ Feito |
| `app/services/asset_universe_service.py` | ✅ Feito (131 ativos) |
| `app/services/portfolio_service.py` | ✅ Feito |
| `app/api/health.py` | ✅ Feito |
| `app/api/assets.py` | ✅ Feito |
| `app/api/portfolios.py` | ✅ Feito |
| `data/assets/universe.json` (~130+ ativos) | ✅ Feito |
| `data/portfolios/` estrutura | ✅ Feito |
| `src/utils/api.ts` — API client | ✅ Feito |
| `src/types/index.ts` — expandir tipos | ✅ Feito |
| `src/context/PortfoliosContext.tsx` — consumir API | ✅ Feito |
| `src/pages/PortfoliosPage.tsx` — fluxo real | ✅ Feito |
| `src/pages/PortfolioDetailsPage.tsx` — posições reais | ✅ Feito |
| `src/pages/NewsPage.tsx` — filtros + modal | ✅ Feito |
| `src/pages/DashboardPage.tsx` — adaptado | ✅ Feito |
| `src/pages/DashboardTechnicalPage.tsx` — adaptado | ✅ Feito |
| `src/pages/ChatPage.tsx` — adaptado | ✅ Feito |
| `src/data/mocks.ts` — alinhado tipos | ✅ Feito |
| `src/utils/portfolios.ts` — alinhado tipos | ✅ Feito |
| `vite.config.ts` — proxy `/api` | ✅ Feito |

**Critério de aceite:** Usuário cria carteira, busca ativos no universo, adiciona posições, vê composição.

---

### Onda 2 — Notícias

**Objetivo:** Ingestão de notícias, filtros, lista, modal, vínculo com ativos.

| Tarefa | Status |
|--------|--------|
| `app/services/news_ingestion_service.py` | ✅ Feito |
| `app/services/news_scoring_service.py` | ✅ Feito |
| `app/services/news_summary_service.py` | ✅ Feito |
| `app/api/news.py` | ✅ Feito |
| `data/news/raw/`, `processed/`, `summaries/` | ✅ Feito |
| Frontend: `NewsPage` com filtros reais | ✅ Feito |
| Frontend: `NewsCard` + `NewsModal` | ✅ Feito |
| Frontend: notícias em `PortfolioDetailsPage` | ✅ Feito |

**Critério de aceite:** Notícias filtráveis, modal com detalhes, vínculo com ativos/carteiras.

---

### Onda 3 — Motor Financeiro

**Objetivo:** Funções financeiras puras, análise de carteira, métricas de risco.

| Tarefa | Status |
|--------|--------|
| `app/services/financial_engine.py` (22 funções) | ✅ Feito |
| `app/services/portfolio_analytics_service.py` | ✅ Feito |
| `app/services/market_data_service.py` | ✅ Feito |
| `app/api/market.py` | ✅ Feito |
| `data/market/prices/*.parquet` | ✅ Feito |
| Frontend: `PortfolioMetrics` | ✅ Feito |
| Frontend: `CompositionCharts` | ✅ Feito |

**Critério de aceite:** Carteira exibe correlação, VaR, concentração, pesos, volatilidade.

---

### Onda 4 — IA

**Objetivo:** ML para notícias, forecast de ativos, opinião consolidada da carteira.

| Tarefa | Status |
|--------|--------|
| `app/services/news_clustering_service.py` | ✅ Feito |
| Upgrade `news_scoring_service.py` (LightGBM Ranker) | ✅ Feito |
| `app/services/forecast_service.py` (XGBoost) | ✅ Feito |
| `app/services/portfolio_opinion_service.py` | ✅ Feito |
| `app/api/models.py` | ✅ Feito |
| `data/datasets/train/`, `data/models/` | ✅ Feito |
| Frontend: `ScenarioView` | ✅ Feito |
| Frontend: "Opinião da Carteira" | ✅ Feito |

**Critério de aceite:** Notícias ranqueadas por impacto, projeções de retorno, opinião consolidada com cenários.

---

### Onda 5 — Polimento

**Objetivo:** Testes, logs, explicabilidade, UX final.

| Tarefa | Status |
|--------|--------|
| Testes unitários do backend (`tests/`) | ✅ Feito |
| Logs estruturados | ✅ Feito |
| Retreino local | ✅ Feito |
| Estados de loading/erro/empty frontend | ✅ Feito |
| Mensagens de confiança/incerteza | ✅ Feito |

**Critério de aceite:** Produto usável internamente de forma consistente.

---

## 📁 Estrutura Final

```
operum/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── assets.py
│   │   ├── market.py
│   │   ├── news.py
│   │   ├── portfolios.py
│   │   └── models.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── asset.py
│   │   ├── news.py
│   │   └── portfolio.py
│   └── services/
│       ├── __init__.py
│       ├── local_storage_service.py
│       ├── asset_universe_service.py
│       ├── market_data_service.py
│       ├── news_ingestion_service.py
│       ├── news_scoring_service.py
│       ├── news_clustering_service.py
│       ├── news_summary_service.py
│       ├── portfolio_service.py
│       ├── portfolio_analytics_service.py
│       ├── financial_engine.py
│       ├── portfolio_opinion_service.py
│       ├── forecast_service.py
│       └── model_training_service.py
├── data/
│   ├── assets/
│   ├── news/
│   │   ├── raw/
│   │   ├── processed/
│   │   └── summaries/
│   ├── portfolios/
│   ├── market/
│   │   └── prices/
│   ├── cache/
│   ├── datasets/
│   │   └── train/
│   ├── models/
│   └── logs/
├── src/            (frontend existente, adaptado)
├── notebooks/
├── scripts/
├── tests/
│   ├── __init__.py
│   ├── test_financial_engine.py
│   └── test_api.py
├── docs/
│   ├── compendium.md
│   └── spec.md
├── skillsFront.md  (atualizado)
├── skillsBack.md   (novo)
├── plano.md        (este arquivo)
├── README.md       (atualizado)
├── requirements.txt
└── package.json    (existente)
```

---

## 🔧 Decisões Técnicas

| Decisão | Escolha |
|---------|---------|
| Backend | Python FastAPI + uvicorn direto |
| Persistência | Arquivos JSON/Parquet via `LocalStorageService` |
| Preços | YFinance |
| Notícias | RSS feeds + YFinance news |
| Universo ativos | ~200+ ativos (BR, FIIs, US, crypto) |
| Integração dev | Proxy Vite `/api` → `localhost:8000` |
| Frontend | React 18 + Vite (existente, adaptado) |
| ML notícias | TF-IDF + Logistic Regression → LightGBM Ranker |
| Forecast ativos | XGBoost tabular |
| Agendamento | `schedule` library |
