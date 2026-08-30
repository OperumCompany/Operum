# Plano de implementação do Operum focado em notícias, carteiras e IA financeira

## Premissas e direção do projeto

Este plano assume exatamente o recorte que você definiu agora: **sem banco de dados nesta fase**, foco total em **módulo de notícias** e **módulo de carteiras**, com possibilidade explícita de **alterar o frontend atual conforme necessário** para acomodar melhor as novas funcionalidades. A recomendação prática é não deixar “somente em memória”, porque isso perderia portfólios, cache de notícias e artefatos de treino ao reiniciar a aplicação; o melhor caminho para esta etapa é **persistência local em arquivos da própria aplicação**, usando JSON para entidades pequenas e Parquet/CSV para séries temporais e datasets de treino.

O PDF de matemática financeira que você anexou ajuda bastante a organizar a IA do Operum como um sistema de operadores separados por blocos: **tempo e juros**, **fluxo e investimento**, **risco e retorno**, **gestão e estrutura**, **mercado e ativos** e **estatística aplicada**, além de distinguir modelos determinísticos de modelos com componente estocástica. Isso é muito útil para o desenho da aplicação, porque evita misturar “notícia”, “preço”, “risco”, “correlação” e “opinião da carteira” em uma única caixa-preta. fileciteturn1file0

A melhor leitura arquitetural para o Operum, portanto, é esta: o sistema deve ter um **motor de ingestão**, um **motor financeiro clássico**, um **motor de IA/ranking**, um **motor de carteira**, uma **API de aplicação** e um **frontend adaptado ao novo fluxo**. A forma canônica descrita no PDF — decisão como composição de operadores de tempo, fluxo e risco — combina bem com essa divisão em serviços e com a ideia de que a “opinião da carteira” deve ser construída por etapas, não por um único modelo mágico. fileciteturn1file0

## Arquitetura alvo do Operum

A arquitetura recomendada para o MVP do Operum é composta por cinco camadas.

A primeira é a **camada de coleta**, responsável por buscar preços, ativos elegíveis e notícias de fontes gratuitas ou por scraping controlado. A segunda é a **camada de persistência local**, que salva ativos, carteiras, notícias, embeddings/scores, datasets processados e modelos treinados em arquivos da própria aplicação. A terceira é a **camada de cálculo financeiro**, com funções puras para retorno, volatilidade, covariância, correlação, beta, alpha, VaR, CVaR, CAPM, CAGR e outros operadores clássicos úteis para explicar carteira e cenário. O seu PDF lista exatamente esse conjunto de métricas e operadores, incluindo retorno, volatilidade, covariância, correlação, regressão, VaR, CVaR, CAPM, WACC, valuation relativo e blocos de fluxo de caixa e crescimento. fileciteturn1file0

A quarta é a **camada de IA**, dividida em três motores independentes: um motor de organização/ranqueamento de notícias, um motor de previsão tabular para ativos e um motor de análise de composição de carteira. A quinta é a **camada de apresentação**, com duas áreas principais por enquanto: **Notícias** e **Carteiras**.

A aplicação deve nascer com esta estrutura de pastas:

```text
operum/
  app/
    api/
    core/
    services/
    schemas/
    ui/
  data/
    assets/
    news/
    portfolios/
    market/
    cache/
    datasets/
    models/
    logs/
  notebooks/
  scripts/
  tests/
```

Dentro de `data/`, salve tudo localmente. Um desenho mínimo e suficiente seria:

```text
data/assets/universe.json
data/market/prices/*.parquet
data/news/raw/*.json
data/news/processed/*.parquet
data/news/summaries/*.json
data/portfolios/*.json
data/datasets/train/*.parquet
data/models/*.pkl
data/models/*.json
data/cache/*.json
```

Esse desenho acomoda bem o seu pedido de ficar sem banco agora, mas já deixa a aplicação pronta para migrar depois para PostgreSQL ou outro storage sem reescrever a regra de negócio.

## Plano de implementação por módulo

### Módulo de notícias

O módulo de notícias deve ser implementado como um pipeline de seis estágios.

