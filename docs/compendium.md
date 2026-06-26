# Compendium - Operum

> Base de conhecimento consolidada do projeto.
> Ultima atualizacao: 26/06/2026

---

## 1. Visao Geral

O Operum e uma aplicacao full-stack para:

- acompanhar carteiras de investimento
- consumir noticias de mercado
- gerar analises financeiras e textuais com IA interna

O produto hoje combina calculo financeiro classico, ingestao local de noticias e geracao deterministica de analise sem dependencia de LLM externa.

---

## 2. Stack Tecnologica

| Camada | Tecnologia |
|--------|-----------|
| Frontend | React 18 + TypeScript + Vite |
| UI | Tailwind CSS |
| Graficos | Recharts |
| Roteamento | React Router DOM |
| Backend | Python 3.11+ + FastAPI |
| Persistencia | JSON + Parquet via `LocalStorageService` |
| Precos | brapi primaria + Yahoo Finance fallback |
| Noticias | RSS + listagens oficiais/editoriais abertas |
| ML | scikit-learn, XGBoost, LightGBM |
| Testes | pytest |

---

## 3. Arquitetura

```text
Frontend -> API FastAPI -> Services -> LocalStorageService -> data/
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

---

## 4. Modulo de Noticias

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

## 5. Analise por IA

### Filosofia atual

A camada de IA atual e interna e deterministica:

- nao usa LLM externa
- usa scores, classificacoes e templates
- privilegia transparencia de fontes

### Analise por ativo

Cada linha da carteira em detalhe possui um botao de estrela que abre uma analise individual.

Essa analise:
- recalcula no clique
- usa snapshot atual do ativo
- combina noticias do ativo, do setor e do contexto macro
- usa historico de noticias do periodo quando o historico de preco e fraco
- agrupa fontes por origem na interface

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

## 6. Modulo de Carteiras

### Estado atual

- CRUD local via API
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

## 7. Modelos de Dados Relevantes

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

## 8. Endpoints que mais mudaram

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

## 9. Observacoes Operacionais

- Startup do backend foi ajustado para nao bloquear por backfill longo.
- Backfill e aquecimento de precos rodam em background.
- O BCB foi mantido no desenho por valor institucional, mas nao deve ser tratado como fonte robusta enquanto a extracao publica continuar limitada.
- Os testes usam storage isolado para nao deixar carteiras residuais no ambiente principal.

---

## 10. Estado de Validacao

Ultimo estado conhecido apos as mudancas recentes:

- `python -m pytest -q` passou com `40 passed`
- `npm run build` passou

---

## 11. Direcao de Produto

O produto hoje segue esta hierarquia para qualidade analitica:

1. fatos oficiais
2. contexto editorial
3. contexto macro e setorial

Isso permite que a analise fique mais util sem abrir mao de rastreabilidade e sem depender de geracao livre por LLM externa.
