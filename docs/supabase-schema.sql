create extension if not exists pgcrypto;

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

alter table public.app_users enable row level security;
alter table public.auth_sessions enable row level security;
alter table public.user_preferences enable row level security;
alter table public.portfolios enable row level security;
alter table public.portfolio_positions enable row level security;

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
