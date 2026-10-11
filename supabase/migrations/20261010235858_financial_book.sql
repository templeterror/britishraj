create table public.families (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  display_name text not null,
  is_demo boolean not null default false,
  plaid_item_id text,
  created_at timestamptz not null default now()
);

create table public.people (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families (id) on delete cascade,
  role text not null check (role in ('parent', 'heir')),
  given_name text not null,
  family_name text not null,
  unique (family_id, role)
);

create table public.goals (
  id uuid primary key default gen_random_uuid(),
  person_id uuid not null references public.people (id) on delete cascade,
  statement text not null
);

create table public.accounts (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families (id) on delete cascade,
  plaid_type text not null,
  plaid_subtype text not null,
  name text not null,
  official_name text,
  current_balance numeric(18, 2) not null,
  available_balance numeric(18, 2),
  currency text not null default 'USD',
  unique (family_id, name)
);

create table public.securities (
  id uuid primary key default gen_random_uuid(),
  ticker text not null unique,
  name text not null,
  currency text not null default 'USD'
);

create table public.holdings (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts (id) on delete cascade,
  security_id uuid not null references public.securities (id),
  quantity numeric(20, 4) not null,
  institution_price numeric(18, 4) not null,
  institution_price_as_of date not null,
  cost_basis numeric(18, 2) not null,
  currency text not null default 'USD'
);

create table public.investment_transactions (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts (id) on delete cascade,
  security_id uuid not null references public.securities (id),
  posted_on date not null,
  name text not null,
  quantity numeric(20, 4) not null,
  price numeric(18, 4) not null,
  fees numeric(18, 2) not null default 0,
  txn_type text not null,
  currency text not null default 'USD'
);

create table public.cash_transactions (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts (id) on delete cascade,
  date_transacted date not null,
  date_posted date not null,
  amount numeric(18, 2) not null,
  description text not null,
  currency text not null default 'USD'
);

create table public.identities (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null unique references public.accounts (id) on delete cascade,
  holder_name text not null,
  street text not null,
  city text not null,
  region text not null,
  postal_code text not null,
  country text not null default 'US'
);

create index people_family_id_idx on public.people (family_id);
create index goals_person_id_idx on public.goals (person_id);
create index accounts_family_id_idx on public.accounts (family_id);
create index holdings_account_id_idx on public.holdings (account_id);
create index holdings_security_id_idx on public.holdings (security_id);
create index investment_transactions_account_id_idx on public.investment_transactions (account_id);
create index investment_transactions_security_id_idx on public.investment_transactions (security_id);
create index cash_transactions_account_id_idx on public.cash_transactions (account_id);

alter table public.families enable row level security;
alter table public.people enable row level security;
alter table public.goals enable row level security;
alter table public.accounts enable row level security;
alter table public.securities enable row level security;
alter table public.holdings enable row level security;
alter table public.investment_transactions enable row level security;
alter table public.cash_transactions enable row level security;
alter table public.identities enable row level security;

revoke all on table public.families from anon, authenticated;
revoke all on table public.people from anon, authenticated;
revoke all on table public.goals from anon, authenticated;
revoke all on table public.accounts from anon, authenticated;
revoke all on table public.securities from anon, authenticated;
revoke all on table public.holdings from anon, authenticated;
revoke all on table public.investment_transactions from anon, authenticated;
revoke all on table public.cash_transactions from anon, authenticated;
revoke all on table public.identities from anon, authenticated;

grant select, insert, update, delete on table public.families to service_role;
grant select, insert, update, delete on table public.people to service_role;
grant select, insert, update, delete on table public.goals to service_role;
grant select, insert, update, delete on table public.accounts to service_role;
grant select, insert, update, delete on table public.securities to service_role;
grant select, insert, update, delete on table public.holdings to service_role;
grant select, insert, update, delete on table public.investment_transactions to service_role;
grant select, insert, update, delete on table public.cash_transactions to service_role;
grant select, insert, update, delete on table public.identities to service_role;
