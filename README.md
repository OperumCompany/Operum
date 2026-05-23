# Operum

Plataforma full-stack para acompanhamento de carteiras de investimento, leitura de notícias de mercado e análise financeira com IA.

## Stack

**Frontend:**
- React 18 + TypeScript
- Vite
- React Router DOM
- Recharts
- Tailwind CSS
- Lucide React

**Backend:**
- Python 3.11+
- FastAPI
- Pydantic v2
- yfinance (preços)
- RSS feeds + yfinance news (notícias)
- scikit-learn, XGBoost, LightGBM (ML)
- Persistência local em JSON + Parquet

## Arquitetura

```
Frontend (React/Vite)  ←→  API (FastAPI)  ←→  Services  ←→  LocalStorageService
                                                              ↓
                                                        Arquivos JSON/Parquet
```

O projeto é um monorepo com frontend em `src/` e backend em `app/`.

## Setup

### Backend

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
npm install
npm run dev      # Vite proxy /api → localhost:8000
```

Acessar frontend em `http://localhost:5173`.

## Módulos

### Notícias
- Coleta automática de notícias via YFinance (13 tickers) + RSS (Folha, InfoMoney, Investing.com, BBC)
- Filtros por ticker, classe, setor, país, sentimento, impacto, data
- Modal com resumo, ativos impactados e link original
- Notícias relacionadas à carteira ativa
- Clusterização temática automática (K-Means)
- Scoring: sentimento (keywords), relevância (TF-IDF + LR), impacto (composto)
- HTML stripping automático de conteúdo RSS

### Carteiras
- CRUD completo de carteiras
- Universo de ~131+ ativos (BR ações, FIIs, US stocks, crypto)
- Posições com quantidade e preço médio
- Composição por classe, setor, moeda
- Análise financeira: pesos, concentração, correlação, VaR, CVaR, beta, volatilidade

### Motor Financeiro (22 funções puras)
- Retorno simples, logarítmico, cumulativo
- Volatilidade, covariância, correlação, beta, alpha
- VaR, CVaR, drawdown
- Média móvel, EMA, RSI, MACD
- Pesos, retorno e volatilidade de carteira, concentração
- CAPM, CAGR

### IA
- Classificação e ranking de notícias (TF-IDF + Logistic Regression / LightGBM Ranker)
- Clusterização temática (K-Means sobre TF-IDF)
- Forecast de ativos (XGBoost Regressor — requer treino via API)
- Opinião consolidada da carteira (score composto + texto analítico)
- Cenários probabilísticos ilustrativos

## Estrutura

```text
operum/
├── app/                  # Backend Python/FastAPI
│   ├── api/              # Endpoints (health, assets, market, news, portfolios, models)
│   ├── core/             # Config (CORS, logging)
│   ├── schemas/          # Pydantic models (asset, news, portfolio)
│   └── services/         # Lógica de negócio (12 serviços)
├── src/                  # Frontend React
│   ├── components/       # UI components + PortfolioMetrics, CompositionCharts, ScenarioView, PortfolioOpinion
│   ├── context/          # Estado global (AuthContext, PortfoliosContext)
│   ├── pages/            # Telas
│   ├── types/            # Interfaces TS
│   └── utils/            # Helpers (api.ts, storage.ts)
├── data/                 # Persistência local
│   ├── assets/           # universe.json
│   ├── news/             # raw/processed/summaries
│   ├── portfolios/       # JSON por carteira
│   ├── market/prices/    # Cache de preços
│   ├── cache/            # Cache de requisições
│   ├── datasets/train/   # Datasets de treino
│   ├── models/           # Modelos serializados (.pkl)
│   └── logs/             # operum.log
├── docs/                 # Documentação (compendium.md, spec.md)
├── tests/                # 30 testes (20 finance engine + 10 API)
├── skillsFront.md        # Guia frontend para IA
├── skillsBack.md         # Guia backend para IA
├── plano.md              # Plano de implementação vivo
└── requirements.txt
```

## Scripts

```bash
# Frontend
npm run dev       # Desenvolvimento (porta 5173)
npm run build     # Build produção
npm run preview   # Preview build

# Backend
uvicorn app.main:app --reload    # Desenvolvimento (porta 8000)
pytest tests/ -v                 # Testes
```

## Documentação

- `docs/compendium.md` — Base de conhecimento consolidada
- `docs/spec.md` — Especificação detalhada
- `plano.md` — Plano de implementação com status

## Rotas

- `/` — Dashboard (visão geral)
- `/dashboard-tecnico` — Painel técnico
- `/noticias` — Notícias de mercado
- `/chat` — Chat explicativo
- `/carteiras` — Lista de carteiras
- `/carteiras/:id` — Detalhe da carteira
- `/configuracoes` — Preferências
- `/login` / `/registro` — Autenticação

## Conta de Exemplo

- E-mail: `camila@operum.app`
- Senha: `Operum123`

## Validação

```bash
npm run build    # Frontend
pytest tests/    # Backend
```
