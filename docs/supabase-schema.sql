create extension if not exists pgcrypto;
create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table if not exists public.app_users (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null unique,
  password_hash text not null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.auth_sessions (
  token text primary key,
  user_id uuid not null references public.app_users(id) on delete cascade,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_auth_sessions_user_id on public.auth_sessions(user_id);

create table if not exists public.user_preferences (
  user_id uuid primary key references public.app_users(id) on delete cascade,
  topics jsonb not null default '[]'::jsonb,
  compact_mode boolean not null default false,
  notifications boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.portfolios (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.app_users(id) on delete cascade,
  name text not null,
  base_currency text not null default 'BRL',
  risk_profile text not null default 'moderado',
  forecast_horizon_days integer not null default 5,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_portfolios_owner_id on public.portfolios(owner_id);

create table if not exists public.portfolio_positions (
  id uuid primary key default gen_random_uuid(),
  portfolio_id uuid not null references public.portfolios(id) on delete cascade,
  asset_id text not null,
  ticker text not null,
  asset_class text not null,
  quantity numeric(20, 8) not null check (quantity > 0),
  avg_price numeric(20, 8),
  currency text not null default 'BRL',
  manual_notes text not null default '',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (portfolio_id, ticker)
);

create index if not exists idx_portfolio_positions_portfolio_id on public.portfolio_positions(portfolio_id);
create index if not exists idx_portfolio_positions_ticker on public.portfolio_positions(ticker);

create table if not exists public.portfolio_transactions (
  id uuid primary key default gen_random_uuid(),
  portfolio_id uuid not null references public.portfolios(id) on delete cascade,
  ticker text not null,
  asset_class text not null,
  kind text not null check (kind in ('opening', 'buy', 'close')),
  quantity_delta numeric(20, 8) not null check (quantity_delta <> 0),
  unit_price numeric(20, 8),
  currency text not null default 'BRL',
  occurred_at date not null,
  origin_key text unique,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_portfolio_transactions_portfolio_date on public.portfolio_transactions(portfolio_id, occurred_at);
create index if not exists idx_portfolio_transactions_ticker on public.portfolio_transactions(portfolio_id, ticker);

create table if not exists public.processed_news (
  id text primary key,
  title text not null,
  summary text not null default '',
  content_excerpt text not null default '',
  source_id text not null default 'unknown',
  source_name text not null,
  source_type text not null default 'rss',
  source_category text,
  source_url text not null,
  is_official boolean not null default false,
  published_at timestamptz not null,
  language text not null default 'pt',
  tags text[] not null default '{}',
  mentioned_assets text[] not null default '{}',
  mentioned_sectors text[] not null default '{}',
  mentioned_countries text[] not null default '{}',
  event_tags text[] not null default '{}',
  sentiment_score real not null default 0,
  relevance_score real not null default 0,
  impact_score real not null default 0,
  raw_storage_path text,
  embedding extensions.vector(384) not null,
  embedding_model text not null,
  embedding_content_hash text not null,
  embedded_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  search_document tsvector not null default ''::tsvector
);

create table if not exists public.knowledge_documents (
  id text primary key,
  slug text not null unique,
  title text not null,
  category text not null,
  aliases text[] not null default '{}',
  short_answer text not null,
  content text not null,
  sources jsonb not null default '[]'::jsonb,
  version integer not null default 1,
  reviewed_at date not null,
  time_sensitive boolean not null default false,
  status text not null default 'published' check (status in ('draft', 'published')),
  content_hash text not null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.knowledge_chunks (
  id text primary key,
  document_id text not null references public.knowledge_documents(id) on delete cascade,
  chunk_index integer not null default 0,
  content text not null,
  embedding extensions.vector(384) not null,
  embedding_model text not null,
  embedding_content_hash text not null,
  search_document tsvector not null default ''::tsvector,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (document_id, chunk_index)
);

create table if not exists public.chat_conversations (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.app_users(id) on delete cascade,
  title text not null default 'Nova conversa',
  summary text not null default '',
  portfolio_id uuid references public.portfolios(id) on delete set null,
  use_all_portfolios boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.chat_conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  mode text,
  sources jsonb not null default '[]'::jsonb,
  retrieval jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_processed_news_published_at on public.processed_news(published_at desc);
create index if not exists idx_processed_news_source_id on public.processed_news(source_id);
create index if not exists idx_processed_news_assets on public.processed_news using gin(mentioned_assets);
create index if not exists idx_processed_news_sectors on public.processed_news using gin(mentioned_sectors);
create index if not exists idx_processed_news_countries on public.processed_news using gin(mentioned_countries);
create index if not exists idx_processed_news_events on public.processed_news using gin(event_tags);
create index if not exists idx_processed_news_search on public.processed_news using gin(search_document);
create index if not exists idx_processed_news_embedding
on public.processed_news using hnsw (embedding extensions.vector_cosine_ops);
create index if not exists idx_knowledge_documents_category on public.knowledge_documents(category);
create index if not exists idx_knowledge_documents_aliases on public.knowledge_documents using gin(aliases);
create index if not exists idx_knowledge_chunks_search on public.knowledge_chunks using gin(search_document);
create index if not exists idx_knowledge_chunks_embedding
on public.knowledge_chunks using hnsw (embedding extensions.vector_cosine_ops);
create index if not exists idx_chat_conversations_owner_updated
on public.chat_conversations(owner_id, updated_at desc);
create index if not exists idx_chat_messages_conversation_created
on public.chat_messages(conversation_id, created_at asc);

create or replace function public.set_processed_news_search_document()
returns trigger
language plpgsql
as $$
begin
  new.search_document = to_tsvector(
    'portuguese',
    coalesce(new.title, '') || ' ' ||
    coalesce(new.summary, '') || ' ' ||
    coalesce(new.content_excerpt, '') || ' ' ||
    coalesce(array_to_string(new.mentioned_assets, ' '), '') || ' ' ||
    coalesce(array_to_string(new.mentioned_sectors, ' '), '') || ' ' ||
    coalesce(array_to_string(new.event_tags, ' '), '')
  );
  return new;
end;
$$;

create or replace function public.set_knowledge_search_document()
returns trigger
language plpgsql
as $$
begin
  new.search_document = to_tsvector('portuguese', coalesce(new.content, ''));
  return new;
end;
$$;

alter table public.app_users enable row level security;
alter table public.auth_sessions enable row level security;
alter table public.user_preferences enable row level security;
alter table public.portfolios enable row level security;
alter table public.portfolio_positions enable row level security;
alter table public.portfolio_transactions enable row level security;
alter table public.processed_news enable row level security;
alter table public.knowledge_documents enable row level security;
alter table public.knowledge_chunks enable row level security;
alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;

-- Auth propria do Operum passa somente pelo backend Python usando SQL direto.
-- Enquanto nao houver Supabase Auth, nao criar policies publicas para anon/authenticated.

drop trigger if exists trg_app_users_updated_at on public.app_users;
create trigger trg_app_users_updated_at
before update on public.app_users
for each row
execute function public.set_updated_at();

drop trigger if exists trg_user_preferences_updated_at on public.user_preferences;
create trigger trg_user_preferences_updated_at
before update on public.user_preferences
for each row
execute function public.set_updated_at();

drop trigger if exists trg_portfolios_updated_at on public.portfolios;
create trigger trg_portfolios_updated_at
before update on public.portfolios
for each row
execute function public.set_updated_at();

drop trigger if exists trg_portfolio_positions_updated_at on public.portfolio_positions;
create trigger trg_portfolio_positions_updated_at
before update on public.portfolio_positions
for each row
execute function public.set_updated_at();

drop trigger if exists trg_processed_news_updated_at on public.processed_news;
create trigger trg_processed_news_updated_at
before update on public.processed_news
for each row
execute function public.set_updated_at();

drop trigger if exists trg_processed_news_search_document on public.processed_news;
create trigger trg_processed_news_search_document
before insert or update of title, summary, content_excerpt, mentioned_assets, mentioned_sectors, event_tags
on public.processed_news
for each row
execute function public.set_processed_news_search_document();

drop trigger if exists trg_knowledge_documents_updated_at on public.knowledge_documents;
create trigger trg_knowledge_documents_updated_at before update on public.knowledge_documents
for each row execute function public.set_updated_at();

drop trigger if exists trg_knowledge_chunks_updated_at on public.knowledge_chunks;
create trigger trg_knowledge_chunks_updated_at before update on public.knowledge_chunks
for each row execute function public.set_updated_at();

drop trigger if exists trg_knowledge_chunks_search_document on public.knowledge_chunks;
create trigger trg_knowledge_chunks_search_document
before insert or update of content on public.knowledge_chunks
for each row execute function public.set_knowledge_search_document();

drop trigger if exists trg_chat_conversations_updated_at on public.chat_conversations;
create trigger trg_chat_conversations_updated_at before update on public.chat_conversations
for each row execute function public.set_updated_at();
