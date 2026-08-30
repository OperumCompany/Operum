# Specification - Operum

> Especificacao funcional, contratos de API e regras de produto.
> Ultima atualizacao: 01/07/2026

---

## 1. Escopo

O Operum cobre os seguintes blocos principais do MVP:

- autenticacao e sessao
- preferencias do usuario
- modulo de carteiras com CRUD, detalhamento por classe e analise financeira
- modulo de dados de mercado para preco atual e historico
- modulo de noticias com ingestao multi-fonte, historico local e filtros
- dashboard resumido e dashboard tecnico
- chatbot educativo contextual
- camada de IA interna para analise por ativo e sintese da carteira
- observabilidade basica, logs e status do sistema

Fora de escopo por enquanto:
- sistema de pagamento
- integracao com corretoras
- execucao de ordens
- recomendacao automatica de compra e venda
- aplicativo mobile nativo
- painel administrativo completo
- social features
- suporte robusto a renda fixa analitica, incluindo Tesouro Direto, CDB, LCI/LCA e poupanca

---

## 2. Requisitos Funcionais

### 2.1 Autenticacao e Sessao

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| A-01 | Permitir cadastro de usuario com nome, email e senha | Alta |
| A-02 | Garantir unicidade de email | Alta |
| A-03 | Permitir login com email e senha | Alta |
| A-04 | Persistir sessao autenticada por token | Alta |
| A-05 | Permitir logout explicito | Alta |
| A-06 | Permitir alteracao de senha mediante senha atual valida | Alta |
| A-07 | Bloquear acesso a rotas privadas sem autenticacao | Alta |
| A-08 | Responder com erro claro para credenciais invalidas | Alta |

### 2.2 Preferencias do Usuario

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| P-01 | Permitir salvar temas de noticias de interesse | Alta |
| P-02 | Permitir salvar preferencia de modo compacto | Media |
| P-03 | Permitir salvar preferencia de alertas locais | Media |
| P-04 | Retornar preferencias do usuario autenticado | Alta |
| P-05 | Aplicar fallback para preferencias padrao quando nao houver registro salvo | Alta |

### 2.3 Modulo de Noticias

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
| N-11 | Permitir abrir detalhe da noticia com resumo e link original | Alta |
| N-12 | Persistir noticias processadas e embeddings de 384 dimensoes no Supabase Postgres | Alta |
| N-13 | Armazenar texto bruto localmente ou em bucket privado do Supabase Storage | Alta |
| N-14 | Suportar busca `hybrid`, `keyword` e `semantic` sem quebrar filtros e paginacao | Alta |
| N-15 | Usar fallback textual quando embeddings ou Supabase estiverem indisponiveis | Alta |

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

### 2.4 Modulo de Carteiras

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| C-01 | Criar carteira com nome e moeda base | Alta |
| C-02 | Listar carteiras do usuario com paginacao local de 10 por pagina | Alta |
| C-03 | Limitar a 50 carteiras no total | Alta |
| C-04 | Editar nome da carteira | Alta |
| C-05 | Excluir carteira individualmente | Alta |
| C-06 | Excluir carteiras em lote por modo de selecao | Alta |
| C-07 | Adicionar ativo com ticker, quantidade e preco medio opcional | Alta |
| C-08 | Remover posicao da carteira | Alta |
| C-09 | Exibir tabelas por classe de ativo na tela de detalhe | Alta |
| C-10 | Exibir precos atuais, valor total, P&L e peso por posicao | Alta |
| C-11 | Exibir noticias relacionadas a carteira | Alta |
| C-12 | Exibir analise por IA por ativo e geral da carteira | Alta |
| C-13 | Permitir selecao de carteira ativa no frontend | Alta |

### 2.5 Dados de Mercado

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| M-01 | Retornar preco atual de ativos suportados | Alta |
| M-02 | Retornar historico de preco por periodo e intervalo | Alta |
| M-03 | Utilizar fonte primaria e fallback quando necessario | Alta |
| M-04 | Expor erros claros para tickers nao suportados ou sem cobertura | Alta |

