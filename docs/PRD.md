# Checklist para criação do PRD

## 1. Identificação do documento

Resposta:

Nome: Operum  
Versão: v0.2  
Responsáveis:
- Produto -> Tomáz
- Backend / IA -> Rony e Lucas
- Frontend -> Ian e Tomáz
- Infraestrutura -> Aksel

Data de criação: 15/06/2026  
Última atualização: 01/07/2026

---

## 2. Resumo executivo do produto

Resposta:

O Operum é uma plataforma web de apoio à análise de investimentos. O produto ajuda o usuário a organizar carteiras, acompanhar notícias relevantes do mercado e entender como diferentes ativos e contextos macroeconômicos podem impactar seus investimentos.

O principal problema resolvido é a dificuldade de transformar dados financeiros dispersos em entendimento claro para apoiar decisões mais conscientes. Hoje muitos investidores dependem de vídeos longos, planilhas, fóruns, notícias soltas e interpretações manuais.

O Operum beneficia principalmente investidores pessoa física, de iniciantes a intermediários, e secundariamente empresas ou assessorias que desejem oferecer uma camada de análise mais clara para seus clientes.

---

## 3. Contexto e problema

Resposta:

Cenário atual:
As pessoas costumam aprender e decidir sobre investimentos usando uma mistura de vídeos no YouTube, conteúdos pagos, notícias soltas, planilhas, comunidades online, aplicativos de corretoras e tentativas por conta própria. O acesso ao investimento ficou mais fácil, mas o entendimento do contexto não acompanhou essa facilidade.

Dores do usuário:
- O usuário tem dificuldade para interpretar o que está acontecendo com seus ativos.
- O usuário se perde entre muitas fontes de informação.
- O usuário não consegue organizar a carteira com clareza.
- O usuário tem medo de errar por falta de contexto.
- O usuário sente insegurança para decidir sozinho.
- O usuário pode pagar por conteúdos caros e ainda assim continuar confuso.

Por que isso importa agora:
O número de investidores cresce no Brasil, e mais pessoas estão expostas a produtos financeiros com diferentes riscos, prazos e comportamentos. Isso aumenta a necessidade de uma solução que una organização, educação e contexto de mercado em um só lugar.

Evidências do problema:
- Crescimento da base de investidores no Brasil entre 2024 e 2025.
- Benchmarking com plataformas como XP, Rico, Modal, Warren e Magnetis, que focam mais em execução ou automação do que em clareza educativa e contextual.
- Experiência direta do time com a dificuldade de organizar e acompanhar investimentos em meio a informações dispersas.
- Necessidade recorrente de recorrer a múltiplas fontes externas para compreender uma decisão de investimento.

---

## 4. Objetivo do produto

Resposta:

Objetivo principal:
Permitir que o usuário compreenda melhor sua carteira e o contexto de mercado para tomar decisões de investimento com mais clareza, organização e segurança.

Objetivos secundários:
- Permitir criação, edição e acompanhamento de carteiras personalizadas.
- Exibir análises por ativo e da composição da carteira como um todo.
- Filtrar e resumir notícias relevantes para o contexto do usuário.
- Oferecer suporte educacional por meio de um chatbot financeiro com linguagem simples.
- Possibilitar leitura mais técnica para usuários avançados por meio de um dashboard complementar.

O que será considerado sucesso:
- Usuário consegue criar ou importar sua lógica de carteira e visualizar uma análise inicial sem depender de outras ferramentas.
- Usuário entende rapidamente quais ativos e classes concentram mais risco ou peso na carteira.
- Usuário encontra notícias relevantes e associadas aos seus ativos.
- Usuário sente aumento de confiança e entendimento, mesmo sem recomendação direta de compra ou venda.

---

## 5. Público-alvo e personas

Resposta:

Usuário principal:
Investidor pessoa física que quer entender melhor no que está investindo e acompanhar sua carteira com mais clareza.

Usuários secundários:
- Investidores mais experientes que querem uma visão técnica complementar.
- Empresas, escritórios ou assessorias que possam usar o Operum como apoio educacional e analítico para clientes.

Personas:

Persona 1  
Nome: Ricardo  
Perfil: Iniciante em investimentos, renda controlada, medo de perder dinheiro  
Dor principal: Não sabe por onde começar nem como interpretar o mercado  
Objetivo: Aprender a investir com mais segurança  
Como o produto ajuda: Organiza a carteira, explica o contexto com linguagem simples e mostra uma leitura inicial dos ativos

