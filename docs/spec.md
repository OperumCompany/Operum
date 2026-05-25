# Specification — Operum v2

> Especificação detalhada do sistema.
> Última atualização: 24/05/2026

---

## 1. Escopo

Este documento especifica os requisitos funcionais, contratos de API, formatos de dados e regras de UX para a evolução do Operum com foco em **módulo de notícias**, **módulo de carteiras**, **motor financeiro** e **motores de IA**.

---

## 2. Requisitos Funcionais

### 2.1 Módulo de Notícias

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| N-01 | Coletar notícias automaticamente de fontes gratuitas | Alta |
| N-02 | Normalizar campos e remover duplicatas | Alta |
| N-03 | Detectar tickers e entidades mencionadas | Alta |
| N-04 | Calcular sentimento (-1 a 1), relevância (0-1), impacto (0-1) | Alta |
| N-05 | Gerar resumo extrativo de cada notícia | Média |
| N-06 | Agrupar notícias em clusters temáticos | Média |
| N-07 | Exibir lista paginada com filtros | Alta |
| N-08 | Abrir modal ao clicar em notícia | Alta |
| N-09 | Vincular notícias a ativos e carteiras | Alta |
| N-10 | Relacionar notícias relevantes à carteira ativa | Alta |

**Filtros obrigatórios:**
- Classe de ativo
- Ticker
- Setor
- País/região
- Sentimento (positivo/negativo/neutro)
- Impacto (alto/médio/baixo)
- Intervalo de tempo
- Apenas notícias da carteira ativa
- Apenas notícias macroeconômicas

**Modal de notícia:**
- Título
- Fonte
- Data/hora
- Resumo
- Ativos impactados (com links)
- Score de impacto
- Link para notícia original

### 2.2 Módulo de Carteiras

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| C-01 | Criar carteira com nome e moeda base | Alta |
| C-02 | Listar todas as carteiras do usuário | Alta |
| C-03 | Editar nome e configurações da carteira | Alta |
| C-04 | Excluir carteira com confirmação | Alta |
| C-05 | Adicionar ativo à carteira (ticker, quantidade, preço médio) | Alta |
| C-06 | Remover ativo da carteira | Alta |
| C-07 | Calcular automaticamente pesos por ativo, classe, setor, moeda | Alta |
| C-08 | Calcular concentração da carteira | Alta |
| C-09 | Calcular correlação média entre ativos | Alta |
| C-10 | Exibir notícias relacionadas à carteira | Alta |
| C-11 | Exibir análise de risco (VaR, volatilidade, drawdown) | Média |

**Universo de ativos:** ~200+ ativos incluindo:
- Ações da bolsa brasileira (B3)
- Fundos imobiliários (FIIs)
- Ativos norte-americanos (BDRs e ETFs)
- Criptomoedas (Bitcoin, Ethereum + principais)

### 2.3 Motor Financeiro

| ID | Função | Prioridade |
|----|--------|-----------|
| F-01 | compute_simple_return | Alta |
| F-02 | compute_log_return | Alta |
| F-03 | compute_cumulative_return | Alta |
| F-04 | compute_volatility | Alta |
| F-05 | compute_covariance_matrix | Alta |
| F-06 | compute_correlation_matrix | Alta |
| F-07 | compute_beta | Alta |
| F-08 | compute_alpha | Alta |
| F-09 | compute_var | Alta |
| F-10 | compute_cvar | Alta |
| F-11 | compute_drawdown | Alta |
| F-12 | compute_moving_average | Média |
| F-13 | compute_ema | Média |
| F-14 | compute_rsi | Média |
| F-15 | compute_macd | Média |
| F-16 | compute_portfolio_weights | Alta |
| F-17 | compute_portfolio_return | Alta |
| F-18 | compute_portfolio_volatility | Alta |
| F-19 | compute_portfolio_concentration | Alta |
| F-20 | compute_capm_expected_return | Média |
| F-21 | compute_cagr | Média |