### 2.6 Dashboard e Visualizacoes

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| D-01 | Exibir resumo da carteira em foco | Alta |
| D-02 | Exibir composicao da carteira por ativos ou classes | Alta |
| D-03 | Exibir noticias relacionadas no dashboard resumido | Alta |
| D-04 | Exibir opiniao geral da carteira | Alta |
| D-05 | Exibir dashboard tecnico complementar para usuarios que queiram profundidade | Media |
| D-06 | Suportar estado vazio quando nao houver carteira ou ativos | Alta |
| D-07 | Suportar sucesso parcial quando um bloco falhar e outro carregar | Alta |

### 2.7 Chatbot Educativo

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| CH-01 | Permitir envio de mensagens de texto pelo usuario | Alta |
| CH-02 | Responder duvidas educativas basicas sobre investimentos | Alta |
| CH-03 | Usar carteira ativa como contexto quando aplicavel | Media |
| CH-04 | Nao emitir recomendacao direta de compra ou venda | Alta |
| CH-05 | Manter historico local de conversa por usuario | Media |

### 2.8 Motor Financeiro

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

### 2.9 IA Interna

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| AI-01 | Classificar relevancia de noticias com TF-IDF + Logistic Regression | Alta |
| AI-02 | Ranquear noticias com features textuais, temporais e peso por fonte | Alta |
| AI-03 | Agrupar noticias em clusters tematicos | Media |
| AI-04 | Projetar retorno futuro de ativos com XGBoost | Alta |
| AI-05 | Gerar analise individual por ativo sem LLM externa | Alta |
| AI-06 | Gerar sintese geral da carteira com foco em composicao | Alta |
| AI-07 | Separar noticia de ativo, setor e macro na analise | Alta |
| AI-08 | Explicitar baixa confianca quando faltarem dados suficientes | Alta |
| AI-09 | Recuperar noticias semanticamente com multilingual E5 + pgvector | Alta |
| AI-10 | Combinar similaridade semantica, texto, recencia, impacto e confianca da fonte | Alta |

---

## 3. Contratos de API

### 3.1 Health

```http
GET /health
Response: { "status": "ok", "timestamp": "..." }
```

### 3.2 Auth

```http
POST /auth/register
Body:
{
  "name": "Tomaz",
  "email": "tomaz@operum.app",
  "password": "Operum123"
}
```

```http
POST /auth/login
Body:
{
  "email": "tomaz@operum.app",
  "password": "Operum123"
}
Response:
{
  "token": "...",
  "user": User
}
```

```http
GET /auth/me
POST /auth/logout
PUT /auth/password
Body:
{
  "current_password": "old",
  "new_password": "new"
}
```

### 3.3 Preferences

```http
GET /auth/preferences
PUT /auth/preferences
Body:
{
  "topics": ["Inflacao", "Juros", "Acoes"],
  "compactMode": false,
  "notifications": true
}
```

### 3.4 Assets

```http
GET /assets/universe
GET /assets/search?q=petr
```

### 3.5 Market

```http
GET /market/price/{ticker}
GET /market/history/{ticker}?period=6mo&interval=1d
```

**Fontes de dados de mercado**
- brapi e a fonte primaria para ativos de renda variavel listados no Brasil, incluindo acoes, FIIs, BDRs, ETFs e indices suportados.
- Sem token, a listagem publica da brapi fornece a ultima cotacao disponivel para ativos B3 e o endpoint publico de graficos do Yahoo fornece o historico.
- Yahoo Finance via biblioteca permanece como ultimo fallback para tickers `.SA`/B3, criptoativos e indices globais.
- A variavel `BRAPI_TOKEN` habilita as chamadas autenticadas e detalhadas da brapi e deve permanecer apenas no backend.

### 3.6 News

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
  - search_mode (`hybrid`, `keyword` ou `semantic`; default `hybrid`)
  - page (default 1)
  - page_size (default 30)

