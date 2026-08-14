# Supabase Setup - Operum

Este passo prepara o banco do Operum no Supabase sem expor credenciais sensiveis no repositorio.

## 1. Variaveis de ambiente

Crie um arquivo `.env` na raiz de `Operum/` com base em `.env.example`.

Preencha:

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_fe0x4TA9YAhHOwioe7mV6A_o12d8HM6
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_fe0x4TA9YAhHOwioe7mV6A_o12d8HM6
SUPABASE_SECRET_KEY=COLE_AQUI_A_SUPABASE_SECRET_KEY
SUPABASE_DB_URL=postgresql://postgres:COLE_AQUI_A_SENHA_DO_BANCO@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
SUPABASE_DB_SCHEMA=public
```

O valor de `SUPABASE_SECRET_KEY` deve ficar apenas no `.env` local ou em variavel secreta do provedor de deploy.
O valor de `SUPABASE_DB_URL` deve usar a string de conexao Postgres do Supabase para que o backend Python use SQL direto.
O backend agora carrega automaticamente o arquivo `.env` local em desenvolvimento. Em producao, prefira variaveis de ambiente do provedor de deploy.

`SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` nao bastam para a autenticacao atual. Como o Operum ainda usa auth propria no backend, o backend precisa obrigatoriamente de `SUPABASE_DB_URL` para criar usuarios, validar senha e persistir sessoes no Postgres.

## 2. Criar o schema inicial

No painel do Supabase:

1. Abra `SQL Editor`
2. Crie uma nova query
3. Cole o conteudo de `docs/supabase-schema.sql`
4. Execute

Ao atualizar uma instalação existente com posições já cadastradas, execute também:

```bash
python scripts/migrate_portfolio_transactions.py
```

O script é idempotente e cria um saldo inicial na data da migração sem duplicar movimentações existentes.

## 3. Escopo do schema inicial

Este schema cobre o MVP descrito no PRD:

- usuarios da aplicacao
- sessoes autenticadas do backend atual
- preferencias do usuario
- carteiras
- posicoes da carteira

Ele nao migra ainda:

- noticias historicas
- cache de analises
- modelos treinados
- logs locais

Esses blocos podem entrar na segunda etapa da migracao.

## 4. Observacao importante

O projeto hoje usa autenticacao propria no backend. Entao, neste primeiro passo, o Supabase sera usado como banco PostgreSQL do projeto, e nao como substituicao imediata do Supabase Auth.

As tabelas criticas devem manter `row level security` ativo e sem policies publicas para `anon`/`authenticated` enquanto a auth propria estiver no backend. O frontend nao deve acessar essas tabelas diretamente via chave publishable.

## 5. Verificacao de auth no Supabase

Depois de criar as tabelas e configurar `SUPABASE_DB_URL`, rode:

```bash
python scripts/verify_supabase_auth.py
```

O script cria um usuario temporario via API, valida `app_users`, `auth_sessions`, `/api/auth/me`, login correto/incorreto, logout, RLS das tabelas criticas e remove apenas o usuario de teste criado.

## 6. Migracao dos dados locais

Depois de criar as tabelas e configurar `SUPABASE_DB_URL`, rode:

```bash
python scripts/migrate_local_to_supabase.py
```

Isso importa:

- usuarios locais
- sessoes locais
- preferencias locais
- carteiras locais
- posicoes locais

## 7. Seguranca de deploy

Consulte tambem:

- `docs/deployment-security.md`

Resumo:

- nao commitar `.env`
- usar apenas placeholders em arquivos versionados
- colocar variaveis `VITE_*` no Vercel apenas para o frontend
- colocar `SUPABASE_SECRET_KEY` e `SUPABASE_DB_URL` somente no host do backend