### 2.4 Motores de IA

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| AI-01 | Classificar relevância de notícias com TF-IDF + Logistic Regression | Alta |
| AI-02 | Ranquear impacto de notícias com LightGBM Ranker | Alta |
| AI-03 | Agrupar notícias em clusters temáticos (K-Means) | Média |
| AI-04 | Projetar retorno futuro de ativos (XGBoost, alvos 1d/5d/20d) | Alta |
| AI-05 | Calcular score consolidado de opinião da carteira | Alta |
| AI-06 | Gerar texto analítico explicando a carteira | Média |
| AI-07 | Exibir cenários probabilísticos futuros | Média |

---

## 3. Contratos de API

### 3.1 Health

```
GET /health
Response: { "status": "ok", "timestamp": "..." }
```

### 3.2 Assets

```
GET /assets/universe
Response: Asset[]

GET /assets/search?q=petr
Query: q (string, min 2 chars)
Response: Asset[]
```

### 3.3 Market

```
GET /market/price/{ticker}
Params: ticker (string)
Response: { "ticker": "PETR4", "price": 31.20, "currency": "BRL", "updated_at": "..." }

GET /market/history/{ticker}
Query: period (string, default "6mo"), interval (string, default "1d")
Response: { "ticker": "...", "prices": [{"date": "...", "close": 31.20, ...}] }
```

### 3.4 News

```
GET /news
Query:
  - ticker (string, optional)
  - asset_class (string, optional)
  - sector (string, optional)
  - country (string, optional)
  - sentiment (string: positive|negative|neutral, optional)
  - impact (string: high|medium|low, optional)
  - date_from (string ISO, optional)
  - date_to (string ISO, optional)
  - portfolio_id (string UUID, optional)
  - macro_only (boolean, optional)
  - page (int, default 1)
  - page_size (int, default 20)
Response: { "items": NewsItem[], "total": int, "page": int }

GET /news/{id}
Response: NewsItem

POST /news/reindex
Response: { "status": "ok", "ingested": int }

POST /news/summarize/{id}
Response: { "id": "...", "summary": "..." }
```

### 3.5 Portfolios

```
GET /portfolios
Response: Portfolio[]

POST /portfolios
Body: { "name": string, "base_currency": string }
Response: Portfolio

GET /portfolios/{id}
Response: Portfolio

PUT /portfolios/{id}
Body: { "name"?: string, "settings"?: {...} }
Response: Portfolio

DELETE /portfolios/{id}
Response: { "status": "deleted" }

POST /portfolios/{id}/positions
Body: { "ticker": string, "quantity": float, "avg_price"?: float }
Response: Portfolio

DELETE /portfolios/{id}/positions/{ticker}
Response: Portfolio

GET /portfolios/{id}/analysis
Response: { "weights": {...}, "concentration": float, "correlation_matrix": [[...]], "volatility": float, "var": float, "cvar": float, "beta": float, "drawdown": float }

GET /portfolios/{id}/news
Query: same filters as GET /news (default scope = this portfolio)
Response: { "items": NewsItem[], "total": int }

GET /portfolios/{id}/scenarios
Response: { "scenarios": { "1d": {...}, "5d": {...}, "30d": {...} }, "confidence": float }
```

### 3.6 Models

```
GET /models/status
Response: { "forecast_models": [...], "forecast_count": int, "news_scoring": "fallback", "clustering": "available", "opinion": "available" }

POST /models/train/forecast/{ticker}
Params: ticker (string)
Response: { "status": "trained"|"error", "ticker": "...", "train_r2": float, "test_r2": float }

GET /models/forecast/{ticker}
Response: { "ticker": "...", "last_price": float, "predicted_return_1d": float, "predicted_price_1d": float, "direction": "up"|"down", "confidence": float, "generated_at": "..." }

GET /models/forecast/trained
Response: { "tickers": [string] }

POST /models/cluster/news
Response: { "status": "ok", "num_news": int, "num_clusters": int, "clusters": {...} }

GET /models/opinion/{portfolio_id}
Response: { "score": float, "components": { "diversification": float, "correlation_risk": float, "news_impact": float, "macro_sensitivity": float, "forecast_risk": float }, "opinion": string }
```