Persona 2  
Nome: Patrícia  
Perfil: Investidora com experiência intermediária, já possui carteira diversificada  
Dor principal: Dificuldade para expandir ou rebalancear a carteira com base em contexto atual  
Objetivo: Garantir longevidade e coerência da carteira  
Como o produto ajuda: Exibe composição, riscos de concentração, notícias relevantes e análise por ativo

Tipos de permissão:
- Usuário comum
- Administrador técnico futuro

No MVP atual existe apenas o perfil de usuário comum.

---

## 6. Proposta de valor

Resposta:

Promessa central:
Organizar carteiras e transformar dados de mercado em leitura clara, útil e rastreável para diferentes perfis de investidor.

Diferenciais:
- Organização da carteira em uma interface simples.
- Análise por ativo e análise geral da composição da carteira.
- Relação entre preço, contexto macro e notícias.
- Chatbot educativo com foco em explicação e não em hype.
- Transparência sobre fontes usadas na análise.
- Visão amigável e visão técnica no mesmo produto.

Benefício prático:
O usuário economiza tempo, ganha contexto, entende melhor sua carteira e reduz a dependência de múltiplas ferramentas externas para acompanhar seus investimentos.

---

## 7. Escopo do MVP

Resposta:

O que entra na primeira versão:
- Cadastro e login
- Gestão básica de sessão
- Criação, edição e exclusão de carteiras
- Adição e remoção de ativos
- Dashboard com resumo da carteira
- Dashboard técnico complementar
- Tela de notícias com busca, filtros e paginação
- Tela de chatbot educativo
- Tela de configurações e preferências
- Análise geral da carteira
- Análise individual por ativo
- Dados de preço e histórico para ativos suportados

O que fica fora do MVP:
- Sistema de pagamento
- Aplicativo mobile nativo
- Painel administrativo completo
- Recomendação automática de compra e venda
- Execução de ordens ou integração com corretora
- Landing page comercial definitiva
- Importação automática via corretora
- Suporte robusto a renda fixa no motor analítico

Prioridade das features:

Must Have:
- Autenticação
- CRUD de carteiras
- Dados de mercado
- Notícias com filtros
- Análise geral da carteira
- Análise por ativo

Should Have:
- Chatbot educativo
- Preferências de notícias
- Dashboard técnico

Could Have:
- Simulação de cenários mais avançada
- Onboarding guiado
- Alertas configuráveis

Won't Have Now:
- Pagamentos
- Integração com corretoras
- Recomendações transacionais
- App mobile nativo

---

## 8. Funcionalidades principais

Resposta:

Funcionalidade: Autenticação  
Descrição: o usuário cria conta, faz login, mantém sessão e altera senha  
Problema que resolve: garante acesso individual aos dados e continuidade de uso  
Usuário: usuário comum  
Entrada esperada: nome, e-mail e senha  
Saída esperada: conta criada, sessão iniciada e acesso ao sistema  
Regras de negócio:
- e-mail deve ser único
- senha deve ter tamanho mínimo
- rotas privadas exigem autenticação
Critérios de aceitação:
- usuário consegue criar conta
- usuário consegue fazer login
- usuário não autenticado não acessa áreas privadas
- usuário consegue sair da conta

Funcionalidade: Gestão de carteiras  
Descrição: criar, listar, editar, excluir e selecionar carteiras  
Problema que resolve: organiza o acompanhamento dos investimentos  
Usuário: usuário comum  
Entrada esperada: nome da carteira, moeda base  
Saída esperada: carteira criada e disponível para edição e análise  
Regras de negócio:
- máximo de 50 carteiras no total
- listagem com 10 carteiras por página
- exclusão individual e em lote
Critérios de aceitação:
- usuário consegue criar carteira
- usuário consegue renomear carteira
- usuário consegue excluir uma ou várias carteiras
- usuário consegue definir carteira ativa

Funcionalidade: Gestão de ativos na carteira  
Descrição: adicionar e remover posições com ticker, quantidade e preço médio opcional  
Problema que resolve: estrutura os ativos da carteira para cálculo e análise  
Usuário: usuário comum  
Entrada esperada: ticker, classe do ativo, quantidade e preço médio opcional  
Saída esperada: posição salva e refletida na carteira  
Regras de negócio:
- quantidade deve ser maior que zero
- ticker deve existir no universo suportado
- preço médio é opcional no MVP
Critérios de aceitação:
- usuário consegue adicionar ativo válido
- usuário consegue remover ativo
- carteira exibe posição atualizada após a ação

