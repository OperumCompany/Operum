---
name: skillsFront
description: Guia de execução para IA contribuir no frontend do OPERUM com React, TypeScript, Vite, Tailwind e gráficos, preservando a experiência simples para leigos e a leitura técnica para usuários avançados.
> Atualizado em: 24/05/2026
---

# Skills Front - OPERUM

> Propósito: definir regras práticas para qualquer IA atuar no frontend do OPERUM com consistência técnica, visual e de produto, sem descaracterizar a experiência da aplicação.

## 1. Escopo e Stack Real do Projeto

Antes de propor qualquer solução, assuma o stack real:

- Frontend: `React 18` + `TypeScript`
- Build/tooling: `Vite`
- Estilo: `Tailwind CSS` + `src/styles.css`
- Roteamento: `react-router-dom`
- Gráficos: `recharts`
- Ícones: `lucide-react`
- Persistência (fallback): `localStorage`
- **Backend:** Python FastAPI (proxy Vite `/api` → `localhost:8001`)
- **API Client:** `fetch()` via `src/utils/api.ts`
- **Build:** `npm run build` (frontend estático para deploy separado)

Regra crítica:

- Não trocar a stack atual.
- Toda comunicação com dados deve passar pela API (`src/utils/api.ts`), exceto auth/session que ainda usa `localStorage`.
- Não fazer fetch direto para o backend sem passar pelos utilitários de API.

## 2. Antes de Codar

Checklist obrigatório:

1. Ler `README.md`, `package.json`, `src/App.tsx` e `src/main.tsx`.
2. Verificar `src/layout/AppShell.tsx` para entender navegação e header.
3. Verificar `src/context/PortfoliosContext.tsx` antes de alterar qualquer fluxo relacionado a carteiras.
4. Verificar `src/data/mocks.ts` e `src/utils/storage.ts` antes de mexer em dados.
5. **Verificar `src/utils/api.ts` antes de fazer qualquer chamada ao backend.**
6. **Verificar `docs/spec.md` para contratos de API antes de criar novos endpoints.**
7. Respeitar a arquitetura existente e fazer a menor mudança necessária.

## 3. Princípios do Produto

O OPERUM tem duas camadas de leitura:

- `Visão geral`: simples, guiada, menos técnica.
- `Painel técnico`: mais analítico, com gráficos e comparativos.

Toda mudança deve respeitar isso.

Regras:

- Não deixar a visão geral com cara de terminal técnico.
- Não empobrecer o painel técnico a ponto de ele perder valor analítico.
- Quando houver dúvida, a visão geral deve priorizar clareza e a técnica deve priorizar densidade útil.

## 4. Arquitetura Atual

Estrutura relevante:

```text
src/
  components/
  context/
  data/
  layout/
  pages/
  types/
  utils/
```

Responsabilidades:

- `components/`: base compartilhada de UI e proteção de rota
- `context/`: estado global de autenticação e carteiras
- `data/`: mocks e séries para simulação
- `layout/`: sidebar, header e shell principal
- `pages/`: páginas e fluxos do produto
- `utils/`: helpers de storage e carteira

## 5. Regra Mais Importante: Carteira Ativa

O estado de seleção global de carteira é central.

Hoje a aplicação suporta:

- uma carteira específica
- `Todas as carteiras`

Esse estado afeta:

- dashboard simples
- painel técnico
- chat
- resumo no módulo de carteiras

Regras:

- Não criar seleção paralela de carteira em páginas isoladas.
- Toda nova feature que analisa dados de carteira deve consumir `PortfoliosContext`.
- Se a tela depende de carteira, precisa lidar com os dois modos: individual e consolidado.

## 6. Persistência e Dados

### 6.1 Dados do Backend (via API)
Dados de negócio (ativos, carteiras, notícias, análises) devem ser obtidos via API.

Usar `src/utils/api.ts` para todas as chamadas:

```typescript
import api from '../utils/api';

// GET
const portfolios = await api.get('/portfolios');

// POST
const novo = await api.post('/portfolios', { name: 'Minha Carteira' });

// PUT
const atualizado = await api.put(`/portfolios/${id}`, { name: 'Novo Nome' });

// DELETE
await api.del(`/portfolios/${id}`);
```

### 6.2 Dados Locais (legado)
`localStorage` ainda é usado para:
- sessão do usuário (auth)
- preferências
- chat (pode migrar para API depois)

As chaves continuam centralizadas em `src/utils/storage.ts`.

Regras:

- Dados de negócio SEMPRE via API, nunca via localStorage.
- Auth/session ainda pode usar localStorage.
- Não espalhar `localStorage` direto por páginas — usar context ou api.ts.
- Se o estado é transversal, preferir `context`.
- Se for preciso criar nova chave de storage, centralizar em `storageKeys`.

