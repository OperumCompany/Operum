# Performance das análises

## Refinamento estruturado e downloads das previsões — 14/09/2026

Esta etapa compara com a revisão `dc6fbe4b0f32a2345b880b289a709f8183d933ee`, posterior às otimizações originais descritas abaixo. Não altera modelo, timeout, limites de geração, fórmulas, fontes ou contrato público.

Ativo e carteira usam schemas Pydantic internos e uma única chamada de refinamento. O Ollama recebe `format`, `think=false` e `stream=false`; provedores compatíveis mantêm o protocolo anterior e têm o retorno validado localmente. Em erro ou conteúdo inválido, a resposta determinística é preservada integralmente. O caminho antigo continua disponível para chatbot e análise preditiva. Foram removidos somente o validador privado e os ramos de formatos antigos do ativo, que ficaram inacessíveis com o contrato das três caixas; suas referências foram verificadas no projeto.

`predict_many` verifica modelos, baixa históricos uma vez por ticker elegível e calcula depois, fora do executor. A carteira preserva as primeiras oito posições e suas contribuições, inclusive posições repetidas. Downloads usam instâncias de `Ticker.history`, com os mesmos parâmetros efetivos do `yf.download` anterior, evitando a reinicialização concorrente das estruturas globais desse último. Falhas são transportadas como resultados indisponíveis, sem novo download no lote.

### Resultados controlados

Oito downloads simulados de 40 ms, cinco amostras por configuração: mediana de **324,62 ms com um worker para 81,66 ms com quatro**, redução de **74,84%**. P95: 345,58 ms e 83,14 ms. Isso mede o lote de I/O, não a análise inteira. Dados completos: [forecast-batch-performance.json](forecast-batch-performance.json).

A suíte de backend passou em **363 testes**. Os testes novos cobrem schema, timeout, provedor indisponível, validação de conteúdo, fallback integral, preservação de campos e horizontes, equivalência dos adaptadores Yahoo com a mesma resposta de origem, ordem, duplicação, modelos ausentes, falha parcial, requisições simultâneas e limite global do executor. A comparação offline também preservou respostas determinísticas nos 12 cenários e 19 combinações adicionais de horizontes.

### Chamadas reais ao Ollama

Modelo local `qwen3:4b`, duas chamadas sequenciais por versão/cenário, usando dados **sintéticos e idênticos** de mercado, notícias e carteira. Os tempos medem somente refinamento real, sem simular a geração. O arquivo [refinement-live-performance.json](refinement-live-performance.json) contém amostras, textos e avaliação. Não representa latência de endpoints completos nem uma estimativa robusta de P95 de produção.

| Cenário | Mediana antes | Mediana depois | P95 antes | P95 depois | Textos aceitos antes/depois |
|---|---:|---:|---:|---:|---:|
| Ativo | 35,98 s | 15,31 s | 39,20 s | 15,79 s | 0/2 → 0/2 |
| Carteira de 5 posições | 38,15 s | 17,40 s | 42,18 s | 17,99 s | 0/2 → 2/2 |
| Carteira de 10 posições | 38,49 s | 17,89 s | 42,48 s | 18,23 s | 0/2 → 2/2 |
| Carteira de 20 posições | 40,06 s | 27,44 s | 43,08 s | 27,96 s | 0/2 → 2/2 |

Na carteira, a redução observada foi de 31% a 54%, acompanhada de maior aceitação, não de mais fallbacks. A leitura das respostas sintéticas confirmou cobertura de composição, sobreposições e blocos, com métricas e incertezas do contexto; não constitui avaliação ampla de qualidade factual. No ativo, o JSON novo foi válido, mas a validação de conteúdo existente rejeitou os três exemplos medidos, inclusive o simultâneo. O diagnóstico inicial foi preservado. Portanto, a espera caiu, mas **não foi demonstrado ganho na entrega de texto refinado do ativo**; não foram afrouxadas validações para melhorar esse indicador.

Com ativo e carteira de 10 posições simultâneos, a versão anterior levou 67,96 s e 62,39 s; a carteira sofreu timeout. A versão nova levou 37,38 s e 21,16 s, com uma chamada por análise, sem timeout e com o texto da carteira aceito. É apenas um par por versão. Houve reinício do Ollama antes desse teste; o custo de carregamento inicial afeta a comparação e impede atribuir todo o ganho à alteração. Não foi forçado descarregamento do modelo para criar um teste frio independente. A instrumentação de timeout da versão anterior foi coletada somente no par simultâneo.

