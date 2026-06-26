# Specification - Operum

> Especificacao funcional, contratos de API e regras de produto.
> Ultima atualizacao: 26/06/2026

---

## 1. Escopo

O Operum cobre quatro blocos principais:

- modulo de noticias com ingestao multi-fonte, historico local e filtros
- modulo de carteiras com CRUD, detalhamento por classe e analise financeira
- motor financeiro com funcoes puras
- camada de IA interna para analise por ativo e sintese da carteira

Fora de escopo por enquanto:
- ativos de renda fixa, incluindo Tesouro Direto, CDB, LCI/LCA e poupanca

---

## 2. Requisitos Funcionais

### 2.1 Modulo de Noticias

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| N-01 | Coletar noticias de fontes oficiais e editoriais publicas | Alta |
| N-02 | Normalizar noticias em schema unico com metadados de origem | Alta |
| N-03 | Persistir historico em `archive.json` e janela curta em `latest.json` | Alta |
| N-04 | Deduplicar por hash considerando titulo, fonte e data | Alta |
| N-05 | Calcular sentimento, relevancia e impacto | Alta |
| N-06 | Gerar resumo local em 2 paragrafos curtos | Alta |
| N-07 | Exibir lista paginada com 30 itens por pagina | Alta |
| N-08 | Suportar busca textual server-side e filtros combinados | Alta |
| N-09 | Suportar `reindex` e `backfill` por fonte | Alta |
| N-10 | Relacionar noticias a ativos, setores e contexto macro | Alta |

**Fontes suportadas**
- Oficiais:
  - CVM
  - B3
  - BCB com cobertura parcial
- Editoriais:
  - Folha Mercado
  - InfoMoney
  - Investing Brasil
- Complemento temporario:
  - yfinance news

**Filtros obrigatorios**
- `ticker`
- `asset_class`
- `sector`
- `country`
- `sentiment`
- `impact`
- `date_from`
- `date_to`
- `portfolio_id`
- `macro_only`
- `q`

### 2.2 Modulo de Carteiras

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| C-01 | Criar carteira com nome e moeda base | Alta |
| C-02 | Listar carteiras do usuario com paginacao local de 10 por pagina | Alta |
| C-03 | Limitar a 50 carteiras no total | Alta |
| C-04 | Excluir carteira individualmente | Alta |
| C-05 | Excluir carteiras em lote por modo de selecao | Alta |
| C-06 | Adicionar ativo com ticker, quantidade e preco medio | Alta |
| C-07 | Remover posicao da carteira | Alta |
| C-08 | Exibir tabelas por classe de ativo na tela de detalhe | Alta |
| C-09 | Exibir precos atuais, valor total e peso por posicao | Alta |
| C-10 | Exibir analise financeira e noticias relacionadas | Alta |
| C-11 | Exibir analise por IA por ativo e geral da carteira | Alta |

### 2.3 Motor Financeiro

| ID | Funcao | Prioridade |
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
| F-12 | compute_moving_average | Media |
| F-13 | compute_ema | Media |
| F-14 | compute_rsi | Media |
| F-15 | compute_macd | Media |
| F-16 | compute_portfolio_weights | Alta |
| F-17 | compute_portfolio_return | Alta |
| F-18 | compute_portfolio_volatility | Alta |
| F-19 | compute_portfolio_concentration | Alta |
| F-20 | compute_capm_expected_return | Media |
| F-21 | compute_cagr | Media |

### 2.4 IA Interna

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| AI-01 | Classificar relevancia de noticias com TF-IDF + Logistic Regression | Alta |
| AI-02 | Ranquear noticias com features textuais, temporais e peso por fonte | Alta |
| AI-03 | Agrupar noticias em clusters tematicos | Media |
| AI-04 | Projetar retorno futuro de ativos com XGBoost | Alta |
| AI-05 | Gerar analise individual por ativo sem LLM externa | Alta |
| AI-06 | Gerar sintese geral da carteira com foco em composicao | Alta |
| AI-07 | Separar noticia de ativo, setor e macro na analise | Alta |

---

## 3. Contratos de API

### 3.1 Health

```http
GET /health
Response: { "status": "ok", "timestamp": "..." }
```

### 3.2 Assets

```http
GET /assets/universe
GET /assets/search?q=petr
```

### 3.3 Market

```http
GET /market/price/{ticker}
GET /market/history/{ticker}?period=6mo&interval=1d
```

**Fontes de dados de mercado**
- brapi e a fonte primaria para ativos de renda variavel listados no Brasil, incluindo acoes, FIIs, BDRs, ETFs e indices suportados.
- Yahoo Finance e fallback para tickers `.SA`/B3 e fonte direta para criptoativos e indices globais quando a brapi nao cobrir.
- A variavel `BRAPI_TOKEN` pode ser definida no ambiente para chamadas autenticadas.

### 3.4 News

```http
GET /news
Query:
  - ticker
  - asset_class
  - sector
  - country
  - sentiment
  - impact
  - date_from
  - date_to
  - portfolio_id
  - macro_only
  - q
  - page (default 1)
  - page_size (default 30)

Response:
{
  "items": NewsItem[],
  "total": int,
  "page": int,
  "page_size": int,
  "total_pages": int
}
```

