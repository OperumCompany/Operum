# Compendium — Operum

> Base de conhecimento consolidada do projeto Operum.
> Última atualização: 23/05/2026

---

## 1. Visão Geral

O Operum é uma aplicação full-stack para **acompanhamento de carteiras de investimento**, **leitura de notícias de mercado** e **análise financeira com IA**. O projeto evoluiu de um frontend React estático para uma arquitetura com backend Python/FastAPI, persistência local em arquivos e três motores de IA independentes.

**Público-alvo:** Investidores pessoa física que querem entender a composição e os riscos de suas carteiras, com notícias filtradas por relevância pessoal.

---

## 2. Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Frontend | React 18 + TypeScript + Vite |
| UI | Tailwind CSS + CSS custom properties |
| Gráficos | Recharts |
| Ícones | Lucide React |
| Roteamento | React Router DOM v6 |
| Backend | Python 3.11+ / FastAPI |
| Persistência | Arquivos locais (JSON + Parquet) |
| Preços | YFinance (gratuito) |
| Notícias | RSS feeds + YFinance news |
| ML/DL | scikit-learn, XGBoost, LightGBM |
| Agendamento | schedule library |

---

## 3. Arquitetura

### 3.1 Visão em Camadas

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│  Pages → Context → API Client → fetch()             │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (JSON)
┌──────────────────────▼──────────────────────────────┐
│              API Layer (FastAPI)                      │
│  Endpoints → Schemas (Pydantic) → Services           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              Service Layer                            │
│  AssetUniverse  │  Portfolio  │  News                 │
│  MarketData     │  Financial  │  Forecast             │
│  Opinion        │  ML Models  │  Storage              │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│           Persistence Layer (LocalStorageService)     │
│  JSON files  │  Parquet files  │  Cache               │
└─────────────────────────────────────────────────────┘
```

### 3.2 Separação de Responsabilidades

- **Cálculo financeiro clássico** → funções puras em `financial_engine.py`
- **IA de notícias** → classificação + ranking + clustering
- **Forecast de ativos** → modelo tabular (XGBoost)
- **Análise de carteira** → composição de scores + texto analítico

### 3.3 Estrutura de Pastas

```
operum/
├── app/              # Backend Python/FastAPI
│   ├── api/          # Endpoints
│   ├── core/         # Config
│   ├── schemas/      # Pydantic models
│   └── services/     # Lógica de negócio
├── src/              # Frontend React
│   ├── components/   # UI components
│   ├── context/      # Estado global
│   ├── data/         # Tipos e mocks legados
│   ├── layout/       # AppShell
│   ├── pages/        # Telas
│   ├── types/        # Interfaces TS
│   └── utils/        # Helpers
├── data/             # Persistência local
│   ├── assets/       # universe.json
│   ├── news/         # raw/processed/summaries
│   ├── portfolios/   # JSON por carteira
│   ├── market/       # prices/*.parquet
│   ├── cache/        # Cache de requisições
│   ├── datasets/     # train/*.parquet
│   ├── models/       # .pkl / .json
│   └── logs/         # Logs de ingestão
├── docs/             # Documentação
├── notebooks/        # Experimentação
├── scripts/          # Utilitários
└── tests/            # Testes
```

---

## 4. Modelo de Dados

### 4.1 Asset

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | Código do ativo (PETR4, BTC, etc.) |
| name | string | Nome completo |
| asset_class | enum | BR_STOCK, FII, US_STOCK, CRYPTO, FIXED_INCOME |
| country | string | BR, US, global |
| currency | string | BRL, USD |
| sector | string | Petróleo, Mineração, Tecnologia, etc. |
| sub_type | string | Ação ON, BDR, ETF, etc. |
| source | string | yfinance, b3, etc. |

### 4.2 Portfolio

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | string (UUID) | Identificador único |
| name | string | Nome da carteira |
| base_currency | string | BRL (padrão) |
| created_at | datetime | Data de criação |
| updated_at | datetime | Data de atualização |
| positions | Position[] | Lista de posições |
| settings | object | risk_profile, forecast_horizon_days |

### 4.3 Position

| Campo | Tipo | Descrição |
|-------|------|-----------|
| asset_id | string | Ticker do ativo |
| ticker | string | Mesmo que asset_id |
| asset_class | string | Classe do ativo no momento da adição |
| quantity | float | Quantidade |
| avg_price | float? | Preço médio opcional |
| currency | string | Moeda do ativo |
| manual_notes | string | Observações |

### 4.4 NewsItem

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | string | UUID |
| title | string | Título |
| subtitle | string? | Subtítulo |
| content_preview | string | Preview do conteúdo |
| full_text_if_available | string? | Texto completo |
| source_name | string | Nome da fonte |
| source_url | string | URL original |
| published_at | datetime | Data de publicação |
| language | string | pt, en |
| tags | string[] | Tags genéricas |
| mentioned_assets | string[] | Tickers mencionados |
| mentioned_countries | string[] | Países mencionados |
| mentioned_sectors | string[] | Setores mencionados |
| sentiment_score | float | -1 a 1 |
| relevance_score | float | 0 a 1 |
| impact_score | float | 0 a 1 |
| summary | string | Resumo gerado |
| cluster_id | int? | ID do cluster temático |
| created_at | datetime | Data de ingestão |

---

## 5. API Endpoints

### 5.1 Health
- `GET /health`

### 5.2 Assets
- `GET /assets/universe` — Lista completa
- `GET /assets/search?q=` — Busca por ticker/nome

### 5.3 Market
- `GET /market/price/{ticker}` — Preço atual
- `GET /market/history/{ticker}` — Histórico de preços

### 5.4 News
- `GET /news` — Lista com filtros (ticker, class, sector, country, sentiment, impact, date_from, date_to, portfolio_only)
- `GET /news/{id}` — Detalhe
- `POST /news/reindex` — Reingestão
- `POST /news/summarize/{id}` — Gerar resumo

### 5.5 Portfolios
- `GET /portfolios` — Lista
- `POST /portfolios` — Criar
- `GET /portfolios/{id}` — Detalhe
- `PUT /portfolios/{id}` — Atualizar
- `DELETE /portfolios/{id}` — Remover
- `POST /portfolios/{id}/positions` — Adicionar posição
- `DELETE /portfolios/{id}/positions/{ticker}` — Remover posição
- `GET /portfolios/{id}/analysis` — Análise financeira
- `GET /portfolios/{id}/news` — Notícias relacionadas
- `GET /portfolios/{id}/scenarios` — Cenários futuros

### 5.6 Models
- `GET /models/status` — Status dos modelos
- `POST /models/train/forecast/{ticker}` — Treinar XGBoost para um ativo
- `GET /models/forecast/{ticker}` — Previsão de retorno 1d
- `GET /models/forecast/trained` — Listar tickers com modelo treinado
- `POST /models/cluster/news` — Clusterizar notícias (K-Means)
- `GET /models/opinion/{portfolio_id}` — Opinião consolidada da carteira

---

## 6. Motor Financeiro

### 6.1 Funções Implementadas

```python
compute_simple_return(prices)
compute_log_return(prices)
compute_cumulative_return(prices)
compute_volatility(returns, window)
compute_covariance_matrix(returns_df)
compute_correlation_matrix(returns_df)
compute_beta(asset_returns, market_returns)
compute_alpha(asset_returns, market_returns, risk_free_rate)
compute_var(returns, confidence_level)
compute_cvar(returns, confidence_level)
compute_drawdown(prices)
compute_moving_average(prices, window)
compute_ema(prices, span)
compute_rsi(prices, window)
compute_macd(prices)
compute_portfolio_weights(positions)
compute_portfolio_return(weights, returns)
compute_portfolio_volatility(weights, cov_matrix)
compute_portfolio_concentration(weights)
compute_capm_expected_return(risk_free_rate, beta, market_return)
compute_cagr(initial_value, final_value, periods)
```

---

## 7. Motores de IA

### 7.1 Motor de Notícias

| Componente | Técnica | Entrada | Saída |
|-----------|---------|---------|-------|
| Classificador de relevância | TF-IDF + Logistic Regression | Texto da notícia | relevance_score (0-1) |
| Sentimento | Keyword-based (pos/neg keywords) | Texto da notícia | sentiment_score (-1 a 1), neutro = -0.1 |
| Rankeamento de impacto | LightGBM Ranker | Features textuais + temporais | impact_score (0-1) |
| Cluster temático | K-Means sobre TF-IDF | Vetores de texto | cluster_id |
| Resumo | Extrativo/templateado | Texto completo | summary |

### 7.2 Motor de Forecast de Ativos

| Componente | Técnica | Alvo |
|-----------|---------|------|
| Baseline | XGBoost Regressor | Retorno futuro 1d/5d/20d |
| Benchmark | LightGBM / CatBoost | Retorno futuro 1d/5d/20d |

Features: lags de retorno, volatilidade móvel, volume relativo, máximas/mínimas recentes, médias móveis, betas, correlação com índices, score de notícia, contagem de notícias, sentimento agregado.

### 7.3 Motor de Opinião da Carteira

```
portfolio_opinion_score =
  0.30 * diversification_score +
  0.20 * correlation_risk_score +
  0.20 * news_impact_score +
  0.15 * macro_sensitivity_score +
  0.15 * forecast_risk_score