**Limitação da medição Yahoo:** o provedor retornou `YFRateLimitError` já nas consultas sequenciais anteriores. A tentativa foi interrompida; não há resultado válido de ganho real de downloads ou de latência completa dos endpoints. Não foi alterado o limite do provedor nem acrescentado retry. A equivalência numérica foi validada com respostas de origem controladas, e a medição real deve ser repetida quando o acesso estiver disponível.

### Métricas e reprodução

`llm_refinement_metrics` informa resultado, tempo HTTP em ms e métricas do Ollama quando fornecidas: durações em nanossegundos e contagens de tokens. Valores ausentes ficam indisponíveis. O tempo residual não é interpretado como fila. Não são registrados prompts, respostas nem dados pessoais nos logs de execução; somente o benchmark salva textos gerados a partir de fixtures sintéticas.

Contadores: `llm_calls`, `llm_validated`, `llm_invalid_response`, `llm_http_error`, `llm_timeout`, `llm_deterministic_fallback` e `llm_refinement_accepted`. Validação de schema e aceitação final pelo serviço são estados diferentes. Para previsões, `forecast_history_batch` mede tempo decorrido do lote, `forecast_history` soma durações dos downloads e `forecast_calculations` mede cálculos. `forecast_history_failed` conta falhas, inclusive históricos vazios.

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_forecast_batch.py --baseline-ref dc6fbe4b0f32a2345b880b289a709f8183d933ee
# Acrescentar --live somente quando o Yahoo estiver disponível.
.\.venv\Scripts\python.exe scripts/benchmark_refinement.py --baseline-ref dc6fbe4b0f32a2345b880b289a709f8183d933ee --repeats 2
# --resume reaproveita amostras já gravadas da mesma revisão/modelo.
```

O executor mantém quatro workers por processo por padrão; `OPERUM_ANALYSIS_IO_WORKERS=1` permite comparação sequencial. Não há nova dependência, migração, mudança de interface ou cache entre requisições. Em uso real, acompanhar aceitação e falhas junto com mediana/P95, sem interpretar respostas inválidas mais rápidas como melhora de qualidade.

## Funcionamento

As análises continuam retornando uma única resposta. Cada requisição reutiliza seus próprios históricos, catálogo de ativos, acervo de notícias, textos normalizados e consultas semânticas idênticas. Não há cache de respostas finais entre requisições. A carteira coleta fontes sem executar análises completas de ativos.

Os históricos independentes da carteira são consultados em um executor compartilhado pela API. Na análise individual, a seleção de notícias pode ocorrer enquanto o histórico é carregado. As fórmulas, o ranking e os limites de fontes permanecem os mesmos. Históricos do serviço de mercado e dados Yahoo usados pelo forecast permanecem separados para preservar fonte, colunas e período.

O frontend solicita somente o horizonte selecionado. Gerar novamente ou reabrir a análise individual consulta o backend; respostas atrasadas não substituem a seleção atual.

## Modelos e worker

Prever não executa treinamento. A API procura modelos em memória e no disco, detecta novos artefatos sem reiniciar e enfileira os ausentes. Na análise individual, horizontes disponíveis usam os modelos existentes; os demais usam a estimativa determinística já existente, com confiança numérica 0,25, quando há dados suficientes. A confiança geral da análise continua sendo uma medida separada.

O worker processa `forecast_training` separadamente do treinamento mensal versionado. Confere novamente os horizontes 1, 5, 21, 42 e 63 dias e treina somente os ausentes ou inválidos. Tarefas têm deduplicação por ticker/dia e até três tentativas. Falhas parciais não são declaradas concluídas. Após falha definitiva, uma solicitação no dia seguinte pode criar outra tarefa.

API e worker devem usar a mesma máquina e os mesmos diretórios persistentes. Há um único worker por diretório de dados; ele recupera tarefas interrompidas na inicialização. A fila local usa bloqueio entre processos; no Postgres, permanecem as transações existentes. Os artefatos `.pkl` e seus metadados continuam sendo publicados, acompanhados por `.pkl.bundle`, fonte de leitura atômica do par modelo/metadados. Não copie apenas parte desses artefatos ao transferir modelos.

Configurações:

| Variável | Padrão | Uso |
|---|---|---|
| `OPERUM_ANALYSIS_IO_WORKERS` | `4` | Consultas simultâneas por processo da API; aceita de 1 a 16. Usar 1 permite comparar execução sequencial. |
| `OPERUM_FORECAST_TRAIN_THREADS` | `2` | Threads do XGBoost no treinamento do forecast, para limitar disputa de CPU. |
| `OPERUM_DATA_DIR` | `data/` do projeto | Dados e fila local compartilhados. |
| `OPERUM_MODELS_DIR` | `<OPERUM_DATA_DIR>/models` | Diretório compartilhado dos modelos de forecast; quando não há configuração, preserva `data/models`. |

`./iniciar.ps1` inicia também o worker, com logs `worker-start.log` e `worker-start.err.log`. `./iniciar.ps1 -Stop` encerra os serviços locais do Operum; o Ollama permanece disponível. No servidor, supervisionar separadamente `uvicorn app.main:app` e `python -m app.workers.analysis_worker`, com as mesmas variáveis e diretórios. Para separar máquinas futuramente, será necessário compartilhar ou sincronizar os artefatos. O limite de consultas é por processo: múltiplos processos da API multiplicam o limite total.

## Campo adicional da API

As respostas de análise de carteira e ativo podem incluir:

```json
{
  "forecast_availability": {
    "status": "partial",
    "items": [
      {"ticker": "PETR4", "missing_horizons": [21, 42, 63], "preparation": "pending"}
    ]
  }
}
```

`status` é `ready`, `partial` ou `unavailable` e descreve a cobertura dos modelos solicitados naquela análise. `items` lista os tickers com horizontes ausentes. `preparation` é `pending`, `running`, `failed` ou `not_scheduled`. Falha ao enfileirar não impede a resposta e não é apresentada como treinamento em andamento. Sem modelos nem dados suficientes, não se fabricam previsões. Carteiras de exemplo mantêm seu comportamento anterior e podem omitir o campo.

Não há polling: o usuário solicita uma nova análise para obter os modelos preparados. A análise continua aguardando o refinamento de texto pelo LLM quando habilitado. Streaming e preparação periódica adicional de dados estão fora desta etapa.

## Validação e medição

O log `analysis_timing` informa operação, duração total, durações acumuladas por etapa e contagens, sem registrar prompts ou dados de carteira. Como etapas podem sobrepor-se, a soma de suas durações pode exceder o tempo total. Os contadores incluem carregamentos, reaproveitamentos de entradas, preparação de features e chamadas ao LLM.

Para reproduzir a comparação com o código anterior:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_analysis.py --baseline-ref 1e4ac3a703bcd81a0ed62f1278ef3c4bbb08283f --repeats 5 --output docs/analysis-performance.json
```