O primeiro estágio é **ingestão**. O sistema coleta notícias em intervalos programados, normaliza campos básicos e remove duplicatas aproximadas. O objeto mínimo de notícia deve conter: `id`, `title`, `subtitle`, `content_preview`, `full_text_if_available`, `source_name`, `source_url`, `published_at`, `language`, `tags`, `mentioned_assets`, `mentioned_countries`, `mentioned_sectors`, `sentiment_score`, `relevance_score`, `impact_score`, `summary`, `cluster_id`, `created_at`.

O segundo estágio é **enriquecimento**. O sistema detecta tickers e entidades, identifica se a notícia fala de empresa, setor, juros, inflação, dólar, geopolítica, cripto ou fundos imobiliários, e marca quais ativos da base podem ser impactados.

O terceiro estágio é **classificação e ranking**. A notícia não deve ser apenas “positiva” ou “negativa”; ela deve receber pelo menos três scores: **relevância geral para o mercado**, **relevância para um ativo específico** e **impacto provável**. Esse desenho dialoga bem com o framework do PDF, porque ele separa operadores estatísticos, operadores de risco e operadores de precificação/equilíbrio, o que favorece avaliação em camadas em vez de uma única saída. fileciteturn1file0

O quarto estágio é **resumo**. No MVP, o ideal é resumo extrativo ou templateado, por segurança e auditabilidade. Ao clicar em uma notícia, o modal deve exibir: título, fonte, data/hora, resumo curto, ativos impactados, score de impacto, e um botão para abrir a notícia original no site da fonte.

O quinto estágio é **filtros**. O usuário deve conseguir filtrar por:
- classe de ativo;
- ticker;
- setor;
- país/região;
- cripto;
- sentimento;
- impacto;
- intervalo de tempo;
- somente notícias da sua carteira;
- somente notícias macroeconômicas.

O sexto estágio é **integração com a carteira**. Toda notícia processada deve poder ser relacionada a uma ou mais carteiras, para alimentar a opinião consolidada do portfólio.

### Módulo de carteiras

O módulo de carteiras deve permitir que o usuário crie várias carteiras e, dentro de cada uma, adicione ativos com quantidade, preço médio opcional, categoria e observações.

O universo inicial de ativos precisa incluir exatamente as classes que você pediu: **ações da bolsa brasileira**, **fundos imobiliários**, **alguns ativos norte-americanos** e **criptomoedas**, pelo menos com **Bitcoin** e **Ethereum**. O ideal é manter um arquivo local `universe.json` com o cadastro de todos os ativos disponíveis, contendo ticker, nome, classe, país, moeda, setor, subtipo e fonte primária de preço.

Cada carteira deve armazenar:

```json
{
  "id": "uuid",
  "name": "Carteira Principal",
  "base_currency": "BRL",
  "created_at": "...",
  "updated_at": "...",
  "positions": [
    {
      "asset_id": "PETR4",
      "ticker": "PETR4",
      "asset_class": "BR_STOCK",
      "quantity": 100,
      "avg_price": 31.20,
      "currency": "BRL",
      "manual_notes": ""
    }
  ],
  "settings": {
    "risk_profile": "moderado",
    "forecast_horizon_days": 5
  }
}
```

A partir dessa estrutura, o Operum deve calcular automaticamente:
- pesos por ativo;
- pesos por classe;
- pesos por setor;
- exposição por moeda;
- correlação média da carteira;
- concentração;
- risco histórico;
- sensibilidade a temas de notícia;
- score agregado de cenário.

A “opinião da carteira” não deve sair como conselho de compra e venda. Ela deve sair como texto analítico, por exemplo: “sua carteira está concentrada em risco doméstico e sensível a juros altos”, ou “a carteira ficou mais exposta a tecnologia americana e cripto após as últimas adições”. Esse tipo de saída é coerente com o formalismo do PDF, que trata decisão como composição de operadores de risco, fluxo e tempo, e com a separação entre modelagem determinística e estocástica. fileciteturn1file0

### Motor de opinião da carteira

Esse motor deve unir três coisas:

**Composição atual da carteira**  
Peso, concentração, classes, setores, moedas, clusters e fatores de risco.

**Estado atual do mundo**  
Notícias macro, notícias específicas por ativo, temas globais, juros, inflação, geopolítica, commodities, tecnologia, cripto.

