---
name: skillsBack
description: Guia de execução para IA contribuir no backend do OPERUM com Python, FastAPI, persistência local e motores de IA financeira.
> Atualizado em: 23/05/2026
---

# Skills Back — OPERUM

> Propósito: definir regras práticas para qualquer IA atuar no backend do OPERUM com consistência técnica, arquitetural e de produto.

## 1. Stack Real do Backend

- **Runtime:** Python 3.11+
- **Framework:** FastAPI
- **Schemas:** Pydantic v2
- **Persistência:** Arquivos locais (JSON + Parquet)
- **Preços:** yfinance (gratuito)
- **Notícias:** RSS feeds + yfinance news
- **ML:** scikit-learn, XGBoost, LightGBM
- **Agendamento:** schedule library
- **Testes:** pytest
- **Dados tabulares:** pandas, numpy, pyarrow

Regra crítica:
- Não adicionar banco de dados relacional sem pedido explícito.
- Não adicionar dependências pesadas sem motivo real.

## 2. Estrutura de Pastas

```text
operum/
  app/
    api/           # Endpoints FastAPI
    core/          # Configurações
    schemas/       # Modelos Pydantic
    services/      # Lógica de negócio
  data/
    assets/        # universe.json
    news/          # raw/processed/summaries
    portfolios/    # JSON por carteira
    market/        # prices/*.parquet
    cache/         # Cache de requisições
    datasets/      # Datasets de treino
    models/        # Modelos serializados (.pkl / .json)
    logs/          # Logs de ingestão
  notebooks/       # Experimentação
  scripts/         # Utilitários
  tests/           # Testes
```

## 3. Antes de Codar

Checklist obrigatório:

1. Ler `docs/compendium.md` para visão geral do projeto.
2. Ler `docs/spec.md` para contratos de API e schemas.
3. Verificar `app/services/local_storage_service.py` antes de criar qualquer persistência.
4. Verificar `app/schemas/` antes de criar novos modelos de dados.
5. Respeitar a separação entre camadas: `api/` → `services/` → `schemas/`.

## 4. Arquitetura de Camadas

### 4.1 Camada de API (`app/api/`)
- Endpoints FastAPI com routers.
- Não contém lógica de negócio.
- Recebe request, chama service, retorna response.
- Usa schemas Pydantic para validação.

### 4.2 Camada de Schemas (`app/schemas/`)
- Modelos Pydantic para request/response.
- Schemas de domínio puro (Asset, Portfolio, NewsItem).

### 4.3 Camada de Serviços (`app/services/`)
- Lógica de negócio real.
- Services podem chamar outros services.
- Services NÃO dependem de HTTP/fastapi.
- Services de persistência são injetados ou instanciados no topo.

### 4.4 Camada de Persistência (`LocalStorageService`)
- Interface única para leitura/escrita em arquivos.
- `save_json(path, data)` / `load_json(path)`
- `save_dataframe(path, df)` / `load_dataframe(path)`
- `append_event(path, event)`

## 5. Padrões de Código

### 5.1 Services

```python
class MeuService:
    def __init__(self):
        self.storage = LocalStorageService()

    def listar(self, user_id: str) -> list[MeuModel]:
        data = self.storage.load_json(f"data/meus/{user_id}.json")
        return [MeuModel(**item) for item in data]
```

### 5.2 Endpoints

```python
router = APIRouter(prefix="/meus", tags=["meus"])

@router.get("")
def listar():
    service = MeuService()
    return service.listar()
```

### 5.3 Schemas

```python
class MeuModel(BaseModel):
    id: str
    nome: str
    valor: float = 0.0
```

## 6. Persistência Local

- Toda persistência passa por `LocalStorageService`.
- JSON para entidades pequenas (portfolios, universe, settings).
- Parquet para séries temporais e datasets (prices, features, train).
- Cache em `data/cache/` com TTL simples.

```python
# Exemplo de uso
storage = LocalStorageService()

# Salvar portfolio
storage.save_json(f"data/portfolios/{portfolio_id}.json", portfolio_dict)

# Carregar portfolio
portfolio_dict = storage.load_json(f"data/portfolios/{portfolio_id}.json")

# Salvar dataframe de preços
storage.save_dataframe(f"data/market/prices/{ticker}.parquet", df_prices)

# Carregar dataframe
df = storage.load_dataframe(f"data/market/prices/{ticker}.parquet")
```

## 7. Motor Financeiro

- Funções PURAS em `financial_engine.py`.
- Recebem dados, retornam resultados.
- Nenhum efeito colateral (IO, storage, logging).
- Testáveis isoladamente.

```python
# Exemplo
def compute_volatility(returns: np.ndarray, window: int = 252) -> float:
    return float(np.std(returns) * np.sqrt(window))
```