## 7. Padrões React + TypeScript

### 7.1 Componentes

- Componentes devem ter responsabilidade clara.
- Evitar lógica de negócio duplicada entre páginas.
- Extrair utilitários quando a mesma regra aparecer em mais de uma tela.

### 7.2 Estado

- Estado global: usar `context` quando realmente transversal.
- Estado local: `useState`.
- Estado derivado: calcular direto ou usar `useMemo` quando fizer sentido.
- Não usar `useEffect` para computação que cabe no render.

### 7.3 Tipagem

- Manter `strict`.
- Evitar `any`.
- Tipar contratos de contexto explicitamente.
- Quando o estado aceitar um modo especial, como `Todas as carteiras`, modelar isso de forma explícita.

## 8. UI e Identidade Visual

O frontend deve manter a paleta atual do projeto:

- Fundo principal: `#F2F2F2`
- Texto principal: `#252525`
- Cinza escuro: `#3E3E3E`
- Cinza médio escuro: `#717171`
- Cinza médio claro: `#A5A5A5`
- Azul principal: `#3D4D9C`
- Rosa secundário: `#C7559B`
- Roxo complementar: `#E15EF2`

Regras:

- Não introduzir paletas paralelas sem pedido explícito.
- Não usar verde, bege ou cores fora da identidade como base do layout.
- Manter a experiência limpa, legível e com bom contraste.

## 9. Linguagem e Microcopy

O texto do produto precisa ser claro.

Regras:

- Evitar jargão desnecessário na visão geral.
- Preferir frases diretas.
- Em dashboard simples, explicar antes de impressionar.
- Em painel técnico, manter precisão sem excesso de floreio.

Se alterar textos:

- revisar acentuação
- evitar encoding quebrado
- manter consistência entre telas

## 10. Gráficos e Análises

Gráficos usam `recharts`.

Regras:

- A visão geral não deve depender de muitos gráficos ao mesmo tempo.
- O painel técnico pode ter mais densidade visual.
- Se o dado muda com a carteira ativa, o gráfico também deve mudar.
- Se estiver em `Todas as carteiras`, o comportamento deve ser consolidado e explícito no texto da tela.

## 11. Módulo de Carteiras

Esse módulo hoje suporta:

- criar carteira (via API)
- importar carteira (via universo de ativos real)
- editar carteira (nome + configurações)
- remover carteira com confirmação
- adicionar/remover posições (ticker, quantidade, preço médio)
- definir carteira para análise global

Regras:

- Qualquer operação de CRUD deve passar por `PortfoliosContext` e consumir a API.
- Exclusão deve sempre pedir confirmação.
- Se a carteira removida for a ativa, o contexto deve decidir o fallback.
- Posições agora têm `quantity` (float) e `avg_price` (float opcional), não mais `allocation` percentual.
- O universo de ativos vem da API (`GET /assets/universe` ou `GET /assets/search?q=`).

## 12. Novos Componentes

### 12.1 NewsCard
- Card compacto com: título, fonte, data, badges de ativos mencionados, score de impacto
- `onClick` → abre `NewsModal`

### 12.2 NewsModal
- Modal exibindo: título, fonte, data/hora, resumo, ativos impactados, score de impacto, link original
- Botão "Abrir original" → `source_url` em nova aba

### 12.3 PortfolioMetrics
- Cards de métricas financeiras: pesos por classe/setor/moeda, correlação, VaR, volatilidade, concentração
- Dados vindos de `GET /portfolios/{id}/analysis`

### 12.4 CompositionCharts
- Gráficos de composição: pizza (classes), barras (setores), rosca (moedas)
- Usa Recharts
- Dados vindos de `GET /portfolios/{id}/analysis`

### 12.5 ScenarioView
- Exibição de cenários futuros (conservador, moderado, agressivo, inflação alta, juros em queda) com indicador de probabilidade
- Cenários ilustrativos baseados em condições macroeconômicas hipotéticas
- Dados mockados no componente (sem endpoint específico)

### 12.6 PortfolioOpinion
- Card com score consolidado (0-100%) + rótulo (Saudável / Atenção / Crítico)
- Texto analítico explicando a carteira
- Barras de componentes: diversificação, risco correlação, impacto notícias, sensibilidade macro, risco forecast
- Dados vindos de `GET /models/opinion/{portfolio_id}`

