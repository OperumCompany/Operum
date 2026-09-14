# Performance das análises

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