## 8. Motores de IA

### 8.1 Separação
- **NÃO** misturar lógica financeira com ML.
- Cada motor tem seu próprio service.
- Modelos serializados em `data/models/`.

### 8.2 Treino vs Inferência
- Serviços de treino em `model_training_service.py`.
- Serviços de inferência acoplados ao service de domínio.
- Ex: `news_scoring_service.py` faz inferência; `model_training_service.py` treina.

### 8.3 Baseline Primeiro
- Implementar baseline simples (TF-IDF + Logistic Regression) antes de modelos complexos.
- Só migrar para LightGBM/XGBoost após baseline validado.

### 8.4 Serviços de IA Implementados

| Serviço | Arquivo | Técnica |
|---------|---------|---------|
| Scoring de notícias | `news_scoring_service.py` | TF-IDF + Logistic Regression / LightGBM Ranker + Sentiment keywords |
| Clusterização | `news_clustering_service.py` | K-Means sobre TF-IDF |
| Forecast de ativos | `forecast_service.py` | XGBoost Regressor (features: lags, volatilidade, médias) |
| Opinião da carteira | `portfolio_opinion_service.py` | Score composto (diversificação, correlação, notícias, macro, forecast) |
| Treino de modelos | `model_training_service.py` | Wrapper para treino de forecast em lote + histórico |

### 8.4.1 Sentiment Scoring (Keyword-based)
- Algoritmo simples em `NewsScoringService.score_sentiment()`.
- Lista de ~15 keywords positivas e ~15 negativas (português + inglês).
- Fórmula: `(pos_count - neg_count) / total` quando há match.
- Retorna `-0.1` para neutro (sem keywords encontradas).
- Acessórios expandidos incluem: "sobe", "recorde", "dividendo", "desemprego", "inflação", "juros", "tarifa".

### 8.4.2 HTML Stripping em RSS
- `NewsIngestionService._strip_html()` remove tags HTML e entidades do conteúdo RSS.
- Chamado dentro de `_clean_text()`.
- Necessário porque InfoMoney e outros feeds retornam `<p><img ...>` no summary.
- Remove: `<tags>`, `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&#\d+;`.

### 8.5 API de Modelos (`app/api/models.py`)
- `GET /models/status` — Status geral dos modelos
- `POST /models/train/forecast/{ticker}` — Treinar XGBoost para um ticker
- `GET /models/forecast/{ticker}` — Obter previsão 1d para um ticker
- `GET /models/forecast/trained` — Listar modelos treinados
- `POST /models/cluster/news` — Clusterizar notícias
- `GET /models/opinion/{portfolio_id}` — Opinião consolidada

## 9. Testes

- Usar `pytest` + `pytest-asyncio`.
- Testes unitários para `financial_engine.py` (funções puras).
- Testes de API com `httpx.AsyncClient` + `ASGITransport`.
- Configurar fixture `async_client` com `@pytest_asyncio.fixture` e `@pytest.mark.asyncio`.

```bash
pytest tests/ -v          # 30 testes (20 finance engine + 10 API)
```

## 10. Regras Importantes

### 10.1 Opinião da Carteira
- **Nunca** emitir recomendação de compra/venda.
- **Sempre** apresentar como análise descritiva.
- Cenários futuros como probabilísticos, não determinísticos.

### 10.2 Tratamento de Erros
- Endpoints devem retornar HTTP 404 para recursos não encontrados.
- Erros de serviço viram HTTP 422 ou 500 com mensagem descritiva.
- Logar erros com o módulo `logging`.

### 10.3 Performance
- Operações de IO (arquivos) podem ser lentas — usar cache onde fizer sentido.
- Modelos de ML carregados em memória apenas quando necessários.
- Preferir Parquet para dados grandes (séries temporais).

## 11. Qualidade e Validação

Toda mudança deve ser validada com:

```bash
cd operum
uvicorn app.main:app --reload
# Testar endpoints manualmente ou via pytest
```

Também vale verificar:
1. `GET /health` responde 200
2. CRUD de portfolios funciona
3. Dados persistem entre restart
4. Erros retornam HTTP status code adequado

## 12. O que Não Fazer

- Não usar banco de dados relacional sem pedido explícito.
- Não espalhar `open()` / `json.dump()` pelo código — usar `LocalStorageService`.
- Não misturar lógica financeira com ML no mesmo arquivo.
- Não adicionar dependências pesadas sem motivo.
- Não ignorar tratamento de erros em endpoints.
- Não fazer deploy de modelos não testados.

## 13. Documento Vivo

Sempre que houver mudança importante em:
- arquitetura
- novos services
- novos endpoints
- formato de dados
- dependências

a IA deve atualizar este `skillsBack.md` para refletir o estado real do projeto.
