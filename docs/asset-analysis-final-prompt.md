# Prompt de Governanca - Analise Final de Ativos

Este documento registra a governanca de produto para a analise individual de ativos do Operum. O backend continua sendo a fonte oficial dos calculos; o LLM apenas refina a narrativa em JSON estruturado.

## Objetivo

A analise deve ajudar o usuario comum a entender:

- o que aconteceu com o ativo;
- quais fatores podem ter influenciado o movimento;
- como separar empresa, preco do ativo e impacto na carteira;
- quais cenarios observar sem tratar previsao como certeza;
- quais indicadores acompanhar antes de decidir.

A analise nao deve emitir ordem direta de compra, venda, manutencao, alocacao ou rebalanceamento.

## Periodos

O texto deve respeitar separadamente:

- historico selecionado: `1w`, `1m`, `2m`, `3m`;
- perspectiva selecionada: `1w`, `1m`, `2m`, `3m`.

Nunca presumir que historico e perspectiva sao iguais.

## Validacoes e Qualidade dos Dados

Antes da narrativa, o sistema deve sinalizar lacunas quando houver:

- ausencia de preco atual;
- historico de preco incompleto ou vazio;
- poucas noticias diretamente relacionadas;
- ausencia de fundamentos estruturados;
- diferenca relevante entre preco atual e ultimo ponto historico.

No MVP, lacunas geram `data_quality_warnings` e reduzem a confianca. A analise so deve ficar indisponivel quando nao houver base minima de preco nem noticias.

## Separacao Conceitual

A analise deve separar obrigatoriamente:

- empresa/fundamentos: qualidade operacional e financeira, quando houver dados;
- acao/fundo/ativo: comportamento de preco, oscilacao, queda maxima, comparacao e sentimento;
- carteira: peso da posicao, concentracao e impacto aproximado no conjunto.

Nunca concluir que uma empresa piorou apenas porque o preco caiu. Nunca concluir que fundamentos estao pressionados apenas porque noticias tiveram tom negativo.

## Classificacoes

Usar labels simples para:

- situacao do ativo;
- tendencia recente do preco;
- fundamentos;
- sentimento das noticias;
- situacao da posicao na carteira;
- risco da posicao na carteira;
- confianca da analise.

Concentracao e uma caracteristica da posicao na carteira, nao um cenario do ativo.

## Linguagem

Usar PT-BR simples, profissional e educativo. Evitar termos tecnicos sem traducao.

Substituicoes preferidas:

- `drawdown` -> maior queda em relacao ao preco maximo do periodo;
- `momentum` -> tendencia recente do preco;
- `benchmark` -> indice de comparacao;
- `volatilidade` -> intensidade das oscilacoes;
- `fundamentos` -> situacao financeira e operacional;
- `sentimento` -> tom predominante das noticias e expectativas.

Evitar falsa precisao, previsoes absolutas, tom alarmista e linguagem promocional.

## Impacto na Carteira

Explicar concentracao com simulacao simples:

`impacto aproximado na carteira = peso do ativo x variacao simulada do ativo`

Exemplo: se o ativo representa 67,3% da carteira, uma queda de 10% no ativo impacta aproximadamente -6,7% da carteira, considerando os demais investimentos estaveis. Uma alta de 10% tem impacto positivo semelhante.

## Cenarios

A perspectiva deve conter tres cenarios:

- favoravel: condicoes necessarias e sinais de confirmacao;
- base: leitura equilibrada e fatores que sustentam o cenario;
- adverso: riscos, sinais de deterioracao e impacto potencial na carteira.

Nenhum cenario deve ser apresentado como certeza.

## Formato Estruturado

O endpoint deve retornar JSON em `analysis_sections` com:

- `visual_summary`;
- `summary`;
- `what_happened`;
- `company_situation`;
- `asset_price_situation`;
- `portfolio_impact`;
- `scenarios.favorable`;
- `scenarios.base`;
- `scenarios.adverse`;
- `what_to_watch`;
- `conclusion`;
- `data_quality_warnings`.

Campos antigos como `current`, `recent`, `outlook`, `recent_by_horizon` e `outlook_by_horizon` permanecem por compatibilidade.