**Cenários de reação futura**  
Probabilidade qualitativa e quantitativa de reação em curto prazo, sempre como cenário probabilístico, nunca como promessa determinística.

A saída recomendada para o usuário é um objeto como este:

```json
{
  "portfolio_id": "uuid",
  "generated_at": "...",
  "headline": "Carteira com concentração moderada em risco doméstico e alto peso em renda variável.",
  "composition_summary": "...",
  "top_risks": [
    "Alta correlação entre ativos brasileiros do mesmo setor",
    "Sensibilidade a notícias de juros e atividade econômica"
  ],
  "news_summary": [
    {
      "title": "...",
      "impact_score": 0.91,
      "affected_assets": ["PETR4", "VALE3"]
    }
  ],
  "scenario_view": {
    "1d": "...",
    "5d": "...",
    "30d": "..."
  },
  "portfolio_scores": {
    "diversification": 0.63,
    "macro_sensitivity": 0.77,
    "news_risk": 0.68,
    "crypto_exposure": 0.12
  }
}
```

## Motor financeiro e modelos de IA

A parte mais importante do Operum é separar o que é **cálculo financeiro clássico** do que é **aprendizado de máquina**.

### Motor financeiro clássico

Antes de qualquer modelo de IA, implemente uma biblioteca local de operadores financeiros. O seu PDF já fornece a ontologia do que faz sentido incluir: blocos de retorno, volatilidade, covariância, correlação, regressão, VaR, CVaR, beta, alpha, CAPM, fluxo de caixa, CAGR, valuation relativo, duration, convexidade, inflação e câmbio. Mesmo que nem tudo entre no MVP visual, esses operadores devem existir como biblioteca base para o produto evoluir corretamente. fileciteturn1file0

O núcleo mínimo do MVP deve ter estas funções:

```python
compute_simple_return()
compute_log_return()
compute_cumulative_return()
compute_volatility()
compute_covariance_matrix()
compute_correlation_matrix()
compute_beta()
compute_alpha()
compute_var()
compute_cvar()
compute_drawdown()
compute_moving_average()
compute_ema()
compute_rsi()
compute_macd()
compute_portfolio_weights()
compute_portfolio_return()
compute_portfolio_volatility()
compute_portfolio_concentration()
compute_capm_expected_return()
compute_cagr()
```

### Modelo para notícias

Para o MVP, a recomendação continua sendo:

**Classificação de relevância**  
TF-IDF + Logistic Regression ou Linear SVM.

**Ranqueamento de impacto**  
LightGBMRanker ou XGBoostRegressor/Classificador convertido em score.

**Agrupamento temático**  
K-Means sobre vetores TF-IDF ou embeddings.

**Resumo**  
Extrativo/templateado.

As features de notícia devem incluir:
- texto do título;
- subtítulo;
- primeiros parágrafos;
- presença do ticker no título;
- quantidade de ativos citados;
- recência;
- tipo de fonte;
- cluster temático;
- sentimento;
- reação histórica média de preço após notícias semelhantes.

### Modelo para ativos

Para projeção do comportamento do ativo, use um modelo tabular supervisionado treinado sobre features de mercado e sinais de notícia. A escolha mais segura para o seu contexto continua sendo:

- XGBoost como caminho rápido de implementação;
- LightGBM como provável melhor benchmark;
- CatBoost como terceira via quando houver muitas categorias.

O alvo do modelo deve ser retorno futuro em janelas curtas, por exemplo `1d`, `5d` e `20d`, e não simplesmente o preço cru. O PDF valoriza exatamente os blocos de retorno, risco, correlação e regressão, o que reforça essa escolha de modelar variação e não apenas preço absoluto. fileciteturn1file0

As features mínimas devem ser:
- lags de retorno;
- volatilidade móvel;
- volume relativo;
- máximas e mínimas recentes;
- médias móveis;
- betas;
- correlação com índices de referência;
- exposição a clusters temáticos;
- score de notícia do ativo;
- contagem de notícias recentes;
- score agregado de sentimento.

### Modelo para carteira

Para a carteira, a melhor estratégia é combinar estatística robusta com aprendizado não supervisionado.

