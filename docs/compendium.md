# Compendium - Operum

> Base de conhecimento consolidada do projeto.
> Ultima atualizacao: 16/07/2026

---

## 1. Visao Geral

O Operum e uma aplicacao full-stack para:

- acompanhar carteiras de investimento
- consumir noticias de mercado
- gerar analises financeiras e textuais com IA interna

O produto hoje combina calculo financeiro classico, ingestao local de noticias e geracao deterministica de analise, com camada opcional de refino textual via Ollama local.

O projeto entrou em fase de preparacao para deploy online com frontend em Vercel e banco principal no Supabase.

---

## 2. Stack Tecnologica

| Camada | Tecnologia |
|--------|-----------|
| Frontend | React 18 + TypeScript + Vite |
| UI | Tailwind CSS |
| Graficos | Recharts |
| Roteamento | React Router DOM |
| Backend | Python 3.11+ + FastAPI |
| Persistencia | JSON + Parquet via `LocalStorageService` + Supabase Postgres para dados transacionais |
| Banco online alvo | Supabase Postgres |
| Deploy alvo | Vercel para frontend; backend Python em host separado |
| Precos | brapi primaria + Yahoo Finance fallback |
| Noticias | RSS + listagens oficiais/editoriais abertas |
| ML | scikit-learn, XGBoost, LightGBM |
| LLM local | Ollama + `qwen3:4b` |
| Testes | pytest |

---

## 3. Arquitetura

### Estado atual

```text
Frontend -> API FastAPI -> Services -> LocalStorageService -> data/
```

### Arquitetura alvo para deploy online

```text
Vercel Frontend -> API FastAPI -> Services -> Supabase Postgres
                                      -> arquivos/caches locais ou servico separado para dados pesados
```

### Camadas principais

- `api/`
  - endpoints HTTP
  - validacao de request/response
- `schemas/`
  - modelos Pydantic de dominio
- `services/`
  - regra de negocio
  - ingestao, ranking, analise e persistencia
- `data/`
  - portfolios
  - news archive/latest/meta
  - modelos
  - cache

### Estado da migracao

- Schema inicial do Supabase criado com:
  - `app_users`
  - `auth_sessions`
  - `user_preferences`
  - `portfolios`
  - `portfolio_positions`
- Variaveis de ambiente de Supabase configuradas no projeto
- Backend ja usa Supabase/Postgres para usuarios, sessoes, preferencias e carteiras quando configurado
- Autenticacao permanece propria no backend; Supabase e usado como Postgres transacional, nao como Supabase Auth
- Tabelas criticas ficam com RLS ativo e sem policies publicas enquanto o backend for a unica camada autorizada
- `LocalStorageService` permanece para noticias, caches e artefatos analiticos
- A IA local via Ollama e opcional e sempre cai para fallback deterministico em falha

---

## 4. Estrategia de Persistencia para Vercel + Supabase

### Vai para Supabase Postgres

Dados transacionais e relacionais do produto:

- usuarios da aplicacao
- sessoes autenticadas do backend atual
- preferencias do usuario
- carteiras
- posicoes da carteira
- configuracoes leves da carteira
- resultados persistidos importantes de analise
  - score final
  - resumo final
  - data da ultima analise
- noticias processadas e enxutas, quando fizer sentido manter historico consultavel
  - titulo
  - fonte
  - url
  - data
  - ativos mencionados
  - sentimento
  - impacto
  - resumo curto

### Pode ir para Supabase Storage

Apenas se houver necessidade real de armazenar arquivos:

- exports
- snapshots
- relatorios gerados
- pequenos artefatos de apoio ao produto

### Nao deve ir para o Postgres do Supabase no MVP

Dados pesados, temporarios ou recalculaveis:

- modelos treinados
- artefatos de treino
- cache temporario de analise por ativo
- historico bruto completo de noticias
- texto bruto extenso de noticias
- series historicas grandes para muitos ativos
- logs detalhados de aplicacao
- pipelines de ingestao ou treino batch

### Racional da separacao

- Vercel funciona bem para frontend e APIs leves
- Supabase Postgres deve guardar dados relacionais do produto
- dados pesados pressionam limite de armazenamento e CPU do plano free
- caches e artefatos analiticos nao devem competir com dados criticos do usuario

### Diretriz pratica

Se o dado for:

- do usuario
- relacional
- importante para persistencia online
- consultado pela UI

entao ele tende a ir para Supabase Postgres.

Se o dado for:

- pesado
- bruto
- temporario
- derivado
- recalculavel

entao ele deve ficar fora do Postgres principal.

---

## 5. Modulo de Noticias

### Estado atual

O modulo de noticias deixou de depender apenas de feeds genericos. Hoje ele usa um catalogo estruturado de fontes, com metadados por origem e conectores especificos por tipo.

### Tipos de fonte

- `rss`
- `official_listing`
- `official_notice_feed`
- `editorial_listing`
- `api_proxy`

### Fontes oficiais ativas

- **CVM**
  - `cvm_decisoes`
  - `cvm_legislacao`
  - `cvm_audiencias`
  - `cvm_sancionadores`
  - `cvm_despachos`
  - `cvm_informativos`
- **B3**
  - `b3_comunicados`
- **BCB**
  - `bcb_copom`
  - `bcb_noticias`
  - observacao: cobertura parcial porque o portal publico e servido como SPA

### Fontes editoriais complementares

- `folha_mercado`
- `infomoney`
- `investing_br`

### Complemento temporario

- yfinance news

### Persistencia

- `data/news/raw/archive.json`
  - acervo principal
- `data/news/raw/latest.json`
  - janela curta para consumo rapido