---

## 4. Formatos de Dados

### 4.1 Asset Schema (Pydantic)

```python
class Asset(BaseModel):
    ticker: str
    name: str
    asset_class: str  # BR_STOCK | FII | US_STOCK | CRYPTO | FIXED_INCOME
    country: str
    currency: str
    sector: str
    sub_type: str = ""
    source: str = "yfinance"
```

### 4.2 Portfolio Schema (Pydantic)

```python
class Position(BaseModel):
    asset_id: str
    ticker: str
    asset_class: str
    quantity: float
    avg_price: float | None = None
    currency: str = "BRL"
    manual_notes: str = ""

class PortfolioSettings(BaseModel):
    risk_profile: str = "moderado"
    forecast_horizon_days: int = 5

class Portfolio(BaseModel):
    id: str
    name: str
    base_currency: str = "BRL"
    created_at: datetime
    updated_at: datetime
    positions: list[Position] = []
    settings: PortfolioSettings = PortfolioSettings()
```

### 4.3 NewsItem Schema (Pydantic)

```python
class NewsItem(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    content_preview: str = ""
    full_text_if_available: str | None = None
    source_name: str
    source_url: str
    published_at: datetime
    language: str = "pt"
    tags: list[str] = []
    mentioned_assets: list[str] = []
    mentioned_countries: list[str] = []
    mentioned_sectors: list[str] = []
    sentiment_score: float = 0.0
    relevance_score: float = 0.0
    impact_score: float = 0.0
    summary: str = ""
    cluster_id: int | None = None
    created_at: datetime
```

---

## 5. Regras de UX

### 5.1 Geral
- Notícias em lista com scroll infinito ou paginação
- Cards compactos com: título, fonte, data, badges de ativos, score de impacto
- Modal ao clicar com detalhes completos
- Sidebar de filtros (esquerda ou superior)
- Carteira ativa global no header
- Toda análise depende da carteira ativa

### 5.2 Tela de Carteira (interna)
- 4 blocos obrigatórios:
  1. Composição atual (tabela + gráficos)
  2. Notícias mais relevantes para a carteira
  3. Análise de risco/correlação
  4. Cenários futuros

### 5.3 Regras de Opinião da Carteira
- **Nunca** emitir recomendação de compra/venda
- **Sempre** apresentar como análise descritiva
- Cenários futuros devem ser probabilísticos, não determinísticos
- Exemplos válidos:
  - "Sua carteira está concentrada em risco doméstico"
  - "Exposição elevada a notícias de juros"
  - "Cripto com alta sensibilidade ao noticiário global"

---

## 6. Critérios de Aceite por Onda

### Onda 1
- [x] `uvicorn` sobe sem erros
- [x] `GET /health` responde 200
- [x] Universo com ~131+ ativos carregado
- [x] CRUD de carteiras funciona via API
- [x] Frontend lista carteiras do backend
- [x] Usuário adiciona ativos à carteira
- [x] `npm run build` passa sem erros

### Onda 2
- [x] Notícias são coletadas (YFinance + RSS)
- [x] Filtros funcionam via API
- [x] Modal de notícia abre com dados reais
- [x] Notícias relacionadas aparecem na carteira

### Onda 3
- [x] Funções financeiras retornam valores corretos (20 testes)
- [x] Análise de carteira retorna weights, correlation, VaR
- [x] Gráficos de composição (CompositionCharts) + métricas (PortfolioMetrics) funcionam

### Onda 4
- [x] Modelo de relevância treina e classifica (TF-IDF + LR / LightGBM Ranker)
- [x] Forecast de ativos gera projeções (XGBoost, requer treino via API)
- [x] Opinião consolidada da carteira (PortfolioOpinionService)
- [x] Cenários futuros (ScenarioView no Dashboard)