### 12.7 PortfolioAnalysisAI
- Componente na página de detalhes da carteira.
- Botão "Gerar análise por IA" → chama `GET /api/models/opinion/{portfolio_id}`.
- Exibe: score circular (0-100%) com cor (verde/amarelo/vermelho), label (Saudável/Atenção/Crítico), texto analítico, barras dos 5 componentes (diversificação, risco correlação, impacto notícias, sensibilidade macro, risco forecast).
- Estados: `initial` (CTA de gerar), `loading` (spinner), `error` (mensagem + retry), `data` (score + texto + barras + regenerar).

### 12.8 Carteira de Exemplo
- O sistema inclui uma "Carteira Exemplo" com 8 ativos (PETR4, VALE3, ITUB4, WEGE3, BBAS3, HGLG11, KNRI11, AAPL34).
- Criada automaticamente via API, serve como onboarding visual.
- Pode ser excluída via UI se desejado.

## 13. Layout da PortfolioDetailsPage (v2)

A página de detalhe da carteira agora segue esta ordem:

1. **Header** — nome editável, botões (Editar nome, Definir como ativa, Voltar)
2. **Análise por IA** — componente PortfolioAnalysisAI (botão "Gerar" → score + texto)
3. **Tabelas por classe** — um card por classe de ativo (BR_STOCK, FII, BDR, CRYPTO) com colunas: Ticker, Quantidade, Preço médio, Preço atual, Valor total, % Carteira, Remover
4. **Adicionar ativos** — formulário com: select de classe → select de ativo filtrado → quantidade → preço médio
5. **Composição** — CompositionCharts (gráficos de pizza) no final da página

### 13.1 Filtro por Tipo de Ativo
- Primeiro select: classe do ativo (BR_STOCK, FII, BDR, CRYPTO, US_STOCK, FIXED_INCOME)
- Segundo select: lista filtrada de ativos da classe escolhida
- Desabilitado até selecionar uma classe

### 13.2 Preços Reais
- `GET /api/portfolios/{id}/prices` carregado na montagem.
- Colunas: Preço atual (R$), Valor total (R$), % Carteira.
- Dados vêm do YFinance com cache de 1h.

## 14. Integração com API

### 14.1 Padrão de Chamada
Toda página que consome dados do backend deve usar o padrão:

```typescript
const [data, setData] = useState<T | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

useEffect(() => {
  api.get('/caminho')
    .then(setData)
    .catch(e => setError(e.message))
    .finally(() => setLoading(false));
}, []);
```

### 14.2 Tratamento de Estados
Toda tela que chama API deve cobrir:
- `loading` → spinner/skeleton
- `error` → mensagem amigável + opção de retry
- `data` vazio → empty state com call to action
- `data` preenchido → render normal

## 15. Chat

O chat é explicativo e orientado a linguagem simples.

Regras:

- O texto do chat deve respeitar a carteira ou seleção ativa.
- Se estiver em `Todas as carteiras`, as respostas devem deixar isso claro.
- Não transformar o chat em motor de regras complexo sem necessidade.

## 16. Qualidade e Validação

Toda mudança relevante deve ser validada com:

```bash
npm run build
```

Para mudanças que envolvem backend + frontend:

```bash
# Terminal 1: backend (porta 8001)
uvicorn app.main:app --reload --port 8001

# Terminal 2: frontend (proxy /api → localhost:8001)
npm run dev
```

Testar manualmente:
1. troca de carteira ativa
2. modo `Todas as carteiras`
3. dashboard simples
4. painel técnico
5. chat
6. módulo de carteiras
7. notícias com filtros
8. modal de notícia
9. análise de carteira (correlação, VaR, pesos)

## 17. O que Não Fazer

- Não quebrar a lógica global de carteira ativa.
- Não introduzir seleção local de carteira em cada página.
- Não espalhar leitura/escrita de storage sem necessidade.
- Não trocar a paleta atual.
- Não adicionar dependências pesadas sem motivo real.
- Não fazer refatoração estrutural grande junto com mudança pequena de interface.
- **Não ignorar os estados de loading, erro e empty nas telas que consomem API.**
- **Não fazer fetch direto sem usar `src/utils/api.ts`.**

## 18. Checklist Final

1. A mudança respeita a stack atual?
2. A seleção global de carteira continua funcionando?
3. O modo `Todas as carteiras` está coberto?
4. A UI continua coerente com a identidade do OPERUM?
5. Os textos continuam claros e sem encoding quebrado?
6. As chamadas de API usam `src/utils/api.ts`?
7. Os estados de loading/erro/empty estão cobertos?
8. `npm run build` passou?

## 19. Documento Vivo

Sempre que houver mudança importante em:

- arquitetura
- contexto global
- persistência
- identidade visual
- navegação
- regras de análise por carteira
- integração com backend

a IA deve atualizar este `skillsFront.md` para refletir o estado real do projeto.