Use:
- matriz de covariância;
- matriz de correlação;
- shrinkage se necessário;
- PCA para fatores latentes;
- clustering para agrupar ativos semelhantes;
- score final de risco/notícia por peso da carteira.

Isso é diretamente suportado pelo seu PDF, que lista covariância, correlação, regressão, retorno ajustado ao risco, VaR, CVaR, CAPM e estrutura de decisão financeira como blocos centrais do sistema. fileciteturn1file0

A opinião final da carteira pode ser construída por regra + score:

```text
portfolio_opinion_score =
0.30 * diversification_score +
0.20 * correlation_risk_score +
0.20 * news_impact_score +
0.15 * macro_sensitivity_score +
0.15 * forecast_risk_score
```

Depois esse score alimenta um gerador de texto analítico.

## Contratos da aplicação e mudanças necessárias no frontend

O frontend atual **pode e deve ser alterado conforme necessário** para acomodar o novo fluxo. Isso é importante porque tentar encaixar essa nova funcionalidade em uma interface pensada para outra estrutura quase sempre piora o produto. O foco agora deve ser **funcionalidade correta**, não preservar layout antigo.

### Telas necessárias

**Tela de Notícias**  
Lista paginada ou infinita, filtros laterais/superiores, cards compactos, badges de ativo/classe, score de impacto e data. Ao clicar, abrir modal com resumo, ativos relacionados, análise curta e link para a fonte original.

**Tela de Carteiras**  
Lista de carteiras do usuário, botão “criar carteira”, edição de nome e configuração básica. Dentro da carteira, adicionar/remover ativos, visualizar tabela de posições, gráficos de composição, resumo da carteira e notícias relacionadas.

**Tela interna da Carteira**  
Essa tela deve ter pelo menos quatro blocos:
- composição atual;
- notícias mais relevantes para a carteira;
- análise de risco/correlação;
- cenários futuros.

### Endpoints recomendados

```text
GET    /health
GET    /assets/universe
GET    /assets/search?q=
GET    /market/price/{ticker}
GET    /market/history/{ticker}
GET    /news
GET    /news/{id}
POST   /news/reindex
POST   /news/summarize/{id}
GET    /portfolios
POST   /portfolios
GET    /portfolios/{id}
PUT    /portfolios/{id}
DELETE /portfolios/{id}
POST   /portfolios/{id}/positions
DELETE /portfolios/{id}/positions/{ticker}
GET    /portfolios/{id}/analysis
GET    /portfolios/{id}/news
GET    /portfolios/{id}/scenarios
POST   /models/train/news
POST   /models/train/assets
GET    /models/status
```

### Serviços internos recomendados

```text
AssetUniverseService
MarketDataIngestionService
NewsIngestionService
NewsScoringService
NewsSummaryService
PortfolioService
PortfolioAnalyticsService
ForecastService
ModelTrainingService
LocalStorageService
```

### Persistência local sem banco

Implemente um `LocalStorageService` com interface única, para que o resto da aplicação não saiba se está gravando em JSON, Parquet ou banco. Exemplo:

```python
class LocalStorageService:
    def save_json(self, path: str, data: dict) -> None: ...
    def load_json(self, path: str) -> dict: ...
    def save_dataframe(self, path: str, df) -> None: ...
    def load_dataframe(self, path: str): ...
    def append_event(self, path: str, event: dict) -> None: ...
```

Isso preserva sua decisão de ficar sem banco agora e economiza retrabalho no futuro.

## Sequência de execução recomendada

A melhor forma de construir isso sem se perder é em ondas curtas.

### Primeira onda

Implemente a base do projeto:
- FastAPI;
- persistência local;
- cadastro de universo de ativos;
- cadastro de carteiras;
- adição e remoção de posições;
- layout novo de notícias e carteiras.

Essa fase termina quando o usuário já consegue criar uma carteira e ver a composição básica.

### Segunda onda

Implemente coleta e exibição de notícias:
- ingestão programada;
- deduplicação;
- filtros;
- lista;
- modal;
- link original;
- resumo simples;
- vínculo notícia-ativo.

Essa fase termina quando o módulo de notícias funciona de ponta a ponta.

### Terceira onda

