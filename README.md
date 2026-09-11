# Operum

Plataforma full-stack para acompanhamento de carteiras de investimento, leitura de noticias de mercado e analise financeira com IA interna.

## Stack

**Frontend**
- React 18 + TypeScript
- Vite
- React Router DOM 7
- Tailwind CSS
- Recharts
- Lucide React

**Backend**
- Python 3.11+
- FastAPI
- Pydantic v2
- Supabase Postgres para persistencia transacional online
- Redis/Upstash para rate limit em producao
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

O backend agora opera em modo dual e com hardening de producao:

- `Supabase Postgres` para usuarios, sessoes, preferencias, carteiras e posicoes quando `SUPABASE_DB_URL` estiver configurada
- `LocalStorageService` para noticias, caches, modelos e fallback local
- sessao web em cookie `operum_session` `HttpOnly`, `SameSite=Lax` e `Secure` em producao
- rate limit para login, cadastro, chat/IA e endpoints administrativos
- security headers, CORS restrito e validacao de origem em metodos mutaveis

## Setup

### Inicio rapido (Windows)

Depois de instalar as dependencias do frontend uma vez com `npm install`, execute:

```powershell
.\iniciar.ps1
```

O script usa `.venv` do projeto, recria ou repara suas dependencias Python quando necessario e inicia backend e frontend em `http://localhost:5173`.

### Backend

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Variaveis recomendadas para producao:

- `OPERUM_ENV=production`
- `SUPABASE_DB_URL`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_DB_SCHEMA`
- `CORS_ORIGINS` com os dominios reais do frontend
- `REDIS_URL` para rate limit distribuido
- `OPERUM_RATE_LIMIT_ENABLED=true`
- `OPERUM_COOKIE_SECURE=true`
- `OPERUM_REFRESH_TOKEN` para endpoints administrativos de noticias
- `BRAPI_TOKEN` para cotacoes detalhadas e historico autenticado da brapi
- `OPERUM_ENABLE_NEWS_INGEST_ON_STARTUP`
- `OPERUM_ENABLE_NEWS_BACKFILL_ON_STARTUP`
- `OPERUM_ENABLE_PRICE_WARMUP_ON_STARTUP`
- `OPERUM_SEED_DEMO_USER=false`

Observacao:

- em desenvolvimento, o backend carrega `.env` automaticamente
- sem `BRAPI_TOKEN`, cotacoes B3 usam a listagem publica da brapi e o historico publico do Yahoo como fallback
- em producao, use variaveis do provedor do backend
- em producao, `REDIS_URL` e obrigatoria quando `OPERUM_RATE_LIMIT_ENABLED=true`
- nao envie `SUPABASE_SECRET_KEY` ou `SUPABASE_DB_URL` para o Vercel se ele hospedar apenas o frontend
- o frontend deve receber apenas variaveis publicas `VITE_*`, como `VITE_API_BASE_URL`

### Frontend

```bash
npm install
npm run dev
```

Frontend em `http://localhost:5173` com proxy `/api` para `localhost:8001`.

Credenciais locais de desenvolvimento:
- `demo@operum.app`
- `Operum123`

### Deploy do frontend no Vercel

O frontend, incluindo o pitch em `/slides`, pode ser publicado no Vercel sem backend. O pitch funciona integralmente; as telas que consultam a API ficam indisponiveis ate que o backend seja publicado.

1. Envie o repositorio para o GitHub.
2. No Vercel, selecione **Add New > Project** e importe o repositorio.
3. Mantenha o preset **Vite**, o Build Command `npm run build` e o Output Directory `dist`.
4. Faça o deploy. A apresentacao fica em `https://seu-projeto.vercel.app/slides`.

O arquivo `vercel.json` ja inclui o rewrite da SPA. Assim, links diretos como `/slides`, `/app`, `/login` e `/app/carteiras` nao retornam 404.

Quando o backend HTTPS estiver publicado, crie no Vercel a variavel publica `VITE_API_BASE_URL` com a URL da API incluindo o prefixo `/api`, por exemplo `https://api.seu-dominio.com/api`. A variavel deve ser aplicada aos ambientes Production e Preview e requer novo deploy. No backend, inclua os dominios Vercel em `CORS_ORIGINS`, separados por virgula. Nunca cadastre no Vercel do frontend `SUPABASE_SECRET_KEY`, `SUPABASE_DB_URL`, tokens de mercado, `OPERUM_REFRESH_TOKEN`, `REDIS_URL` ou qualquer outro segredo do backend.

### Atualizar os videos do pitch

Com o frontend e o backend locais em execucao por `./iniciar.ps1`, gere novamente os videos demonstrativos do pitch com:

```powershell
npm run capture:pitch
```

O processo cria uma conta local temporaria, usa a Carteira Exemplo, grava os cinco fluxos em `public/presentation/demos/` e remove a conta ao finalizar. Os videos sao estaticos e podem ser publicados pelo Vercel sem expor credenciais ou depender da API durante a apresentacao.

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
- Ledger de aportes com data, preço médio ponderado e evolução histórica por carteira ou ativo
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
python -m pip_audit -r requirements.txt

# Migracao local -> Supabase
python scripts/migrate_local_to_supabase.py

# Hardening Supabase/RLS
python scripts/secure_supabase_rls.py
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
npm audit --audit-level=low
python -m pytest
python -m pip_audit -r requirements.txt
```