### Onda 5
- [x] 30 testes do backend passam (20 finance engine + 10 API)
- [x] Logs de ingestão em `data/logs/operum.log`
- [x] Estados de loading/erro/empty no frontend
- [x] Mensagens de confiança/incerteza nos cenários

## 7. Pós-Onda 5 — Correções e Ajustes

### 7.1 HTML Stripping em RSS
- Adicionado `NewsIngestionService._strip_html()` para remover tags HTML e entidades de conteúdo RSS.
- Necessário porque feeds como InfoMoney retornam `<p><img ...>` como `summary`.

### 7.2 Correção de Sentiment Score
- `score_sentiment()` agora retorna `-0.1` para textos neutros (sem keywords), em vez de `0.0`.
- Fórmula corrigida de `(pos-neg)/(total+1)` para `(pos-neg)/total`.
- Keywords expandidas (+10 termos) para melhor cobertura.

### 7.3 Carteira de Exemplo
- "Carteira Exemplo" criada no sistema com 8 ativos (5 BR_STOCK, 2 FII, 1 BDR).
- Serve como onboarding visual para novos usuários.

### 7.4 Dependência de Servidor
- Frontend (Vite) proxy `/api` → `localhost:8001`. Backend (uvicorn) deve estar rodando.
- Sem backend, Vite retorna `ECONNREFUSED` e frontend exibe erro de carregamento.
- Porta migrada de 8000 → 8001 para evitar TIME_WAIT no Windows.

### 7.5 Bug Fix — main.py
- `AssetUniverseService.get_universe()` não existe. Corrigido para `get_all()` em `app/main.py:27`.
- Lifespan do FastAPI agora executa corretamente no startup.

## 8. Onda 6 — Melhorias na Carteira em Detalhes e IA

### 8.1 Backend

#### 8.1.1 Auto-Startup
- `app/main.py` usa `lifespan` do FastAPI para executar tarefas na inicialização.
- Dispara `NewsIngestionService.ingest()` automaticamente.
- Atualiza cache de preços para os primeiros 20 ativos do universo.

#### 8.1.2 Endpoint de Preços
```
GET /api/portfolios/{id}/prices
Response: {
  "portfolio_id": string,
  "portfolio_name": string,
  "total_value": number | null,
  "positions": [{
    "ticker": string,
    "asset_class": string,
    "quantity": number,
    "avg_price": number | null,
    "current_price": number | null,
    "currency": string,
    "total_value": number | null,
    "name": string,
    "weight_pct": number | null
  }]
}
```

#### 8.1.3 Análise Enriquecida com Notícias
- `PortfolioOpinionService._generate_text()` agora inclui para cada ativo:
  - Número de notícias relevantes
  - Sentimento médio (positivo/negativo/neutro)
  - Impacto médio

### 8.2 Frontend

#### 8.2.1 PortfolioDetailsPage Reformulada
- **Tabelas separadas por classe**: BR_STOCK, FII, BDR, CRYPTO cada um em seu próprio card.
- **Filtro por tipo**: select de classe de ativo antes do select de ativo.
- **Preços reais**: colunas de preço atual, valor total e % da carteira.
- **Editar nome inline**: botão ao lado de "Voltar" no header.
- **CompositionCharts** movido para o final da página.

#### 8.2.2 PortfolioAnalysisAI
- Novo componente na página de detalhes.
- Botão "Gerar análise por IA" → chama `GET /api/models/opinion/{id}`.
- Exibe: score circular colorido, label (Saudável/Atenção/Crítico), texto analítico, barras dos 5 componentes.
- Estados de loading (spinner), erro (retry) e vazio (CTA inicial).

### 8.3 Componente Button
- Agora suporta `variant: 'primary' | 'ghost'`.
- `ghost` exibe botão com fundo transparente e borda.