Implemente o motor financeiro:
- retornos;
- volatilidade;
- correlação;
- beta;
- VaR/CVaR;
- score de concentração;
- análise de composição.

Essa fase termina quando a carteira já consegue gerar uma visão quantitativa explicável. O PDF que você anexou dá suporte direto a esse conjunto de operadores, especialmente nos blocos de risco e retorno, estatística aplicada e mercado/ativos. fileciteturn1file0

### Quarta onda

Implemente os modelos de IA:
- classificador de relevância de notícias;
- rankeador de impacto;
- modelo tabular de previsão por ativo;
- score combinado da carteira.

Essa fase termina quando o Operum já consegue dizer quais notícias importam para a carteira e produzir cenários futuros.

### Quinta onda

Aprimore explicabilidade e UX:
- textos de opinião da carteira;
- explicação de score;
- mensagens de confiança/incerteza;
- logs de ingestão;
- retreino local;
- testes automatizados.

Essa fase termina quando o produto já pode ser usado internamente de forma consistente.

## Limitações e decisões que precisam estar explícitas

Sem banco de dados, o Operum pode funcionar muito bem no começo, mas você deve assumir desde já estas limitações: risco de perda de estado em deploy mal configurado, dificuldade para múltiplos usuários simultâneos, concorrência de escrita em arquivos e pouca escalabilidade horizontal. Por isso, a persistência local deve ser organizada desde o primeiro dia como se fosse uma mini-camada de storage, e não como gambiarras espalhadas no código.

A segunda limitação é conceitual: a saída “como a carteira irá reagir no futuro” deve ser tratada como **cenário probabilístico** e não como promessa. O próprio PDF diferencia modelos financeiros clássicos determinísticos de modelos avançados com componente estocástica, o que reforça que o Operum deve comunicar faixas, riscos e probabilidades, e não previsões absolutas. fileciteturn1file0

A terceira limitação é operacional: resumo generativo livre pode ser adicionado depois, mas o MVP deve priorizar rastreabilidade, ligação com a fonte original e justificativa quantitativa do score.

## Bloco copiável para outra IA

O texto abaixo já está formatado para você copiar e colar na outra IA que vai programar o Operum:

