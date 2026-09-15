# Esteira preditiva local

O Operum mantém a análise global de cada ativo em snapshots e calcula no clique somente o contexto da carteira. Os números vêm do XGBoost ou do baseline validado; notícias passam pelo scorer financeiro promovido e pela fusão limitada; o Qwen apenas reescreve o texto.

## Processos

Execute API, scheduler e worker separadamente:

```powershell
uvicorn app.main:app --reload
python -m app.jobs.predictive_scheduler
python -m app.workers.analysis_worker
```

O scheduler ingere notícias a cada 15 minutos, agrupa eventos por 10 minutos, agenda preços às 19h em dias úteis e treinamento no primeiro sábado do mês às 02h (America/Sao_Paulo). Jobs atrasados permanecem no banco e são retomados no reinício.

## Treinamento e promoção

```powershell
python -m app.ml.cli dataset build --since 2019-01-01 --universe top30-b3
python -m app.ml.cli nlp benchmark --dataset current-ptbr
python -m app.ml.cli train --dataset latest --stage shadow
python -m app.ml.cli replay --model latest-shadow
python -m app.ml.cli snapshots generate --model latest-shadow
python -m app.ml.cli promote --model latest-shadow --require-gates
```

`promote` é transacional: todos os horizontes/classes passam ou nenhum é ativado. Um horizonte sem modelo aprovado usa o baseline e continua retornando análise completa com confiança baixa e faixa mais ampla.

O benchmark NLP cria `data/nlp/current-ptbr.json` com 300 notícias estratificadas quando a referência não existe. Os rótulos sugeridos não são aceitos automaticamente: preencha `label` e altere `review_status` para `reviewed`. Somente um modelo offline, com licença e checksum auditados, macro-F1 pelo menos 5 pontos acima do baseline, pode ser selecionado.

Dados macro opcionais devem ser fornecidos em `data/macro/releases.parquet`, com `available_at`, `selic` e/ou `ipca_12m`. `available_at` precisa representar a divulgação real; sem esse arquivo auditado, macro não entra no dataset e a ausência fica registrada no manifesto.

## Artefatos locais

- `data/datasets/predictive/<hash>/`: Parquets, manifesto e relatório de qualidade.
- `data/models/predictive/<uuid>/`: modelo e metadados shadow.
- `data/ai/predictive/`: versões, snapshots, jobs, replay e resultados realizados no modo local.
- Supabase: as mesmas entidades persistentes quando `OPERUM_STORAGE_MODE=auto` e `SUPABASE_DB_URL` está configurada.

Nunca edite ou promova manualmente um artefato para contornar gates. O último snapshot ativo permanece disponível em falhas, e a LLM não participa dos cálculos.