```

Saída: texto analítico (ex: "Carteira com concentração moderada em risco doméstico"), nunca recomendação financeira.

---

## 8. Princípios de Design

1. **Separação total** entre cálculo financeiro clássico e aprendizado de máquina
2. **Persistência abstrata** via `LocalStorageService` — preparado para migrar para banco depois
3. **Cenários probabilísticos**, nunca previsões determinísticas
4. **Funcionalidade correta primeiro**, estética depois
5. **Carteira ativa global** guia toda a experiência do usuário

---

## 9. Glossário

| Termo | Definição |
|-------|-----------|
| VaR | Value at Risk — perda máxima esperada em dado nível de confiança |
| CVaR | Conditional VaR — perda média além do VaR |
| CAPM | Capital Asset Pricing Model — retorno esperado = risco-free + beta * prêmio |
| CAGR | Compound Annual Growth Rate — taxa de crescimento anual composta |
| RSI | Relative Strength Index — indicador de momentum |
| MACD | Moving Average Convergence Divergence — indicador de tendência |
| Sharpe | Retorno ajustado ao risco (não implementado ainda) |
| Beta | Sensibilidade do ativo ao mercado |
| Alpha | Retorno acima do esperado pelo CAPM |
| Drawdown | Queda do pico ao vale |

---

## 10. Logs e Monitoramento

- Logs estruturados via módulo `logging` do Python.
- Formato: `timestamp | LEVEL | module | mensagem`
- Handler: stdout (console) + arquivo rotativo em `data/logs/operum.log`.
- Configuração centralizada em `app/core/config.py`.
- Logs de ingestão de notícias registram quantidade ingerida, erros por fonte.

---

## 11. Tratamento de Dados de Notícias

### 11.1 Limpeza de HTML
- RSS feeds (InfoMoney, Folha) retornam conteúdo com tags HTML (`<p>`, `<img>`, etc.).
- `NewsIngestionService._strip_html()` remove tags HTML e entidades (`&amp;`, `&lt;`, `&gt;`, `&quot;`, `&#\d+;`) antes de armazenar `content_preview`.
- Chamado dentro de `_clean_text()` em conjunto com correção de encoding (latin1 → utf-8).

### 11.2 Scoring de Sentimento
- Algoritmo baseado em keywords positivas/negativas (~30 palavras cada).
- Fórmula: `(pos_count - neg_count) / total` quando há match, `-0.1` para neutro (sem keywords).
- Keywords expandidas: inclui "sobe", "recorde", "dividendo", "desemprego", "inflação", "juros", "tarifa" etc.
- Valores típicos: -1.0 (fortemente negativo), 1.0 (fortemente positivo), -0.1 (neutro).

### 11.3 Exemplo de Carteira
- `data/portfolios/` contém a carteira "Carteira Exemplo" com 8 ativos:
  - PETR4, VALE3, ITUB4, WEGE3, BBAS3 (BR_STOCK)
  - HGLG11, KNRI11 (FII)
  - AAPL34 (BDR)