Funcionalidade: Notícias de mercado  
Descrição: listar, filtrar e resumir notícias relevantes para o contexto financeiro  
Problema que resolve: reduz dispersão de informação e melhora o contexto da análise  
Usuário: usuário comum  
Entrada esperada: filtros por ativo, sentimento, impacto, intervalo e busca textual ou semântica
Saída esperada: lista paginada de notícias com resumo e metadados  
Regras de negócio:
- paginação padrão de 30 itens
- filtros e busca acontecem no backend
- notícias podem ser oficiais ou editoriais
- quando houver consulta, a busca combina palavras exatas, significado, recência e qualidade da fonte
- indisponibilidade da busca semântica deve ativar fallback textual
Critérios de aceitação:
- usuário consegue buscar notícias
- usuário encontra notícias semanticamente relacionadas mesmo sem correspondência literal
- usuário consegue filtrar por contexto
- usuário consegue abrir resumo e link original

Funcionalidade: Análise geral da carteira  
Descrição: gerar uma síntese da composição, concentração e contexto da carteira  
Problema que resolve: ajuda o usuário a entender a carteira como conjunto  
Usuário: usuário comum  
Entrada esperada: carteira com ativos válidos  
Saída esperada: score, síntese, forças, sobreposições e diagnóstico  
Regras de negócio:
- não emitir recomendação direta de compra ou venda
- explicitar baixa confiança quando faltarem dados
- priorizar fatos oficiais e contexto rastreável
Critérios de aceitação:
- sistema retorna análise estruturada da carteira
- sistema exibe fontes agrupadas
- sistema continua funcional mesmo com dados parciais

Funcionalidade: Análise individual por ativo  
Descrição: gerar leitura por ativo com base em preço, notícias e contexto macro  
Problema que resolve: dá clareza sobre o papel de cada ativo na carteira  
Usuário: usuário comum  
Entrada esperada: carteira e ticker presentes na posição  
Saída esperada: análise textual, janela histórica, perspectiva e fontes  
Regras de negócio:
- usar notícias do ativo, setor e macro
- usar histórico de notícias quando o histórico de preço for insuficiente
- indicar confiança da análise
Critérios de aceitação:
- usuário consegue abrir análise por ativo
- sistema mostra histórico, perspectiva e fontes
- sistema informa quando os dados forem insuficientes

Funcionalidade: Chatbot educativo  
Descrição: responder dúvidas básicas sobre investimentos e sobre a carteira ativa  
Problema que resolve: reduz barreira de entendimento para usuários iniciantes  
Usuário: usuário comum  
Entrada esperada: mensagem de texto do usuário  
Saída esperada: resposta educativa contextualizada  
Regras de negócio:
- tom explicativo e simples
- sem recomendação de compra ou venda
- pode usar a carteira ativa como contexto
Critérios de aceitação:
- usuário consegue enviar mensagem
- sistema responde com linguagem simples
- chatbot consegue comentar o contexto da carteira ativa

---

## 9. Histórias de usuário

Resposta:

- Como investidor iniciante, quero criar uma conta, para acessar minhas carteiras com segurança.
- Como usuário, quero criar uma carteira, para organizar meus ativos em um só lugar.
- Como usuário, quero adicionar ativos à carteira, para visualizar minha composição real.
- Como usuário, quero ver um resumo da minha carteira, para entender rapidamente o que mais pesa nela.
- Como usuário, quero abrir uma análise por ativo, para entender o contexto de um investimento específico.
- Como usuário, quero ler notícias relacionadas aos meus ativos, para acompanhar o que pode impactá-los.
- Como usuário, quero usar um chatbot educativo, para tirar dúvidas sem precisar sair da plataforma.
- Como usuário, quero ajustar preferências de notícias, para receber uma experiência mais relevante.

Critérios de aceitação por história:

História: criar conta
- Dado que o usuário preenche nome, e-mail e senha válidos, quando confirmar o cadastro, então a conta deve ser criada e a sessão iniciada.

História: criar carteira
- Dado que o usuário informa um nome válido, quando salvar a carteira, então ela deve aparecer na listagem.

História: adicionar ativo
- Dado que o usuário seleciona um ticker suportado e quantidade válida, quando confirmar, então o ativo deve aparecer no detalhe da carteira.

História: ver análise geral
- Dado que a carteira possui ativos, quando a tela de detalhe ou dashboard carregar, então o sistema deve exibir uma leitura geral da composição.

História: ver análise por ativo
- Dado que o usuário abre a análise de uma posição, quando houver dados suficientes, então o sistema deve exibir leitura textual, histórico e fontes.

História: ler notícias
- Dado que o usuário aplica filtros, quando a busca for executada, então o sistema deve retornar notícias paginadas compatíveis com o filtro.