Response:
{
  "items": NewsItem[],
  "total": int,
  "page": int,
  "page_size": int,
  "total_pages": int,
  "search_mode_used": string,
  "semantic_available": boolean
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

### 3.7 Portfolios

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
GET /portfolios/{id}/history?period=1m|6m|1y|max&ticker=PETR4
GET /portfolios/{id}/news
GET /portfolios/{id}/scenarios
```

`POST /portfolios/{id}/positions` aceita `occurred_at` opcional no formato `YYYY-MM-DD`. Quando omitido, usa a data atual. Cada adição registra uma movimentação e atualiza o preço médio ponderado da posição.

O histórico da carteira retorna:
- `points` com `market_value`, `invested_value`, `quantity`, `contribution_value` e `contribution_quantity` por data
- `available_tickers` para alternar entre consolidado e ativo
- `warnings` quando preço ou custo histórico estiver indisponível

Remover uma posição zera o saldo atual, mas preserva as movimentações anteriores para consulta histórica.

### 3.8 Models

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

### 4.1 User

```python
class User(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
```

### 4.2 Preferences

```python
class UserPreferences(BaseModel):
    topics: list[str] = []
    compactMode: bool = False
    notifications: bool = True
```

### 4.3 Asset

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

### 4.4 Portfolio

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

### 4.5 NewsItem

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

### 4.6 ChatMessage

```python
class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
```

---

## 5. Regras de UX

### 5.1 Estados de Tela

Toda tela principal do MVP deve suportar, quando aplicavel:
- estado vazio ou inicial
- estado carregando
- estado com sucesso
- estado com erro
- estado sem permissao ou indisponibilidade

Telas analiticas tambem devem suportar:
- sucesso parcial
- dados insuficientes
- processamento de analise

### 5.2 Login e Cadastro

- Formularios exibem feedback inline para erro e sucesso
- Rotas privadas redirecionam para login quando a sessao nao for valida
- Sessao em validacao exibe estado de carregamento

### 5.3 Noticias

- Lista paginada com 30 itens por pagina
- Navegacao com setas e paginas numeradas
- Busca e filtros sempre reiniciam a pagina para `1`
- Modal exibe resumo em 2 paragrafos

### 5.4 Carteiras

- Tela de listagem com 10 carteiras por pagina e maximo de 5 paginas
- Exclusao em lote e ativada por icone de lixeira no topo da secao
- Cada card continua com lixeira individual
- Estado vazio orienta o usuario a criar a primeira carteira

### 5.5 Carteira em Detalhe

- Tabelas por classe de ativo
- Analise geral da carteira em card dedicado
- Botao de estrela por ativo para analise individual
- Fontes agrupadas por origem tanto na analise por ativo quanto na analise geral
- Quando um bloco falhar, a tela deve manter os demais blocos disponiveis

### 5.6 Dashboard

- Deve destacar a carteira em foco
- Deve mostrar composicao, resumo e proximos passos
- Deve reaproveitar noticias relacionadas e opiniao geral
- Deve suportar estado vazio sem quebrar a navegacao

### 5.7 Chatbot

- Deve usar linguagem simples
- Deve sugerir perguntas rapidas
- Deve mostrar contexto da carteira ativa quando houver
- Nao deve soar como recomendacao de compra ou venda

### 5.8 Regras da IA

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
  - match direto por ticker ou alias
  - compatibilidade por setor e pais
  - recencia
  - impacto e relevancia
  - peso da fonte
  - peso de contexto macro

---

## 7. Regras de Seguranca e Sessao

- Senhas nunca devem ser persistidas em texto puro
- Tokens e chaves nao devem ficar expostos no frontend
- Usuario so pode acessar suas proprias carteiras, preferencias e analises
- Token invalido deve bloquear o acesso e forcar novo login
- Logout deve invalidar a sessao local mesmo que a chamada remota falhe
- A sessao atual nao expira automaticamente por tempo nesta fase; acesso e bloqueado por token invalido ou logout
- Com `SUPABASE_DB_URL` configurada, usuarios, hashes de senha, sessoes e preferencias sao persistidos no Supabase Postgres
- `app_users`, `auth_sessions`, `user_preferences`, `portfolios` e `portfolio_positions` devem manter RLS ativo e sem policies publicas enquanto a auth propria estiver no backend

---

## 8. Criterios de Aceite

- `POST /auth/register` cria conta com email unico
- `POST /auth/register` cria linha em `app_users` e sessao em `auth_sessions` quando Postgres esta habilitado
- `POST /auth/login` retorna token e usuario quando as credenciais sao validas
- `POST /auth/logout` remove a sessao persistida em `auth_sessions`
- `PUT /auth/password` exige senha atual valida
- `GET /auth/preferences` retorna preferencias do usuario autenticado ou fallback padrao
- `PUT /auth/preferences` persiste temas e preferencia de interface
- `GET /news` retorna `page_size=30` e `total_pages`
- `POST /news/backfill` aceita `source_id` opcional
- `GET /models/opinion/{portfolio_id}/positions/{ticker}` retorna `historical_window`, `source_groups` e `used_news_count`
- Noticias oficiais e editoriais coexistem no acervo sem quebrar resumo, scoring ou clustering
- A analise do ativo usa noticias do periodo quando o historico de preco for insuficiente
- A UI de fontes agrupadas funciona tanto na analise do ativo quanto na analise da carteira
- A listagem de carteiras respeita o limite de 50 no backend e 10 por pagina no frontend
- O chatbot responde perguntas educativas sem emitir recomendacao transacional

---

## 9. Observacoes Operacionais

### Base de conhecimento e conversas persistentes

- `knowledge_documents` armazena metadados, resposta editorial, fontes, versão e revisão das FAQs.
- `knowledge_chunks` armazena conteúdo pesquisável e embedding E5 de 384 dimensões com HNSW.
- `chat_conversations` e `chat_messages` persistem histórico isolado por `owner_id`.
- RLS permanece ativa e sem policies públicas; somente o backend acessa as tabelas.
- `GET/POST /chat/conversations` lista e cria conversas.
- `PATCH/DELETE /chat/conversations/{id}` renomeia e exclui uma conversa.
- `GET/POST /chat/conversations/{id}/messages` recupera o histórico e envia mensagens.
- `POST /chat` permanece como contrato stateless de compatibilidade.
- Correspondência editorial direta evita chamada ao LLM; sínteses usam até 4 FAQs, 3 notícias e 8 mensagens.
- O fallback usa o conteúdo editorial recuperado e não retorna respostas genéricas de uma frase.
- Correspondência editorial direta exige igualdade normalizada com título ou alias; similaridade semântica isolada não aciona resposta direta.
- Trechos semânticos abaixo de `KNOWLEDGE_MIN_SIMILARITY` são descartados e resultados lexicais exigem termos discriminativos.
- Resultados sem apoio lexical precisam atingir `KNOWLEDGE_STRONG_SEMANTIC_SIMILARITY=0.86` para entrar no contexto.
- Perguntas financeiras sem FAQ relevante podem usar o Qwen para conhecimento geral estável; dados atuais continuam dependentes do contexto recuperado.
- O Qwen retorna JSON estrito com o campo `answer`, cujo Markdown tem estrutura adaptativa e não contém rótulos editoriais obrigatórios.
- Pedidos educacionais sobre segurança usam resposta editorial imediata com exemplos de baixo risco relativo, sem aguardar o LLM nem prescrever investimento.
- O frontend não renderiza fontes do chat, mas `sources` e `retrieval` permanecem na API e no histórico para auditoria.

- Backend roda na porta `8001`
- O startup faz ingestao e aquecimento em background para nao bloquear a inicializacao
- O BCB permanece no catalogo, mas hoje pode retornar pouco ou nada por limitacao tecnica do portal publico
- Falhas de fonte externa devem degradar apenas o bloco afetado sempre que possivel
