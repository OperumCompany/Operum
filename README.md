# Operum

Plataforma full-stack para acompanhamento de carteiras de investimento, leitura de noticias de mercado e analise financeira com IA interna.

## Stack

**Frontend**
- React 18 + TypeScript
- Vite
- React Router DOM
- Tailwind CSS
- Recharts
- Lucide React

**Backend**
- Python 3.11+
- FastAPI
- Pydantic v2
- Supabase Postgres para persistencia transacional online
- yfinance para precos
- Ingestao de noticias por RSS e listagens oficiais/editoriais abertas
- scikit-learn, XGBoost, LightGBM
- Persistencia local em JSON + Parquet

## Arquitetura

```text
Frontend (React/Vite) <-> API (FastAPI) <-> Services <-> LocalStorageService
                                                      |
                                                      v
                                                JSON / Parquet
```

O projeto e um monorepo com frontend em `src/` e backend em `app/`.

O backend agora opera em modo dual:

- `Supabase Postgres` para usuarios, sessoes, preferencias, carteiras e posicoes quando `SUPABASE_DB_URL` estiver configurada
- `LocalStorageService` para noticias, caches, modelos e fallback local

## Setup

### Backend

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Variaveis recomendadas para producao:

- `SUPABASE_DB_URL`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_DB_SCHEMA`
- `OPERUM_ENABLE_NEWS_INGEST_ON_STARTUP`
- `OPERUM_ENABLE_NEWS_BACKFILL_ON_STARTUP`
- `OPERUM_ENABLE_PRICE_WARMUP_ON_STARTUP`

Observacao:

- em desenvolvimento, o backend carrega `.env` automaticamente
- em producao, use variaveis do provedor do backend
- nao envie `SUPABASE_SECRET_KEY` ou `SUPABASE_DB_URL` para o Vercel se ele hospedar apenas o frontend

### Frontend

```bash
npm install
npm run dev
```

Frontend em `http://localhost:5173` com proxy `/api` para `localhost:8001`.

Credenciais locais de desenvolvimento:
- `demo@operum.app`
- `Operum123`

## Modulos

### Noticias
- Acervo historico local com `archive.json` e `latest.json`
- Paginacao server-side de 30 noticias por pagina
- Busca textual e filtros por ticker, classe, setor, pais, sentimento, impacto e datas
- Backfill desde `2026-05-01` para fontes suportadas
- Resumo local em 2 paragrafos curtos, sem LLM externa
- Agrupamento e scoring de noticias para alimentar analise por ativo e por carteira

### Fontes de noticias atualmente integradas

**Oficiais**
- CVM: decisoes, legislacao, audiencias, sancionadores, despachos e informativos
- B3: comunicados e paginas oficiais abertas
- Tesouro Nacional / Tesouro Direto: paginas oficiais abertas
- BCB: conectores preparados, mas com cobertura parcial porque o portal publico e servido como SPA

**Editoriais complementares**
- Folha Mercado
- InfoMoney
- Investing Brasil

**Complemento temporario**
- yfinance news

### Carteiras
- CRUD de carteiras com persistencia no Supabase quando configurado
- Limite de 50 carteiras, em ate 5 paginas de 10 itens
- Exclusao individual e exclusao em lote por modo de selecao na interface
- Posicoes com quantidade e preco medio
- Tabelas por classe de ativo na tela de detalhe
- Precos reais com cache
- Analise financeira: pesos, concentracao, correlacao, VaR, CVaR, beta e volatilidade

### IA interna
- Scoring de noticias por relevancia, impacto e sentimento
- Ranking de noticias com pesos por tipo de fonte
- Analise individual por ativo com geracao deterministica por templates
- Sintese geral da carteira com foco em composicao, sobreposicao e blocos de risco
- Agrupamento de fontes por origem na UI da analise

## Analise por IA

### Analise por ativo
- Botao com icone de estrela em cada ativo na `Carteira em Detalhe`
- Recalculo no clique, sem reutilizar resposta antiga como cache ativo
- Blocos:
  - `Situacao atual`
  - `Ultimos 3 meses`
  - `Perspectivas 3 meses`
- Usa noticias do ativo, do setor e do contexto macro
- Fontes exibidas por origem, com expansao das noticias usadas

### Analise geral da carteira
- `GET /api/models/opinion/{portfolio_id}`
- Mantem `score` e `components`
- Retorna tambem:
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

## Estrutura

```text
operum/
|-- app/
|   |-- api/
|   |-- core/
|   |-- schemas/
|   `-- services/
|-- src/
|   |-- components/
|   |-- context/
|   |-- layout/
|   |-- pages/
|   |-- types/
|   `-- utils/
|-- data/
|   |-- assets/
|   |-- news/
|   |-- portfolios/
|   |-- market/
|   |-- cache/
|   |-- datasets/
|   |-- models/
|   `-- logs/
|-- docs/
|-- tests/
|-- skillsFront.md
|-- skillsBack.md
`-- requirements.txt
```

## Scripts

```bash
# Frontend
npm run dev
npm run build
npm run preview

# Backend
uvicorn app.main:app --reload --port 8001
pytest tests/ -q

# Migracao local -> Supabase
python scripts/migrate_local_to_supabase.py
```

## Documentacao

- `docs/compendium.md` - base de conhecimento consolidada
- `docs/spec.md` - especificacao funcional e contratos de API
- `docs/deployment-security.md` - regras de segredos e deploy seguro
- `skillsFront.md` - guia para alteracoes no frontend
- `skillsBack.md` - guia para alteracoes no backend

## Rotas principais

- `/` - Dashboard
- `/dashboard-tecnico` - Painel tecnico
- `/noticias` - Noticias
- `/carteiras` - Lista de carteiras
- `/carteiras/:id` - Detalhe da carteira
- `/configuracoes` - Preferencias
- `/login` e `/registro` - Autenticacao

## Validacao

```bash
npm run build
pytest tests/ -q
```