O script usa dados e relógio fixos, chamadas de mercado simuladas e um LLM simulado que retorna ao texto determinístico. Não mede tempo de treinamento real nem inferência do provedor. Verifica igualdade das respostas completas, exceto o novo campo de disponibilidade, em 12 cenários e em outras 19 combinações de horizontes. Apresenta mediana e percentil 95, separando a espera simulada pelo LLM. O relatório [analysis-performance.json](analysis-performance.json) contém os resultados medidos; os números não são uma promessa de latência em produção.

Testes:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/api-client.test.mjs tests/dashboard-overview.test.mjs tests/analysis-ui.test.mjs
npm run build
```

O teste da interface usa Chromium do Playwright, servidor Vite temporário e API interceptada, sem criar contas ou acessar dados reais. Na implantação, começar com concorrência 1, comparar logs e ativar 4 após verificar latência, erros dos provedores, uso de CPU e fila do worker. Aumentar o limite não é uma solução para lentidão do LLM ou treinamento.

### Resultado controlado registrado em 14/09/2026

Cinco amostras por cen?rio, em milissegundos, com dados de mercado e LLM simulados. N?o representa o tempo esperado em produ??o.

| Cen?rio com dados dispon?veis | Mediana antes | Mediana depois | P95 antes | P95 depois |
|---|---:|---:|---:|---:|
| Ativo individual | 91.71 | 50.23 | 93.53 | 52.09 |
| Carteira: 5 ativos | 501.18 | 46.18 | 536.8 | 46.97 |
| Carteira: 10 ativos | 515.87 | 62.27 | 524.61 | 64.79 |
| Carteira: 20 ativos | 539.06 | 96.96 | 552.46 | 127.61 |

A mediana das dez consultas de lat?ncia uniforme caiu de 208.11 ms para 62.8 ms (69.82%). Na carteira de dez ativos, o cen?rio medido passou de 6 para 1 chamadas ao LLM simulado, de 107 para 11 consultas de hist?rico e de 6 para 1 carregamentos do acervo. O JSON inclui tamb?m os cen?rios de dados frios simulados e modelos indispon?veis.