História: usar chatbot
- Dado que o usuário envia uma pergunta, quando o sistema processar a mensagem, então deve retornar uma resposta educativa e contextual.

---

## 10. Fluxos do usuário

Resposta:

Fluxo principal:
Acessar plataforma -> criar conta ou fazer login -> criar carteira -> adicionar ativos -> visualizar dashboard -> abrir detalhe da carteira -> consultar análise geral e por ativo -> acompanhar notícias -> usar chatbot para dúvidas

Fluxo de erro:
Usuário tenta adicionar ativo inválido -> sistema bloqueia ação e informa erro  
Usuário acessa carteira removida -> sistema informa indisponibilidade e redireciona para listagem  
Usuário tenta carregar análise e o dado externo falha -> sistema mostra erro ou sucesso parcial sem quebrar a tela

Fluxo de usuário novo:
Criar conta -> acessar tela de carteiras -> criar primeira carteira -> adicionar primeiros ativos -> voltar ao dashboard para leitura inicial

Fluxo de usuário recorrente:
Fazer login -> abrir dashboard -> revisar carteira ativa -> aprofundar no detalhe da carteira -> filtrar notícias -> usar chatbot para dúvidas específicas

Fluxo administrativo:
Não faz parte do MVP atual.

---

## 11. Telas necessárias

Resposta:

Tela de Login  
Objetivo: permitir que o usuário acesse a plataforma  
Principais componentes:
- campo de e-mail
- campo de senha
- botão de entrar
- link para cadastro
- mensagem de feedback
Estados:
- vazio/inicial: formulário disponível
- carregando: autenticação em andamento
- sucesso: login concluído e redirecionamento
- erro: credenciais inválidas ou falha no serviço
- sem permissão/não disponível: usuário já autenticado

Tela de Cadastro  
Objetivo: permitir criação de conta  
Principais componentes:
- campo de nome
- campo de e-mail
- campo de senha
- campo de confirmação
- checkbox de aceite
- botão de criar conta
Estados:
- vazio/inicial
- carregando
- sucesso
- erro
- sem permissão/não disponível

Tela de Dashboard  
Objetivo: apresentar visão resumida da carteira selecionada  
Principais componentes:
- destaques da carteira
- composição
- notícias relacionadas
- opinião geral
- ações rápidas
Estados:
- vazio/inicial: sem carteira ou sem ativos
- carregando: dados da carteira e notícias sendo buscados
- sucesso: resumo e blocos disponíveis
- erro: falha ao montar visão geral
- sem permissão/não disponível: carteira inválida ou sessão expirada
- sucesso parcial: algum bloco falhou, mas a tela continua utilizável

Tela de Carteiras  
Objetivo: permitir criação, seleção, edição e exclusão de carteiras  
Principais componentes:
- formulário de nova carteira
- lista paginada
- botão de editar
- botão de remover
- seleção em lote
Estados:
- vazio/inicial: nenhuma carteira criada
- carregando
- sucesso
- erro
- sem permissão/não disponível
- criando carteira
- removendo carteira
- limite atingido

Tela de Detalhe da Carteira  
Objetivo: permitir gestão de ativos e visualização analítica da carteira  
Principais componentes:
- cabeçalho da carteira
- tabela de ativos
- formulário de adição de ativo
- filtros e ordenação
- gráficos
- análise geral
- análise por ativo
Estados:
- vazio/inicial: carteira sem ativos
- carregando: preços, análise e comparativos em andamento
- sucesso: ativos, gráficos e análises carregados
- erro: falha ao carregar dados
- sem permissão/não disponível: carteira não encontrada
- processando análise
- dados insuficientes
- sucesso parcial

Tela de Chatbot  
Objetivo: permitir dúvidas educativas sobre finanças e carteira  
Principais componentes:
- histórico de mensagens
- sugestões rápidas
- campo de mensagem
- botão de enviar
Estados:
- vazio/inicial: conversa ainda não iniciada
- carregando: contexto e base de apoio sendo carregados
- sucesso
- erro
- sem permissão/não disponível
- enviando mensagem
- gerando resposta

Tela de Configurações  
Objetivo: permitir ajuste de preferências e segurança da conta  
Principais componentes:
- dados do usuário
- formulário de senha
- temas de notícias
- preferências de interface
- botão de logout
Estados:
- vazio/inicial: preferências padrão
- carregando
- sucesso
- erro
- sem permissão/não disponível
- salvando preferências
- alterando senha