```text
Quero que você implemente a próxima evolução do Operum com foco apenas nas funcionalidades centrais, deixando dashboard, chat e configurações para depois.

CONTEXTO GERAL
- O projeto deve ser reorganizado para focar em dois módulos principais:
  1) módulo de notícias
  2) módulo de carteiras
- O frontend atual pode ser alterado conforme necessário para se adaptar corretamente às novas funcionalidades.
- Nesta fase, NÃO quero banco de dados relacional.
- A persistência deve ser local dentro da aplicação, usando arquivos JSON para entidades pequenas e Parquet/CSV para dados de mercado e datasets.
- A arquitetura deve ser limpa e preparada para migrar para banco de dados depois, sem acoplamento.

OBJETIVO DO MÓDULO DE NOTÍCIAS
- Criar um módulo em que cheguem todas as notícias coletadas.
- O usuário deve conseguir filtrar o que quer ler.
- As notícias devem aparecer em lista.
- Ao clicar em uma notícia, deve abrir um modal.
- No modal, deve aparecer:
  - título
  - fonte
  - data/hora
  - resumo
  - ativos impactados
  - score de impacto
  - link para a notícia original no site da fonte
- Deve ser possível filtrar por:
  - ticker
  - classe de ativo
  - setor
  - país/região
  - sentimento
  - impacto
  - intervalo de tempo
  - somente notícias relacionadas à carteira do usuário

OBJETIVO DO MÓDULO DE CARTEIRAS
- O usuário poderá criar uma carteira.
- Dentro da carteira ele poderá adicionar ativos.
- O universo inicial de ativos deve incluir:
  - ações da bolsa brasileira
  - fundos imobiliários
  - alguns ativos norte-americanos
  - criptomoedas, pelo menos Bitcoin e Ethereum
- Cada carteira deve ter:
  - nome
  - moeda base
  - lista de posições
  - quantidade
  - preço médio opcional
  - classe do ativo
  - observações opcionais
- O Operum deve entender automaticamente a composição da carteira e gerar:
  - pesos por ativo
  - pesos por classe
  - pesos por setor
  - exposição por moeda
  - concentração
  - correlação
  - risco histórico
  - sensibilidade a notícias
  - opinião consolidada da carteira

OBJETIVO DA IA
- Quero três motores separados:
  1) motor de notícias
  2) motor de previsão/forecast de ativos
  3) motor de análise da carteira
- NÃO quero um único modelo para tudo.

MODELOS A IMPLEMENTAR
- Notícias:
  - baseline com TF-IDF + Logistic Regression ou Linear SVM para relevância
  - ranking de impacto com LightGBMRanker ou XGBoost
  - clustering temático com K-Means
  - resumo inicialmente extrativo ou templateado
- Ativos:
  - modelo tabular com XGBoost como primeira implementação
  - benchmark preparado para LightGBM e CatBoost
  - alvo principal: retorno futuro (1d, 5d, 20d), não apenas preço bruto
- Carteira:
  - cálculo de covariância
  - cálculo de correlação
  - PCA para fatores latentes
  - clustering para grupos de ativos semelhantes
  - score final de opinião da carteira com base em composição, correlação, notícias e forecast

REGRAS IMPORTANTES DA OPINIÃO DA CARTEIRA
- A saída não deve ser recomendação financeira direta.
- A saída deve ser explicação analítica.
- Exemplo:
  - “carteira com concentração moderada em risco doméstico”
  - “exposição elevada a notícias de juros”
  - “cripto com alta sensibilidade ao noticiário global”
- A análise futura deve ser apresentada como cenário probabilístico, nunca como promessa determinística.

ARQUITETURA TÉCNICA
- Backend em Python com FastAPI
- Persistência local via arquivos
- Criar camada de storage abstrata para leitura/escrita
- Criar serviços separados:
  - AssetUniverseService
  - MarketDataIngestionService
  - NewsIngestionService
  - NewsScoringService
  - NewsSummaryService
  - PortfolioService
  - PortfolioAnalyticsService
  - ForecastService
  - ModelTrainingService
  - LocalStorageService

ESTRUTURA DE PASTAS
operum/
  app/
    api/
    core/
    services/
    schemas/
    ui/
  data/
    assets/
    news/
    portfolios/
    market/
    cache/
    datasets/
    models/
    logs/
  notebooks/
  scripts/
  tests/

PERSISTÊNCIA LOCAL
- Usar arquivos locais como:
  - data/assets/universe.json
  - data/market/prices/*.parquet
  - data/news/raw/*.json
  - data/news/processed/*.parquet
  - data/news/summaries/*.json
  - data/portfolios/*.json
  - data/datasets/train/*.parquet
  - data/models/*.pkl
  - data/models/*.json
  - data/cache/*.json

ENDPOINTS QUE QUERO
GET    /health
GET    /assets/universe
GET    /assets/search?q=
GET    /market/price/{ticker}
GET    /market/history/{ticker}
GET    /news
GET    /news/{id}
POST   /news/reindex
POST   /news/summarize/{id}
GET    /portfolios
POST   /portfolios
GET    /portfolios/{id}
PUT    /portfolios/{id}
DELETE /portfolios/{id}
POST   /portfolios/{id}/positions
DELETE /portfolios/{id}/positions/{ticker}
GET    /portfolios/{id}/analysis
GET    /portfolios/{id}/news
GET    /portfolios/{id}/scenarios
POST   /models/train/news
POST   /models/train/assets
GET    /models/status

ESTRUTURA DE DADOS DE NOTÍCIA
- Cada notícia deve ter:
  - id
  - title
  - subtitle
  - content_preview
  - full_text_if_available
  - source_name
  - source_url
  - published_at
  - language
  - tags
  - mentioned_assets
  - mentioned_countries
  - mentioned_sectors
  - sentiment_score
  - relevance_score
  - impact_score
  - summary
  - cluster_id
  - created_at

ESTRUTURA DE DADOS DE CARTEIRA
{
  "id": "uuid",
  "name": "Carteira Principal",
  "base_currency": "BRL",
  "created_at": "...",
  "updated_at": "...",
  "positions": [
    {
      "asset_id": "PETR4",
      "ticker": "PETR4",
      "asset_class": "BR_STOCK",
      "quantity": 100,
      "avg_price": 31.20,
      "currency": "BRL",
      "manual_notes": ""
    }
  ],
  "settings": {
    "risk_profile": "moderado",
    "forecast_horizon_days": 5
  }
}

FUNÇÕES FINANCEIRAS QUE DEVEM EXISTIR
- compute_simple_return()
- compute_log_return()
- compute_cumulative_return()
- compute_volatility()
- compute_covariance_matrix()
- compute_correlation_matrix()
- compute_beta()
- compute_alpha()
- compute_var()
- compute_cvar()
- compute_drawdown()
- compute_moving_average()
- compute_ema()
- compute_rsi()
- compute_macd()
- compute_portfolio_weights()
- compute_portfolio_return()
- compute_portfolio_volatility()
- compute_portfolio_concentration()
- compute_capm_expected_return()
- compute_cagr()

FLUXO DO MÓDULO DE NOTÍCIAS
1. coletar notícias
2. normalizar campos
3. remover duplicatas
4. detectar entidades e tickers
5. calcular sentimento, relevância e impacto
6. gerar resumo
7. salvar localmente
8. relacionar com ativos e carteiras
9. exibir no frontend com filtros e modal

FLUXO DO MÓDULO DE CARTEIRAS
1. criar carteira
2. adicionar/remover ativos
3. atualizar preços
4. recalcular pesos
5. recalcular correlação e risco
6. buscar notícias relacionadas
7. calcular score consolidado
8. gerar opinião da carteira
9. exibir composição, riscos, notícias e cenários

REGRAS DE UX
- Notícias em lista
- Clique abre modal
- Modal mostra resumo e link externo
- Carteira deve ter tela própria com:
  - composição atual
  - posições
  - notícias relevantes
  - correlação/risco
  - cenários futuros
  - opinião consolidada
- O frontend atual pode ser refatorado livremente para acomodar essas novas necessidades

ORDEM DE IMPLEMENTAÇÃO
FASE 1
- montar estrutura do projeto
- criar storage local
- cadastrar universo de ativos
- criar CRUD de carteiras
- adaptar frontend para notícias e carteiras

FASE 2
- implementar ingestão de notícias
- filtros
- lista
- modal
- link original
- resumo simples

FASE 3
- implementar motor financeiro clássico
- retorno, volatilidade, correlação, beta, VaR/CVaR, concentração

FASE 4
- implementar IA de notícias
- implementar forecast de ativos com XGBoost
- preparar benchmark para LightGBM/CatBoost
- implementar score consolidado da carteira

FASE 5
- melhorar explicabilidade
- logs
- retreino local
- testes automatizados
- mensagens de incerteza/confiança

CRITÉRIOS DE ACEITAÇÃO
- usuário consegue criar carteira e adicionar ativos
- sistema mostra preços e composição
- sistema mostra notícias filtráveis
- ao clicar na notícia abre modal com resumo e link original
- sistema relaciona notícias relevantes à carteira
- sistema calcula correlação e risco da carteira
- sistema gera opinião consolidada da carteira
- sistema gera cenários probabilísticos futuros
- tudo funcionando sem banco relacional, apenas com persistência local em arquivos

IMPORTANTE
- Priorizar funcionamento correto antes de estética.
- Priorizar arquitetura limpa.
- Manter separação total entre:
  - cálculo financeiro clássico
  - IA de notícias
  - forecast de ativos
  - análise de carteira
- Preparar o código para futura migração para banco de dados e para futura adição de dashboard/chat/configurações.
```

## Fechamento técnico

Se você quiser ser muito pragmático, a frase mais importante para a outra IA é esta: **“implemente primeiro o Operum como um sistema local com persistência em arquivos, módulo de notícias, módulo de carteiras, motor financeiro clássico e IA separada em notícias, ativos e carteira, podendo refatorar o frontend livremente para se adaptar ao fluxo correto.”**

Esse plano é o mais coerente com o que você descreveu agora e também com o framework matemático do PDF, que organiza o problema financeiro como composição de operadores de tempo, fluxo, risco, mercado e estatística, incluindo correlação, covariância, regressão, retorno ajustado ao risco, VaR, CVaR e modelos de equilíbrio/preço. fileciteturn1file0