---
name: skillsFront
description: Guia de execucao para IA contribuir no frontend do Operum com React, TypeScript, Vite e Tailwind, preservando a experiencia de produto e os contratos atuais da API.
updated_at: 2026-06-01
---

# Skills Front - Operum

## 1. Stack e regras base

- React 18 + TypeScript
- Vite
- Tailwind CSS
- React Router DOM
- Recharts
- Lucide React
- API via `src/utils/api.ts`
- Backend em `localhost:8001`

Regras:
- nao fazer fetch direto fora de `api.ts`
- nao trocar a stack
- nao empurrar logica de negocio complexa para componentes

## 2. Checklist antes de mexer

1. Ler `README.md`
2. Ler `docs/spec.md`
3. Conferir `src/types/index.ts`
4. Conferir `src/utils/api.ts`
5. Conferir `src/context/PortfoliosContext.tsx` se a mudanca tocar carteiras

## 3. Principios do produto

- clareza para usuario leigo
- densidade util na camada tecnica
- estados de loading, erro e vazio sempre cobertos
- texto sempre em portugues claro

## 4. Noticias: estado atual da UI

### Tela de noticias

- paginacao de 30 itens por pagina
- navegacao com setas e paginas numeradas
- filtros e busca sao server-side
- alterar busca/filtro reseta para pagina `1`
- modal da noticia mostra resumo em 2 paragrafos

### Contrato esperado

`GET /api/news` retorna:
- `items`
- `total`
- `page`
- `page_size`
- `total_pages`

`NewsItem` no frontend hoje pode conter:
- `source_id`
- `source_type`
- `is_official`
- `source_category`

Nao assumir que toda noticia tera todos os campos preenchidos; manter tolerancia em render.

## 5. Carteiras: estado atual da UI

### Lista de carteiras

- maximo de 50 carteiras
- 10 por pagina
- ate 5 paginas
- lixeira individual em cada card
- lixeira no topo para entrar em modo de selecao em lote
- no modo de selecao, o clique no bloco seleciona/desseleciona a carteira

### Cuidados

- nao reintroduzir selecao de pagina inteira para exclusao
- manter feedback visual claro entre modo normal e modo selecao
- se o backend bloquear acima de 50 carteiras, refletir a mensagem de forma amigavel

## 6. Carteira em detalhe

### Estrutura atual

- header
- analise geral da carteira
- tabelas por classe de ativo
- formulario de adicao
- composicao/graficos

### Analise por ativo

Cada ativo tem botao de estrela.

Comportamento esperado:
- clicar com card fechado -> buscar analise fresca
- clicar com card aberto -> fechar
- fonte nao deve parecer reaproveitamento de resposta antiga

Render atual relevante:
- `analysis_sections.current`
- `analysis_sections.recent`
- `analysis_sections.outlook`
- `historical_window`
- `used_news_count`
- `source_groups`

### Fontes agrupadas

Tanto na analise por ativo quanto na analise geral:
- mostrar chips por origem
- cada chip exibe nome da fonte e contador
- clique expande noticias daquela origem

Nao voltar para grade de links soltos como UI principal.

## 7. Tipos importantes

Atualizar `src/types/index.ts` sempre que o backend mudar:

- `NewsItem`
- `PortfolioOpinion`
- `AssetOpinion` ou tipo equivalente da analise por ativo
- grupos de fonte (`source_groups`)

Se o backend adicionar campo opcional, refletir como opcional no frontend quando isso melhorar compatibilidade.

## 8. Padrões React

- estado local com `useState`
- contexto apenas quando transversal
- evitar `useEffect` desnecessario
- nao usar `any`
- preferir componentes pequenos e claros

## 9. Integracao com API

Padrão:

```typescript
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

useEffect(() => {
  api.get('/rota')
    .then(...)
    .catch((e) => setError(e.message))
    .finally(() => setLoading(false));
}, []);
```

Para a analise por ativo, lembrar:
- o clique deve disparar nova chamada
- nao confiar apenas em cache de componente se a regra de produto exigir recomputacao

## 10. Validacao

Minimo antes de fechar:

```bash
npm run build
```

Quando tocar contrato com backend:

```bash
uvicorn app.main:app --reload --port 8001
npm run dev
```

Checar manualmente:
- noticias paginadas
- filtros com reset de pagina
- analise por ativo
- fontes agrupadas
- analise geral da carteira
- exclusao em lote de carteiras

## 11. O que nao fazer

- nao quebrar `PortfoliosContext`
- nao fazer fetch fora de `api.ts`
- nao esconder erro de contrato de API sem tratamento
- nao reintroduzir mocks em fluxo principal quando o endpoint existe
- nao simplificar a analise visual de fontes para algo menos transparente

## 12. Documento vivo

Atualizar este arquivo quando mudarem:
- rotas de frontend
- contrato de noticias
- contrato de analise por ativo
- contrato de analise da carteira
- UX de paginacao ou de gestao de carteiras