Tela de Notícias  
Objetivo: permitir acompanhamento de notícias do mercado  
Principais componentes:
- busca textual
- filtros
- grid/lista de notícias
- paginação
- modal de detalhe
- link para fonte original
Estados:
- vazio/inicial
- carregando
- sucesso
- erro
- sem permissão/não disponível
- sem resultados
- atualizando

Tela de Dashboard Técnico  
Objetivo: oferecer leitura mais analítica e detalhada para usuários avançados  
Principais componentes:
- gráficos técnicos
- comparativos
- indicadores
- métricas por ativo e carteira
Estados:
- vazio/inicial
- carregando
- sucesso
- erro
- sem permissão/não disponível
- dados insuficientes
- sucesso parcial

---

## 12. Requisitos funcionais

Resposta:

Autenticação
- O sistema deve permitir cadastro de usuário.
- O sistema deve permitir login com e-mail e senha.
- O sistema deve permitir logout.
- O sistema deve permitir alteração de senha.
- O sistema deve bloquear rotas privadas sem autenticação.

Carteiras
- O sistema deve permitir criar carteira com nome e moeda base.
- O sistema deve listar carteiras do usuário.
- O sistema deve permitir editar nome da carteira.
- O sistema deve permitir excluir carteira individualmente.
- O sistema deve permitir exclusão em lote.
- O sistema deve limitar a 50 carteiras por usuário no MVP.

Ativos
- O sistema deve permitir adicionar posição com ticker, classe, quantidade e preço médio opcional.
- O sistema deve permitir remover posição da carteira.
- O sistema deve exibir posições agrupadas por classe de ativo.
- O sistema deve exibir peso, preço atual, valor total e P&L não realizado quando disponível.

Notícias
- O sistema deve coletar e persistir notícias de fontes oficiais e editoriais.
- O sistema deve permitir busca textual em notícias.
- O sistema deve permitir busca híbrida usando texto e embeddings semânticos.
- O sistema deve permitir filtros por ativo, sentimento, impacto, período e contexto.
- O sistema deve listar notícias de forma paginada.
- O sistema deve mostrar resumo e link original da notícia.
- O sistema deve manter o bruto localmente no desenvolvimento e em storage privado no ambiente online.
- A busca semântica deve operar sobre o acervo coletado e não substituir os conectores de busca na web.

Análise
- O sistema deve gerar análise geral da carteira.
- O sistema deve gerar análise individual por ativo.
- O sistema deve indicar confiança da análise.
- O sistema deve usar notícias do ativo, setor e macro na análise.
- O sistema deve continuar operando com dados parciais quando possível.

Chat
- O sistema deve permitir envio de mensagens no chatbot.
- O sistema deve responder perguntas educativas básicas.
- O sistema deve conseguir usar a carteira ativa como contexto quando aplicável.

Configurações
- O sistema deve permitir salvar preferências de temas de notícias.
- O sistema deve permitir ajustar preferências de interface.

---

## 13. Requisitos não funcionais

Resposta:

Performance:
- 95% das rotas de leitura simples devem responder em até 1 segundo em ambiente estável local ou homologação.
- Processamentos analíticos mais pesados podem ultrapassar esse tempo, mas devem exibir feedback visual de carregamento.

Disponibilidade:
- O MVP deve estar disponível durante janelas normais de uso acadêmico e demonstração.
- Falhas de fontes externas não devem impedir o acesso às demais áreas do sistema.

Responsividade:
- O sistema deve funcionar em desktop e mobile web.

Acessibilidade básica:
- botões com texto claro
- contraste mínimo aceitável
- mensagens de erro compreensíveis
- navegação por teclado nas principais ações

Compatibilidade:
- versões recentes de Chrome, Edge, Firefox e Safari

Manutenibilidade:
- código separado por frontend, API, serviços e dados
- documentação suficiente para continuidade por outro desenvolvedor
- testes automatizados para módulos críticos

Segurança operacional:
- tokens e segredos não devem ficar expostos no frontend
- falhas de autenticação e serviços críticos devem ser registradas

---

## 14. Backend no PRD

Resposta:

Domínios principais:
- Usuários e autenticação
- Carteiras
- Ativos e universo de ativos
- Dados de mercado
- Notícias
- Modelos e análises
- Preferências do usuário
- Logs e status do sistema

Ações esperadas por domínio:

Usuários:
- criar conta
- autenticar
- consultar usuário atual
- alterar senha
- encerrar sessão

Carteiras:
- criar, listar, editar e excluir carteiras
- adicionar e remover posições
- calcular preços e composição
- buscar notícias relacionadas