```http
GET /news/{id}
POST /news/reindex
POST /news/summarize/{id}
POST /news/backfill
Body:
{
  "start_date": "2026-05-01",
  "source_id": "optional"
}
```

### 3.5 Portfolios

```http
GET /portfolios
POST /portfolios
GET /portfolios/{id}
PUT /portfolios/{id}
DELETE /portfolios/{id}
POST /portfolios/bulk-delete
POST /portfolios/{id}/positions
DELETE /portfolios/{id}/positions/{ticker}
GET /portfolios/{id}/analysis
GET /portfolios/{id}/prices
GET /portfolios/{id}/news
GET /portfolios/{id}/scenarios
```

### 3.6 Models

```http
GET /models/status
POST /models/train/forecast/{ticker}
GET /models/forecast/{ticker}
GET /models/forecast/trained
POST /models/cluster/news
GET /models/opinion/{portfolio_id}
GET /models/opinion/{portfolio_id}/positions/{ticker}
```

**Resposta de `GET /models/opinion/{portfolio_id}`**

```json
{
  "portfolio_id": "uuid",
  "score": 0.74,
  "components": {
    "diversification": 0.8,
    "correlation_risk": 0.6,
    "news_impact": 0.7,
    "macro_sensitivity": 0.68,
    "forecast_risk": 0.72
  },
  "headline": "...",
  "composition_grade": "7.5 / 10",
  "composition_summary": "...",
  "strengths": ["..."],
  "overlaps": ["..."],
  "block_reviews": [{"title": "...", "body": "..."}],
  "final_diagnosis": "...",
  "conclusion": "...",
  "sources": [],
  "source_groups": []
}
```

**Resposta de `GET /models/opinion/{portfolio_id}/positions/{ticker}`**

```json
{
  "portfolio_id": "uuid",
  "ticker": "PETR4",
  "asset_name": "Petrobras PN",
  "asset_class": "BR_STOCK",
  "generated_at": "...",
  "recomputed_at": "...",
  "confidence": "media",
  "status": "ok",
  "current_snapshot": {},
  "recent_performance": {},
  "outlook_3m": {},
  "historical_window": {
    "start_date": "2026-03-01",
    "end_date": "2026-06-01",
    "news_count": 12,
    "has_price_history": false
  },
  "analysis_sections": {
    "current": "...",
    "recent": "...",
    "outlook": "..."
  },
  "used_news_count": 12,
  "sources": [],
  "source_groups": []
}
```

---

## 4. Formatos de Dados

### 4.1 Asset

```python
class Asset(BaseModel):
    ticker: str
    name: str
    asset_class: str
    country: str
    currency: str
    sector: str
    sub_type: str = ""
    source: str = "brapi"
```

### 4.2 Portfolio

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

### 4.3 NewsItem

```python
class NewsItem(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    content_preview: str = ""
    full_text_if_available: str | None = None
    source_name: str
    source_url: str
    source_id: str = ""
    source_type: str = "rss"
    is_official: bool = False
    source_category: str | None = None
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

### 5.1 Noticias
- Lista paginada com 30 itens por pagina
- Navegacao com setas e paginas numeradas
- Busca e filtros sempre reiniciam a pagina para `1`
- Modal exibe resumo em 2 paragrafos

### 5.2 Carteiras
- Tela de listagem com 10 carteiras por pagina e maximo de 5 paginas
- Exclusao em lote e ativada por icone de lixeira no topo da secao
- Cada card continua com lixeira individual

### 5.3 Carteira em Detalhe
- Tabelas por classe de ativo
- Analise geral da carteira em card dedicado
- Botao de estrela por ativo para analise individual
- Fontes agrupadas por origem tanto na analise por ativo quanto na analise geral

### 5.4 Regras da IA
- Nunca emitir recomendacao direta de compra ou venda
- Explicitar baixa confianca quando faltarem dados
- Priorizar:
  1. noticia direta do ativo
  2. noticia de setor
  3. noticia macro contextual

---

## 6. Regras de Ranking de Noticias

- Fontes oficiais tem maior peso factual
- Fontes editoriais tem peso contextual medio
- yfinance tem peso menor
- `context_role` pode ser:
  - `asset`
  - `sector`
  - `macro`
- O ranking da analise por ativo considera:
  - match direto por ticker/alias
  - compatibilidade por setor e pais
  - recencia
  - impacto e relevancia
  - peso da fonte
  - peso de contexto macro

---

## 7. Criterios de Aceite

- `GET /news` retorna `page_size=30` e `total_pages`
- `POST /news/backfill` aceita `source_id` opcional
- `GET /models/opinion/{portfolio_id}/positions/{ticker}` retorna `historical_window`, `source_groups` e `used_news_count`
- noticias oficiais e editoriais coexistem no acervo sem quebrar resumo, scoring ou clustering
- a analise do ativo usa noticias do periodo quando o historico de preco for insuficiente
- a UI de fontes agrupadas funciona tanto na analise do ativo quanto na analise da carteira

---

## 8. Observacoes Operacionais

- Backend roda na porta `8001`
- O startup faz ingestao e aquecimento em background para nao bloquear a inicializacao
- O BCB permanece no catalogo, mas hoje pode retornar pouco ou nada por limitacao tecnica do portal publico
