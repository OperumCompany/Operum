# Plano De Implementacao Do Operum

## Resumo

Este documento organiza a implementacao em fases para atualizar a comunicacao do Operum, melhorar a experiencia mobile, ajustar a geracao de analises com IA, corrigir o fluxo de noticias, implementar refresh token de sessao e revisar a velocidade das operacoes de carteira.

O objetivo e deixar o produto mais alinhado ao Operum atual: uma ferramenta de previsao e analise de ativos que combina noticias, leitura quantitativa dos ativos e uma camada de IA responsavel por transformar esses sinais em uma analise clara para o usuario.

## Fase 1: Landing Page Comercial

Atualizar a landing page para vender melhor a proposta central do Operum: previsao e analise inteligente de ativos.

Principais entregas:

- Reposicionar o headline e a narrativa principal para destacar o Operum como plataforma de previsao, analise e simulacao de ativos.
- Explicar os 3 motores de analise do produto:
  - IA para noticias: coleta, interpreta e relaciona noticias relevantes aos ativos.
  - IA para medicao de status dos ativos: avalia comportamento, contexto, sinais de mercado e situacao atual.
  - IA de formatacao da analise: organiza os sinais em uma leitura final clara, acionavel e compreensivel para o usuario.
- Adicionar secao sobre multiplas carteiras, permitindo simulacoes de cenarios, estrategias diferentes e comparacao entre composicoes.
- Tornar o texto mais persuasivo e comercial, com foco em conversao para cadastro.
- Manter o posicionamento educativo: o Operum apoia a analise, mas nao recomenda compra ou venda de ativos.

## Fase 2: UI/UX Mobile

Melhorar a usabilidade em telas mobile, especialmente nas telas de dashboard, carteira, analise por ativo e graficos.

Principais entregas:

- Revisar graficos em mobile para evitar overflow, legendas cortadas e perda de leitura.
- Ajustar a localizacao dos principais botoes, deixando a previsao com IA mais visivel.
- Renomear a coluna `IA` para `Analise com IA`.
- Ajustar tambem os `data-label` usados na tabela responsiva para manter o nome correto no mobile.
- Impedir zoom out em mobile atualizando a meta viewport para travar o comportamento no padrao mobile.
- Revisar overflow horizontal em cards, tabelas, graficos e filtros.
- Garantir area minima de toque para botoes e controles importantes.

## Fase 3: Textos Da Previsao

Padronizar o tamanho dos textos de previsao e analise exibidos ao usuario.

Principais entregas:

- Aplicar limite minimo de 750 caracteres e maximo de 1250 caracteres nos textos principais de previsao/analise.
- Ajustar a geracao deterministica, fallback e refino por IA para respeitar esse intervalo antes de retornar ao frontend.
- Garantir que os campos exibidos em `PortfolioDetailsPage` recebam textos consistentes.
- Tratar respostas abaixo do minimo com complemento explicativo baseado nos dados disponiveis.
- Tratar respostas acima do maximo com compactacao preservando riscos, sinais principais e disclaimer educativo.

## Fase 4: Dropdowns E Componentes De Selecao

Redesenhar os dropdowns e selects das caixinhas para ficarem mais consistentes com a identidade visual do Operum.

Principais entregas:

- Revisar seletores de carteira, classe de ativo, ativo, filtros de noticias e horizontes de previsao.
- Aplicar visual consistente: borda, foco, icone, padding, altura e estados hover/disabled.
- Melhorar leitura em mobile, evitando selects espremidos ou com texto cortado.
- Manter acessibilidade basica: foco visivel, navegacao por teclado e area de toque confortavel.
- Evitar que dropdowns criem overflow horizontal em telas pequenas.

## Fase 5: Noticias Do Dia

Investigar e corrigir por que as noticias do dia nao estao sendo carregadas ou exibidas.

Principais entregas:

- Revisar `NewsIngestionService`, incluindo fontes RSS, fontes HTML/listing e YFinance.
- Verificar os endpoints `/api/news`, `/api/news/reindex` e `/api/news/backfill`.
- Validar startup hooks de ingestao automatica em `app/main.py`.
- Confirmar configuracao e uso do token administrativo `OPERUM_REFRESH_TOKEN`, sem confundir com refresh token de autenticacao.
- Revisar parse de datas para evitar noticias recentes sendo salvas com data incorreta.
- Adicionar teste para garantir que noticias recentes aparecem quando a ingestao retorna itens publicados no dia.
- Melhorar logs de ingestao para identificar fonte vazia, erro de parsing, bloqueio externo ou falha de armazenamento.

## Fase 6: Refresh Token De Autenticacao

Implementar refresh token real de sessao para usuarios autenticados.

Principais entregas:

- Separar token de acesso curto e refresh token longo.
- Armazenar ambos em cookies `HttpOnly`.
- Criar endpoint `/api/auth/refresh`.
- Adaptar `api.ts` para tentar renovar a sessao uma unica vez ao receber `401`.
- Atualizar `/api/auth/logout` para invalidar access token e refresh token.
- Atualizar o servico de autenticacao para persistir, validar, rotacionar e revogar refresh tokens.
- Garantir que o refresh token de usuario seja separado do `OPERUM_REFRESH_TOKEN`, que hoje e administrativo para noticias.

## Fase 7: Login

Melhorar a mensagem, o fluxo visual e os estados da tela de login.

Principais entregas:

- Reescrever a copy da tela de login para reforcar o valor do Operum: previsao, analise de ativos, noticias e carteiras de simulacao.
- Melhorar mensagens de erro para serem mais amigaveis e seguras.
- Evitar expor detalhes internos de falha de autenticacao.
- Adicionar estado de carregamento no botao `Entrar`.
- Impedir multiplos submits enquanto a tentativa de login esta em andamento.
- Melhorar a mensagem de proximo passo para usuarios novos ou indecisos.

## Fase 8: Performance Ao Adicionar E Remover Ativos

Revisar a velocidade percebida e real ao adicionar ou remover ativos das carteiras.

Principais entregas:

- Medir gargalos no `PortfoliosContext`, endpoints de posicoes e chamadas subsequentes de precos, historico e analises.
- Evitar invalidacoes amplas quando apenas uma posicao muda.
- Aplicar atualizacao otimista quando a operacao for segura.
- Invalidar apenas os dados dependentes da carteira alterada.
- Evitar limpar todas as analises quando a mudanca afeta somente um ticker.
- Criar teste ou benchmark simples para comparar tempo de adicionar/remover antes e depois.
- Manter mensagens de erro claras caso a operacao falhe e seja necessario desfazer uma atualizacao otimista.

## Test Plan

- Rodar testes existentes de frontend e backend relacionados a carteira, noticias, autenticacao e analise.
- Testar manualmente em mobile: landing, dashboard, carteira, coluna `Analise com IA`, graficos e dropdowns.
- Validar login, expiracao de sessao, refresh automatico e logout.
- Confirmar que noticias recentes aparecem apos ingestao ou reindex.
- Conferir que textos de previsao ficam entre 750 e 1250 caracteres.
- Medir tempo percebido de adicionar e remover ativos antes e depois dos ajustes de performance.

## Assumptions

- Este arquivo deve ficar na raiz do projeto e nao substitui `plano.md`.
- Refresh token significa renovacao de sessao do usuario, nao o `OPERUM_REFRESH_TOKEN` administrativo usado em noticias.
- A implementacao futura deve preservar o aviso educativo: o Operum nao recomenda compra ou venda de ativos.
- As fases podem ser implementadas sequencialmente, mas Fase 2 e Fase 4 devem ser validadas juntas em mobile por compartilharem componentes visuais.