Notícias:
- listar, paginar, filtrar, resumir, reindexar e fazer backfill

Modelos:
- expor status dos modelos
- treinar e consultar previsões
- gerar análise da carteira
- gerar análise por ativo

Integrações necessárias:
- fontes de preço de mercado
- fontes de notícias oficiais e editoriais
- camada de IA interna e modelos locais
- armazenamento local persistente

Regras importantes:
- usuário só acessa seus próprios dados
- análise não pode emitir recomendação direta
- quando não houver dado suficiente, o sistema deve dizer isso explicitamente

---

## 15. Frontend no PRD

Resposta:

Experiência esperada:
O Operum deve parecer claro, guiado, técnico quando necessário e amigável por padrão. A experiência deve reduzir jargão para iniciantes sem impedir profundidade para usuários mais avançados.

Páginas principais:
- Login
- Cadastro
- Dashboard
- Dashboard técnico
- Carteiras
- Detalhe da carteira
- Notícias
- Chatbot
- Configurações

Comportamento esperado das interações:
- botões devem mostrar loading quando houver processamento
- erros devem aparecer próximos do contexto da ação
- telas devem tratar vazio, erro, sucesso e indisponibilidade
- dados analíticos devem vir acompanhados de texto explicativo
- o sistema deve evitar linguagem que soe como recomendação de investimento

Dashboard:
- deve mostrar a carteira em foco
- deve destacar concentração, composição e próximos passos
- deve exibir notícias relacionadas e opinião geral

Onboarding:
- no primeiro acesso, o fluxo principal deve levar o usuário a criar uma carteira e adicionar ativos

---

## 16. Banco de dados no PRD

Resposta:

Entidades principais:
- Usuário
- Sessão
- Preferências do usuário
- Carteira
- Posição
- Ativo
- Notícia
- Análise de carteira
- Análise por ativo
- Modelos treinados
- Logs

Dados principais:

Usuário:
- id
- nome
- e-mail
- senha hash
- data de criação

Sessão:
- token
- usuário
- data de criação
- data de expiração

Preferências:
- tópicos de notícias
- modo compacto
- alertas locais

Carteira:
- id
- nome
- moeda base
- data de criação
- data de atualização

Posição:
- ticker
- classe do ativo
- quantidade
- preço médio
- moeda

Ativo:
- ticker
- nome
- classe
- setor
- país
- moeda
- subtipo

Notícia:
- id
- título
- subtítulo
- resumo
- conteúdo prévio
- fonte
- url
- data de publicação
- ativos mencionados
- sentimento
- impacto
- relevância

Análise:
- score
- resumo
- diagnóstico
- confiança
- fontes usadas
- data de geração

Dados sensíveis:
- senha hash
- e-mail
- token de sessão
- eventuais chaves de integração

Necessidade de histórico:
- o usuário deve conseguir visualizar análises e notícias persistidas em contexto recente
- o sistema deve manter histórico local de notícias e de carteiras

Necessidade de exclusão:
- o usuário deve poder excluir carteiras
- futuramente deve poder excluir a conta e os dados relacionados

---

## 17. Segurança

Resposta:

Autenticação:
- acesso por e-mail e senha
- sessão persistida por token
- logout explícito disponível ao usuário

Autorização:
- usuário comum acessa apenas suas próprias carteiras, preferências e análises
- rotas privadas exigem autenticação válida

Proteção de dados sensíveis:
- senhas nunca devem ser salvas em texto puro
- tokens e chaves não podem ficar expostos no frontend
- dados do usuário devem ser isolados por identidade

Regras de sessão:
- token inválido deve bloquear acesso
- sessão expirada deve redirecionar para login
- usuário pode encerrar a sessão manualmente

Riscos de segurança relevantes:
- acesso indevido a dados de outro usuário
- exposição de tokens
- abuso de endpoints de análise
- injeção em campos de texto
- vazamento de chaves de integração

---

## 18. Regras de negócio

Resposta:

Regras comerciais e de produto:
- o Operum é uma ferramenta de apoio à análise e educação, não de recomendação direta
- a análise deve priorizar clareza, contexto e rastreabilidade de fontes
- a análise geral da carteira depende da existência de ativos válidos
- a análise por ativo depende de o ativo existir dentro da carteira

Regras de limite:
- até 50 carteiras no total
- 10 carteiras por página na UI
- notícias com paginação de 30 itens

Regras de plano:
- o MVP não possui planos pagos definidos
- todos os usuários usam a mesma camada funcional no momento