- `data/news/raw/meta.json`
  - metadados de ingestao e backfill por fonte

### Resumo

O `NewsSummaryService` gera resumo local em 2 paragrafos:

1. o que aconteceu
2. porque isso importa

Tambem limpa ruido de syndication, HTML e trechos como `The post ... appeared first on ...`.

### Paginacao

- `GET /api/news`
- `page_size` padrao = `30`
- resposta com `items`, `total`, `page`, `page_size`, `total_pages`
- busca textual `q` e filtros executados no backend antes da paginacao

---

## 6. Analise por IA

### Filosofia atual

A camada de IA atual segue dois niveis:

- calculo oficial continua deterministico
- refino textual opcional pode usar `Ollama` local
- privilegia transparencia de fontes
- fallback obrigatorio preserva a resposta deterministica atual

### Analise por ativo

Cada linha da carteira em detalhe possui um botao de estrela que abre uma analise individual.

Essa analise:
- recalcula no clique
- usa snapshot atual do ativo
- combina noticias do ativo, do setor e do contexto macro
- usa historico de noticias do periodo quando o historico de preco e fraco
- agrupa fontes por origem na interface
- pode refinar apenas os textos finais com `qwen3:4b`, sem alterar numeros, series ou confianca

Campos relevantes do payload:
- `analysis_sections.current`
- `analysis_sections.recent`
- `analysis_sections.outlook`
- `historical_window`
- `used_news_count`
- `source_groups`
- `recomputed_at`

### Analise geral da carteira

`PortfolioOpinionService` deixou de responder apenas com um texto curto. Hoje ele retorna uma sintese estruturada com:

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

Os campos textuais dessa opiniao tambem podem passar por refino local de LLM, preservando `score`, `components`, `benchmark`, pesos e fontes.

### Chatbot educativo

O chatbot agora responde pelo backend.

- usa contexto da carteira ativa ou do consolidado quando informado
- pode usar Ollama local para respostas mais coesas
- mantem fallback simples se a IA local falhar ou estiver desligada
- continua sem recomendacao de compra ou venda

Configuracao padrao local:

- `AI_PROVIDER=ollama`
- `AI_BASE_URL=http://localhost:11434/v1`
- `AI_API_KEY=ollama`
- `AI_MODEL=qwen3:4b`
- `AI_ENABLED=true`

### Ranking de noticias para analise

O `AssetAnalysisService` hoje considera:

- match direto por ticker/alias
- match por setor
- match por pais
- recencia
- impacto
- relevancia
- peso de confianca por tipo de fonte
- peso de contexto macro

Papéis de contexto:
- `asset`
- `sector`
- `macro`

Pesos relativos de fonte:
- oficiais: mais altos
- editoriais: intermediarios
- yfinance: menor

### Temas dominantes

O sistema hoje identifica melhor temas como:

- juros
- inflacao
- cambio
- commodities
- fiscal/politica
- geopolitica
- dividendos
- resultados

---

## 7. Modulo de Carteiras

### Estado atual

- CRUD via API do backend, persistindo no Supabase quando `SUPABASE_DB_URL` esta configurada
- fallback local permanece apenas para desenvolvimento sem banco configurado
- maximo de 50 carteiras
- 10 carteiras por pagina
- ate 5 paginas na UI
- exclusao individual por card
- exclusao em lote por modo de selecao ativado por lixeira no topo

### Tela de detalhe

- tabelas separadas por classe
- precos atuais e pesos por posicao
- analise geral da carteira
- analise individual por ativo
- fontes agrupadas por origem nas analises

---

## 8. Modelos de Dados Relevantes

### `NewsItem`

Campos novos importantes:

- `source_id`
- `source_type`
- `is_official`
- `source_category`

Esses metadados permitem:
- peso por fonte
- filtragem futura por origem
- transparencia maior na analise

---

## 9. Endpoints que mais mudaram

- `GET /api/news`
  - agora pagina no backend
  - `page_size=30`
  - `q` server-side
- `POST /api/news/backfill`
  - aceita `source_id` opcional
- `GET /api/portfolios/{id}/news`
  - reaproveita a base estruturada
- `GET /api/models/opinion/{portfolio_id}`
  - resposta enriquecida
- `GET /api/models/opinion/{portfolio_id}/positions/{ticker}`
  - analise individual por ativo
- `POST /api/portfolios/bulk-delete`
  - exclusao em lote

---

## 10. Observacoes Operacionais

- Startup do backend foi ajustado para nao bloquear por backfill longo.
- Backfill e aquecimento de precos rodam em background.
- O BCB foi mantido no desenho por valor institucional, mas nao deve ser tratado como fonte robusta enquanto a extracao publica continuar limitada.
- Os testes usam storage isolado para nao deixar carteiras residuais no ambiente principal.
- O deploy alvo usa Vercel para a camada web, entao jobs pesados e persistencia critica devem evitar dependencia de filesystem efemero.

---

## 11. Estado de Validacao

Ultimo estado conhecido apos as mudancas recentes:

- `python -m pytest -q` passou com `50 passed`
- `npm run build` passou
- schema inicial do Supabase foi aplicado com sucesso no projeto configurado
- `python scripts/verify_supabase_auth.py` validou cadastro, login, `/auth/me`, logout, limpeza do usuario temporario e RLS no Supabase

---

## 12. Direcao de Produto

O produto hoje segue esta hierarquia para qualidade analitica:

1. fatos oficiais
2. contexto editorial
3. contexto macro e setorial

Isso permite que a analise fique mais util sem abrir mao de rastreabilidade e sem depender de geracao livre por LLM externa.
