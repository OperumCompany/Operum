---
name: skillsFront
description: Guia de execução para IA contribuir no frontend do OPERUM com React, TypeScript, Vite, Tailwind e gráficos, preservando a experiência simples para leigos e a leitura técnica para usuários avançados.
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
- Persistência atual: `localStorage`

Regra crítica:

- Não inventar backend ou integrações externas sem pedido explícito.
- Não trocar a stack atual.

## 2. Antes de Codar

Checklist obrigatório:

1. Ler `README.md`, `package.json`, `src/App.tsx` e `src/main.tsx`.
2. Verificar `src/layout/AppShell.tsx` para entender navegação e header.
3. Verificar `src/context/PortfoliosContext.tsx` antes de alterar qualquer fluxo relacionado a carteiras.
4. Verificar `src/data/mocks.ts` e `src/utils/storage.ts` antes de mexer em dados.
5. Respeitar a arquitetura existente e fazer a menor mudança necessária.

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

O projeto usa `localStorage`, com chaves em `src/utils/storage.ts`.

Persistências atuais:

- usuário
- sessão
- carteiras
- carteira ativa
- chat
- preferências

Regras:

- Não espalhar `localStorage` direto por páginas se já existe contexto/utilitário.
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

- criar carteira
- importar carteira mockada
- editar carteira
- remover carteira com confirmação
- definir carteira para análise global

Regras:

- Qualquer operação de CRUD deve passar por `PortfoliosContext`.
- Exclusão deve sempre pedir confirmação.
- Se a carteira removida for a ativa, o contexto deve decidir o fallback.

## 12. Chat

O chat é explicativo e orientado a linguagem simples.

Regras:

- O texto do chat deve respeitar a carteira ou seleção ativa.
- Se estiver em `Todas as carteiras`, as respostas devem deixar isso claro.
- Não transformar o chat em motor de regras complexo sem necessidade.

## 13. Qualidade e Validação

Toda mudança relevante deve ser validada com:

```bash
npm run build
```

Também vale testar manualmente:

1. troca de carteira ativa
2. modo `Todas as carteiras`
3. dashboard simples
4. painel técnico
5. chat
6. módulo de carteiras

## 14. O que Não Fazer

- Não quebrar a lógica global de carteira ativa.
- Não introduzir seleção local de carteira em cada página.
- Não espalhar leitura/escrita de storage sem necessidade.
- Não trocar a paleta atual.
- Não adicionar dependências pesadas sem motivo real.
- Não fazer refatoração estrutural grande junto com mudança pequena de interface.

## 15. Checklist Final

1. A mudança respeita a stack atual?
2. A seleção global de carteira continua funcionando?
3. O modo `Todas as carteiras` está coberto?
4. A UI continua coerente com a identidade do OPERUM?
5. Os textos continuam claros e sem encoding quebrado?
6. `npm run build` passou?

## 16. Documento Vivo

Sempre que houver mudança importante em:

- arquitetura
- contexto global
- persistência
- identidade visual
- navegação
- regras de análise por carteira

a IA deve atualizar este `skillsFront.md` para refletir o estado real do projeto.