Regras de bloqueio:
- se o usuário não estiver autenticado, não acessa áreas privadas
- se o ativo não estiver no universo suportado, ele não pode ser adicionado
- se não houver dados suficientes, o sistema informa indisponibilidade parcial em vez de inventar análise

---

## 19. Integrações externas

Resposta:

Serviços externos necessários:
- fontes de preço de mercado
- fontes de notícias oficiais
- fontes de notícias editoriais
- bibliotecas de machine learning
- armazenamento local persistente

Finalidade de cada integração:
- dados de mercado: buscar preço atual e histórico
- notícias: fornecer contexto factual e editorial
- ML local: ranking de notícias, previsões e análises

Dependência crítica:
- preços de mercado e notícias são críticos para a proposta analítica
- se essas fontes falharem, o produto continua com funcionalidade reduzida

Fallback:
- se a notícia falhar, a carteira ainda pode ser exibida com dados locais e preço
- se o preço falhar, o sistema deve informar indisponibilidade daquele bloco
- se a análise falhar, o sistema deve manter CRUD e navegação funcionando

---

## 20. Dados, analytics e métricas

Resposta:

Eventos importantes:
- usuário criou conta
- usuário fez login
- usuário criou carteira
- usuário selecionou carteira ativa
- usuário adicionou ativo
- usuário abriu análise da carteira
- usuário abriu análise por ativo
- usuário filtrou notícias
- usuário enviou mensagem no chatbot
- usuário salvou preferências

KPIs do produto:
- número de usuários ativos
- número médio de carteiras por usuário
- taxa de carteiras com ao menos um ativo
- frequência de uso do dashboard
- taxa de abertura de análise por ativo
- uso do chatbot
- retenção semanal

Métricas técnicas:
- tempo de resposta da API
- taxa de erro por endpoint
- falhas de login
- falhas em fontes externas
- tempo para gerar análise da carteira
- tempo para gerar análise por ativo

---

## 21. Testes e qualidade

Resposta:

O que precisa ser testado:
- cadastro
- login
- proteção de rotas
- criação e remoção de carteiras
- adição e remoção de ativos
- listagem e filtros de notícias
- análise geral da carteira
- análise por ativo
- preferências do usuário

Critérios de aceite por funcionalidade:
- cadastro cria usuário e inicia sessão
- login válido autentica e login inválido exibe erro
- carteira criada aparece na listagem
- ativo adicionado aparece no detalhe
- análise retorna estrutura mínima esperada
- filtros de notícias alteram o resultado paginado

Testes de erro:
- credenciais inválidas
- sessão expirada
- carteira inexistente
- ticker inválido
- fonte externa indisponível
- ativo sem histórico suficiente

Testes de segurança básicos:
- usuário não acessa dados de outro usuário
- senha não aparece em respostas
- rotas privadas exigem autenticação

---

## 22. Infraestrutura e DevOps no PRD

Resposta:

Ambientes necessários:
- Desenvolvimento
- Homologação
- Produção futura

Deploy:
- o sistema deve permitir deploy controlado do frontend e backend separadamente
- mudanças aprovadas devem poder ser publicadas sem depender de ajuste manual complexo

Logs:
- erros de autenticação, notícias, dados de mercado e análise devem ser registrados

Monitoramento:
- API fora do ar
- erro em integração externa
- falha de autenticação
- lentidão nos endpoints de análise

Backup:
- dados persistidos localmente devem ter política simples de backup em ambientes relevantes

---

## 23. Observabilidade e suporte

Resposta:

Erros que precisam ser rastreados:
- erro de login
- erro ao carregar carteiras
- erro ao buscar preços
- erro ao carregar notícias
- erro ao gerar análise geral
- erro ao gerar análise por ativo
- erro ao salvar preferências

Informações mínimas em logs:
- data e hora
- endpoint ou serviço afetado
- tipo de erro
- id do usuário ou sessão quando aplicável
- mensagem de contexto técnico

Como suporte investiga:
Usuário informa e-mail e horário aproximado -> time consulta logs, status do endpoint e histórico da carteira ou ação executada.

Mensagens amigáveis:
- "Não foi possível carregar sua análise agora. Tente novamente em instantes."
- "Esse ativo ainda não possui dados suficientes para uma leitura confiável."
- "Sua sessão expirou. Faça login novamente para continuar."

---

## 24. Riscos e premissas

Resposta:

Premissas:
- o usuário entende o valor de organizar a carteira antes de buscar profundidade analítica
- as fontes externas continuarão disponíveis em nível suficiente para o MVP
- a análise explicativa sem recomendação direta é suficiente para gerar valor inicial

