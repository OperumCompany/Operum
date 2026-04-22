# Operum

Frontend React para acompanhamento de carteiras, leitura simplificada de investimentos e painel técnico com análises mais detalhadas.

## Visão Geral

O OPERUM foi estruturado para atender dois perfis de uso:

- `Visão geral`: leitura amigável da carteira selecionada, com linguagem menos técnica.
- `Painel técnico`: gráficos e comparativos mais densos para leitura analítica.

A aplicação também possui:

- seleção global de `Carteira ativa` no header
- opção de analisar `Todas as carteiras`
- módulo de carteiras com criação, importação, edição e remoção
- chat explicativo com respostas baseadas na seleção atual
- notícias de mercado e configurações básicas

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

## Estrutura Principal

```text
src/
  components/        # componentes base de UI e proteção de rota
  context/           # auth e estado global de carteiras
  data/              # mocks e dados locais
  layout/            # shell principal da aplicação
  pages/             # telas principais
  types/             # tipos TypeScript
  utils/             # storage e utilitários de carteira
```

## Fluxos Importantes

### 1. Carteira ativa global

A seleção de carteira no header controla o comportamento dos principais módulos:

- dashboard simples
- painel técnico
- chat
- resumo da carteira ativa no módulo de carteiras

Quando `Todas as carteiras` está selecionado, os módulos passam a operar no consolidado.

### 2. Persistência local

O projeto usa `localStorage` para simular persistência de:

- sessão do usuário
- carteiras
- carteira ativa
- preferências
- histórico de chat

As chaves ficam centralizadas em `src/utils/storage.ts`.

### 3. Dados mockados

Não há backend integrado neste momento. Os dados de usuário, ativos, notícias, séries de gráficos e carteira inicial ficam em `src/data/mocks.ts`.

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

## Padrões do Frontend

- paleta base definida em `src/styles.css`
- componentes compartilhados em `src/components/UI.tsx`
- sidebar e header centralizados em `src/layout/AppShell.tsx`
- estado global de carteiras em `src/context/PortfoliosContext.tsx`

## Observações

- o projeto hoje é orientado a demonstração/prototipação
- os gráficos usam dados simulados
- a build atual funciona normalmente, mas o Vite ainda alerta sobre tamanho de chunk no bundle final

## Validação

Antes de entregar mudanças no frontend, o mínimo esperado é:

```bash
npm run build
```

Se a alteração afetar navegação, também vale validar manualmente:

- troca de carteira ativa
- visão geral
- painel técnico
- chat
- módulo de carteiras
