-- WealthBridge/Heirloom multi-tenancy: a Clerk Organization = a wealth
-- management firm. Families are a lighter-weight grouping *within* a firm
-- (Clerk doesn't nest orgs), so that layer lives here.
--
-- Tenant isolation is enforced by RLS comparing each row's firm_org_id to
-- the Clerk JWT's org_id claim (auth.jwt()->>'org_id'), set when a user
-- has an active organization in their Clerk session.

create table if not exists families (
  id uuid primary key default gen_random_uuid(),
  firm_org_id text not null,
  name text not null,
  created_by text not null, -- clerk_user_id of the wealth manager who created it
  created_at timestamptz not null default now()
);

alter table families enable row level security;

drop policy if exists "firm members see their firm's families" on families;
create policy "firm members see their firm's families"
on families
for select
to authenticated
using (firm_org_id = auth.jwt()->>'org_id');

drop policy if exists "wealth managers manage their firm's families" on families;
create policy "wealth managers manage their firm's families"
on families
for all
to authenticated
using (
  firm_org_id = auth.jwt()->>'org_id'
  and auth.jwt()->>'org_role' = 'org:admin'
)
with check (
  firm_org_id = auth.jwt()->>'org_id'
  and auth.jwt()->>'org_role' = 'org:admin'
);

grant select, insert, update, delete on families to authenticated;

-- Tie each user_roles row to the firm (org) and, for parents/heirs, the
-- family within it. Nullable: a role can be chosen before a user has
-- joined or created an organization.
alter table user_roles add column if not exists firm_org_id text;
alter table user_roles add column if not exists family_id uuid references families(id);

drop policy if exists "users manage their own role" on user_roles;
create policy "users manage their own role"
on user_roles
for all
to authenticated
using (clerk_user_id = auth.jwt()->>'sub')
with check (clerk_user_id = auth.jwt()->>'sub');