Riscos técnicos:
- indisponibilidade de fontes de preço ou notícias
- baixa cobertura de algumas fontes oficiais
- ativos sem histórico suficiente para boa previsão
- custo de manutenção do pipeline analítico

Riscos de negócio:
- usuário esperar recomendação direta de compra e venda
- concorrentes com experiência mais polida na camada visual
- percepção de complexidade para usuários muito iniciantes

Mitigações:
- mostrar estados de tela claros para falhas parciais
- assumir comunicação explícita sobre limites da análise
- manter foco em clareza, educação e organização
- priorizar ativos e contextos mais relevantes no MVP

---

## 25. Fora do escopo

Resposta:

Não será feito agora:
- app mobile nativo
- compra e venda de ativos
- integração com corretoras
- pagamento e assinatura
- painel administrativo completo
- recomendação automática transacional
- social features ou comunidade
- cobertura robusta de renda fixa analítica

Por que ficou fora:
Para reduzir complexidade e validar primeiro o núcleo do produto: carteira + notícias + análise + educação financeira.

Pode entrar em versões futuras:
- pós-MVP
- versão 2
- backlog futuro

---

## 26. Roadmap inicial

Resposta:

Fase 1: Autenticação e sessão  
Entrega: cadastro, login, proteção de rotas, logout

Fase 2: Carteiras  
Entrega: CRUD de carteiras, seleção de carteira ativa, posições

Fase 3: Dados de mercado e dashboard  
Entrega: preços, composição, resumo e dashboard inicial

Fase 4: Notícias e contexto  
Entrega: ingestão, filtros, paginação e resumo de notícias

Fase 5: IA interna e análises  
Entrega: análise geral da carteira e análise individual por ativo

Fase 6: Experiência complementar  
Entrega: chatbot educativo, configurações e dashboard técnico

Primeira entrega utilizável:
Usuário cria conta, monta uma carteira com ativos e visualiza ao menos um resumo básico com preços e composição.

Dependências entre fases:
- dashboard depende de carteira e posições
- análises dependem de preços, histórico e notícias
- chatbot contextual depende de carteira e ativos

Prazo estimado por fase:
- Fase 1: curta
- Fase 2: curta
- Fase 3: média
- Fase 4: média
- Fase 5: média/alta
- Fase 6: média

---

## 27. Critérios finais de aceite do PRD

Resposta:

- O problema está claro.
- O público-alvo está claro.
- O objetivo do produto está claro.
- O MVP está bem definido.
- O que está fora do escopo está claro.
- As funcionalidades estão priorizadas.
- As histórias de usuário estão escritas.
- Os critérios de aceitação são testáveis.
- As regras de negócio estão documentadas.
- Os principais dados estão identificados.
- Os requisitos de segurança estão descritos.
- Os riscos estão listados.
- As métricas de sucesso estão definidas.
- O time consegue ler o PRD e entender o que precisa ser construído.
- Ainda não há excesso de decisão técnica que deveria ficar para a SPEC.

---

## 28. Checklist final antes de partir para a SPEC

### Evolução do agente financeiro

- O agente responde em português brasileiro com profundidade adaptada à pergunta.
- Perguntas conceituais usam uma base editorial financeira, sem notícias incidentais.
- Perguntas temporais podem combinar conhecimento estável, notícias recentes e contexto da carteira.
- A base inicial contém 60 FAQs com fontes institucionais, exemplos e pontos de atenção.
- Notícias e fontes são deduplicadas e mantidas como rastreabilidade interna, sem blocos visuais na conversa.
- O usuário pode criar, reabrir, renomear e excluir conversas vinculadas à própria conta.
- O agente permanece educativo e não recomenda compra, venda, manutenção ou alocação específica.
- O agente pode citar instrumentos como exemplos educacionais, explicando riscos e sem prescrever uma escolha ao usuário.
- A resposta começa diretamente pelo conteúdo útil e não segue obrigatoriamente um modelo fixo de definição, explicação e exemplo.
- Quando nenhuma FAQ for suficientemente relevante, o agente pode usar conhecimento financeiro geral para conceitos estáveis.

Resposta:

- O PRD responde o que vamos construir.
- O PRD responde por que vamos construir.
- O PRD responde para quem vamos construir.
- O PRD responde o que entra no MVP.
- O PRD responde o que não entra agora.
- O PRD tem requisitos claros o suficiente para virar tarefas técnicas.
- O PRD tem critérios de aceite claros o suficiente para virar testes.
- O PRD foi revisado por produto, negócio e tecnologia.
- O PRD está pronto para ser transformado em SPEC técnica.
