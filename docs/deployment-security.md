# Deployment Security - Operum

Este documento define como tratar segredos do projeto no GitHub, Vercel e no host do backend Python.

## 1. Regra principal

Segredos nunca devem ser commitados no repositório.

Isso inclui:

- `SUPABASE_SECRET_KEY`
- `SUPABASE_DB_URL`
- senhas de banco
- tokens privados
- chaves de terceiros

Arquivos permitidos no Git:

- `.env.example`
- documentacao com placeholders

Arquivos proibidos no Git:

- `.env`
- `.env.production`
- qualquer arquivo com segredo real

## 2. GitHub

No GitHub:

- manter `.env` fora do versionamento
- usar apenas placeholders em `.env.example`
- se houver CI futuro, salvar segredos em `GitHub Actions Secrets`

Checklist antes de push:

- confirmar que `.env` nao esta staged
- confirmar que nenhuma chave real entrou em `README`, `docs` ou `scripts`
- se uma chave foi exposta, rotacionar imediatamente no provedor

## 3. Vercel

O Vercel deve receber apenas variaveis do frontend:

- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`

Nao colocar no Vercel, se ele hospedar apenas o frontend:

- `SUPABASE_SECRET_KEY`
- `SUPABASE_DB_URL`

Essas variaveis pertencem ao backend Python, nao ao frontend.
O frontend deve continuar chamando apenas a API do backend para auth; ele nao cria usuario nem valida senha diretamente no Supabase.

## 4. Host do backend

O host do backend Python deve receber:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_DB_URL`
- `SUPABASE_DB_SCHEMA`
- `CORS_ORIGINS`
- `OPERUM_ENV`
- `OPERUM_RATE_LIMIT_ENABLED`
- `REDIS_URL`
- `OPERUM_REFRESH_TOKEN`
- `OPERUM_ENABLE_NEWS_INGEST_ON_STARTUP`
- `OPERUM_ENABLE_NEWS_BACKFILL_ON_STARTUP`
- `OPERUM_ENABLE_PRICE_WARMUP_ON_STARTUP`
- `OPERUM_SEED_DEMO_USER`

Recomendacao para producao:

- `OPERUM_ENABLE_NEWS_INGEST_ON_STARTUP=false`
- `OPERUM_ENABLE_NEWS_BACKFILL_ON_STARTUP=false`
- `OPERUM_ENABLE_PRICE_WARMUP_ON_STARTUP=false`
- `OPERUM_SEED_DEMO_USER=false`
- `OPERUM_ENV=production`
- `OPERUM_RATE_LIMIT_ENABLED=true`
- `OPERUM_COOKIE_SECURE=true`
- `REDIS_URL` configurada para Redis/Upstash
- `CORS_ORIGINS` contendo apenas o dominio real do frontend

Auth em producao:

- a autenticacao continua propria no backend Python
- sessoes devem trafegar via cookie `operum_session` com `HttpOnly`, `Secure` e `SameSite=Lax`
- o backend precisa de `SUPABASE_DB_URL` para persistir `app_users`, `auth_sessions` e `user_preferences`
- manter RLS ativo em `app_users`, `auth_sessions`, `user_preferences`, `portfolios` e `portfolio_positions`
- nao criar policies publicas permissivas nessas tabelas enquanto o frontend nao usar Supabase Auth

Rate limit em producao:

- `REDIS_URL` e obrigatoria quando `OPERUM_RATE_LIMIT_ENABLED=true`
- login, cadastro, chat/IA e endpoints administrativos sao limitados pela API
- WAF/bot protection gerenciado ainda deve ser adicionado na borda quando o dominio estiver pronto

Checks antes do deploy:

- `python -m pytest`
- `npm run build`
- `npm audit --audit-level=low`
- `python -m pip_audit -r requirements.txt`
- `python scripts/secure_supabase_rls.py`

## 5. Rotacao de segredos

Rotacione imediatamente uma chave se:

- ela apareceu em commit
- ela apareceu em screenshot
- ela apareceu em chat compartilhado
- ela foi colocada em documentacao publica

Depois da rotacao:

- atualizar o segredo apenas no provedor de deploy
- nao atualizar com valor real em arquivos versionados

## 6. Banco e URI

Se a senha do banco tiver caracteres especiais, a senha dentro de `SUPABASE_DB_URL` pode precisar de URL encoding.

Exemplo:

- `!` pode virar `%21`
- `@` pode virar `%40`
- `#` pode virar `%23`

Se a conexao falhar mesmo com os dados corretos, esse deve ser o primeiro ponto a revisar.
