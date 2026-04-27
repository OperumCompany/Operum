# Operum

Frontend React para acompanhamento de carteiras, leitura simplificada de investimentos e painel tecnico com analises mais detalhadas.

## Visao Geral

O Operum foi estruturado para atender dois perfis de uso:

- `Visao geral`: leitura amigavel da carteira selecionada, com linguagem menos tecnica.
- `Painel tecnico`: graficos e comparativos mais densos para leitura analitica.

A aplicacao tambem possui:

- selecao global de `Carteira ativa` no header
- opcao de analisar `Todas as carteiras`
- modulo de carteiras com criacao, importacao, edicao e remocao
- chat explicativo com respostas baseadas na selecao atual
- noticias de mercado e configuracoes basicas

## Stack

- `React 18`
- `TypeScript`
- `Vite`
- `React Router DOM`
- `Recharts`
- `Tailwind CSS`
- `Lucide React`

## Scripts

```bash
npm install
npm run dev
npm run build
npm run preview
```

## Deploy na Vercel

O projeto pode ser publicado como frontend estatico na Vercel.

1. Importe o repositorio na Vercel.
2. Mantenha o preset de framework como `Vite`.
3. Use `npm run build` como comando de build.
4. Use `dist` como output directory.

O arquivo `vercel.json` ja foi incluido para garantir o rewrite das rotas do `React Router` para `index.html`.

## Estrutura Principal

```text
src/
  components/        # componentes base de UI e protecao de rota
  context/           # auth e estado global de carteiras
  data/              # mocks e dados locais
  layout/            # shell principal da aplicacao
  pages/             # telas principais
  types/             # tipos TypeScript
  utils/             # storage e utilitarios de carteira
```

## Fluxos Importantes

### 1. Carteira ativa global

A selecao de carteira no header controla o comportamento dos principais modulos:

- dashboard simples
- painel tecnico
- chat
- resumo da carteira ativa no modulo de carteiras

Quando `Todas as carteiras` esta selecionado, os modulos passam a operar no consolidado.

### 2. Persistencia local

O projeto usa `localStorage` para simular persistencia de:

- sessao do usuario
- base local de usuarios cadastrados
- carteiras por usuario
- carteira ativa por usuario
- preferencias por usuario
- historico de chat por usuario

As chaves ficam centralizadas em `src/utils/storage.ts`.

### 3. Conta de exemplo

- E-mail: `camila@operum.app`
- Senha: `Operum123`

A conta da Camila continua fixa como perfil de demonstracao. Novos cadastros ficam salvos apenas no navegador de quem estiver usando a aplicacao.

### 4. Dados mockados

Nao ha backend integrado neste momento. Os dados de usuario, ativos, noticias, series de graficos e carteira inicial ficam em `src/data/mocks.ts`.

## Rotas

- `/login`
- `/registro`
- `/`
- `/dashboard-tecnico`
- `/noticias`
- `/chat`
- `/carteiras`
- `/carteiras/:id`
- `/configuracoes`

## Padroes do Frontend

- paleta base definida em `src/styles.css`
- componentes compartilhados em `src/components/UI.tsx`
- sidebar e header centralizados em `src/layout/AppShell.tsx`
- estado global de carteiras em `src/context/PortfoliosContext.tsx`

## Observacoes

- o projeto hoje e orientado a demonstracao e prototipacao
- os graficos usam dados simulados
- a build atual funciona normalmente, mas o Vite ainda alerta sobre tamanho de chunk no bundle final
- por usar `localStorage`, cada navegador mantera sua propria base local de teste

## Validacao

Antes de entregar mudancas no frontend, o minimo esperado e:

```bash
npm run build
```

Se a alteracao afetar navegacao, tambem vale validar manualmente:

- troca de carteira ativa
- visao geral
- painel tecnico
- chat
- modulo de carteiras
