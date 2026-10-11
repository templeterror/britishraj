-- Heirloom: one role per Clerk user, chosen once at first sign-in.
do $$ begin
  create type user_role as enum ('parent', 'child', 'wealth_manager');
exception when duplicate_object then null;
end $$;

create table if not exists user_roles (
  id uuid primary key default gen_random_uuid(),
  clerk_user_id text not null unique,
  role user_role not null,
  created_at timestamptz not null default now()
);

alter table user_roles enable row level security;

drop policy if exists "users manage their own role" on user_roles;
create policy "users manage their own role"
on user_roles
for all
to authenticated
using (clerk_user_id = auth.jwt()->>'sub')
with check (clerk_user_id = auth.jwt()->>'sub');

grant select, insert, update, delete on user_roles to authenticated;
