-- =====================================================================
-- Heirloom · 01_schema.sql
-- Run once in a fresh Supabase project: SQL Editor -> paste -> Run.
-- Then run 02_seed.sql. Run 03_demo_mode.sql only if the demo has no login.
--
-- What this gives you
--   Tables : firms, advisors, households, clients, heirs, accounts,
--            beneficiary_designations, interactions, documents,
--            retention_assumptions
--   Views  : heir_priority            <- the ranked "who to meet first" list
--            heir_relationship        <- do we know this heir? (derived)
--            household_summary        <- one row per household
--            book_summary             <- one row per advisor
--            account_beneficiary_gaps <- accounts where the paperwork has holes
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Tables
-- ---------------------------------------------------------------------

create table public.firms (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  created_at timestamptz not null default now()
);

create table public.advisors (
  id         uuid primary key default gen_random_uuid(),
  firm_id    uuid not null references public.firms (id) on delete cascade,
  clerk_user_id text unique, -- Clerk user ID (looks like user_2abc...), set when the advisor first signs in
  full_name  text not null,
  email      text,
  created_at timestamptz not null default now()
);

create table public.households (
  id         uuid primary key default gen_random_uuid(),
  firm_id    uuid not null references public.firms (id) on delete cascade,
  advisor_id uuid references public.advisors (id) on delete set null,
  name       text not null,
  notes      text,
  created_at timestamptz not null default now()
);

-- Current clients: the benefactors whose money will move.
create table public.clients (
  id           uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households (id) on delete cascade,
  full_name    text not null,
  birth_date   date,
  created_at   timestamptz not null default now()
);

-- The people who inherit. One row per heir per household.
create table public.heirs (
  id              uuid primary key default gen_random_uuid(),
  household_id    uuid not null references public.households (id) on delete cascade,
  full_name       text not null,
  relationship    text not null default 'child'
                  check (relationship in ('spouse','child','grandchild','sibling','other_family','charity','other')),
  birth_date      date,
  email           text,
  phone           text,
  city            text,
  is_client       boolean not null default false, -- already has an account with the firm
  has_own_advisor boolean,                        -- null = unknown
  notes           text,
  created_at      timestamptz not null default now()
);

create table public.accounts (
  id              uuid primary key default gen_random_uuid(),
  household_id    uuid not null references public.households (id) on delete cascade,
  owner_client_id uuid references public.clients (id) on delete set null, -- null = joint / trust
  name            text not null,
  account_type    text not null default 'brokerage'
                  check (account_type in ('brokerage','ira','roth_ira','401k','trust','annuity','529','other')),
  custodian       text,
  balance         numeric(16,2) not null default 0 check (balance >= 0),
  created_at      timestamptz not null default now()
);

-- Uploaded estate summaries, beneficiary forms, trust documents.
-- Files live in Supabase Storage; `extracted` holds what the AI pulled out.
create table public.documents (
  id           uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households (id) on delete cascade,
  doc_type     text not null default 'other'
               check (doc_type in ('beneficiary_form','trust','will','estate_summary','crm_export','meeting_notes','other')),
  file_name    text,
  storage_path text,
  status       text not null default 'uploaded'
               check (status in ('uploaded','processing','extracted','failed')),
  extracted    jsonb,
  created_at   timestamptz not null default now()
);

-- Who gets what share of which account, and where we learned it.
-- The beneficiary is EITHER an heir OR another client in the household
-- (the usual pattern: spouse is primary, children are contingent).
create table public.beneficiary_designations (
  id                 uuid primary key default gen_random_uuid(),
  account_id         uuid not null references public.accounts (id) on delete cascade,
  heir_id            uuid references public.heirs (id) on delete cascade,
  client_id          uuid references public.clients (id) on delete cascade,
  designation        text not null default 'primary' check (designation in ('primary','contingent')),
  share_pct          numeric(5,2) not null check (share_pct > 0 and share_pct <= 100),
  source             text not null default 'custodian_form'
                     check (source in ('custodian_form','trust','will','estate_summary','crm_note','advisor_memory')),
  source_document_id uuid references public.documents (id) on delete set null,
  created_at         timestamptz not null default now(),
  constraint beneficiary_is_heir_or_client check (num_nonnulls(heir_id, client_id) = 1),
  unique (account_id, heir_id, designation),
  unique (account_id, client_id, designation)
);

-- Every touchpoint between the firm and an heir. This is the evidence
-- behind "do I actually know them?".
create table public.interactions (
  id          uuid primary key default gen_random_uuid(),
  heir_id     uuid not null references public.heirs (id) on delete cascade,
  advisor_id  uuid references public.advisors (id) on delete set null,
  kind        text not null check (kind in ('meeting','call','event','email','intro')),
  occurred_on date not null default current_date,
  notes       text,
  created_at  timestamptz not null default now()
);

-- Retention rate assumed for each relationship level. Editable, so the
-- model is transparent and a firm can tune it.
create table public.retention_assumptions (
  relationship_level text primary key
                     check (relationship_level in ('none','contacted','met','meaningful','client','spouse')),
  retention_rate     numeric(4,3) not null check (retention_rate between 0 and 1),
  is_sourced         boolean not null default false, -- true = published figure, false = placeholder
  basis              text
);

insert into public.retention_assumptions (relationship_level, retention_rate, is_sourced, basis) values
  ('none',       0.200, true,  'Heirs who already inherited: 20% kept the benefactor''s advisor (Cerulli, via CNBC)'),
  ('contacted',  0.300, false, 'PLACEHOLDER: interpolated between "none" and "met"'),
  ('met',        0.450, false, 'PLACEHOLDER: anchored to next-gen heirs, 45% plan to stay (Natixis); not a like-for-like sample'),
  ('meaningful', 0.640, true,  'Heirs with a meaningful advisor relationship before transfer: 64% stay (T. Rowe Price)'),
  ('client',     0.900, false, 'PLACEHOLDER: heir already holds an account with the firm'),
  ('spouse',     0.720, true,  'Surviving spouse: about 72% stay (Natixis 2026, via Amplified Advisors)');


-- ---------------------------------------------------------------------
-- 2. Indexes on foreign keys
-- ---------------------------------------------------------------------

create index advisors_firm_idx         on public.advisors (firm_id);
create index households_firm_idx       on public.households (firm_id);
create index households_advisor_idx    on public.households (advisor_id);
create index clients_household_idx     on public.clients (household_id);
create index heirs_household_idx       on public.heirs (household_id);
create index accounts_household_idx    on public.accounts (household_id);
create index documents_household_idx   on public.documents (household_id);
create index designations_account_idx  on public.beneficiary_designations (account_id);
create index designations_heir_idx     on public.beneficiary_designations (heir_id);
create index designations_client_idx   on public.beneficiary_designations (client_id);
create index interactions_heir_idx     on public.interactions (heir_id, occurred_on desc);


-- ---------------------------------------------------------------------
-- 3. Views
--    security_invoker = true makes the views respect the caller's RLS.
-- ---------------------------------------------------------------------

-- Relationship level is DERIVED from logged interactions, never typed in.
--   client      heir already has an account with the firm
--   spouse      surviving spouse
--   meaningful  2+ live contacts (meeting / call / event) in the last 24 months
--   met         at least 1 live contact in the last 36 months
--   contacted   only emails / introductions, or a live contact older than 36 months
--   none        nothing on record
create view public.heir_relationship
with (security_invoker = true) as
select
  h.id as heir_id,
  count(i.id)::int                                                   as interactions_total,
  (count(i.id) filter (where i.kind in ('meeting','call','event')))::int as live_contacts_total,
  (count(i.id) filter (where i.kind in ('meeting','call','event')
                         and i.occurred_on >= current_date - interval '24 months'))::int as live_contacts_24m,
  max(i.occurred_on)                                                 as last_contact_on,
  case
    when h.is_client then 'client'
    when h.relationship = 'spouse' then 'spouse'
    when count(i.id) filter (where i.kind in ('meeting','call','event')
                               and i.occurred_on >= current_date - interval '24 months') >= 2 then 'meaningful'
    when count(i.id) filter (where i.kind in ('meeting','call','event')
                               and i.occurred_on >= current_date - interval '36 months') >= 1 then 'met'
    when count(i.id) >= 1 then 'contacted'
    else 'none'
  end as relationship_level
from public.heirs h
left join public.interactions i on i.heir_id = h.id
group by h.id;

-- Rough timing. Money reaches the next generation when the LAST client in
-- the household dies, so we use the youngest client and a flat planning
-- age of 90. This is a ranking heuristic, not an actuarial estimate.
create view public.household_horizon
with (security_invoker = true) as
select
  hh.id as household_id,
  max(c.birth_date) as youngest_client_birth_date,
  greatest(1, 90 - extract(year from age(current_date, max(c.birth_date)))::int) as years_to_transfer
from public.households hh
left join public.clients c on c.household_id = hh.id
group by hh.id;

-- What each heir eventually receives from each account.
--   eventual share = their primary share
--                  + their contingent share x (the part whose primary is a client spouse)
-- Example: Dad's IRA is 100% to Mom (a client), contingent 50/50 to the kids.
-- Each child's eventual share is 50%. Assumes the spouse keeps the designations.
create view public.heir_account_shares
with (security_invoker = true) as
select
  bd.account_id,
  bd.heir_id,
  sum(case when bd.designation = 'primary' then bd.share_pct
           else bd.share_pct * coalesce(sp.spouse_primary_pct, 0) / 100 end) as eventual_share_pct
from public.beneficiary_designations bd
left join (
  select account_id, sum(share_pct) as spouse_primary_pct
  from public.beneficiary_designations
  where designation = 'primary' and client_id is not null
  group by account_id
) sp on sp.account_id = bd.account_id
where bd.heir_id is not null
group by bd.account_id, bd.heir_id;

-- THE MAIN VIEW: one row per heir, ready to sort by priority_score desc.
--   expected_inheritance = sum(account balance x eventual share)
--   dollars_at_risk      = expected_inheritance x (1 - retention_rate)
--   priority_score       = dollars_at_risk / years_to_transfer
--                          (annualized dollars at risk: big AND soon ranks first)
create view public.heir_priority
with (security_invoker = true) as
select
  h.id                                          as heir_id,
  h.full_name                                   as heir_name,
  h.relationship,
  extract(year from age(current_date, h.birth_date))::int as heir_age,
  h.city,
  h.email,
  h.phone,
  h.is_client,
  h.has_own_advisor,
  hh.id                                         as household_id,
  hh.name                                       as household_name,
  hh.firm_id,
  a.id                                          as advisor_id,
  a.full_name                                   as advisor_name,
  coalesce(e.expected_inheritance, 0)           as expected_inheritance,
  hz.years_to_transfer,
  r.relationship_level,
  r.interactions_total,
  r.live_contacts_24m,
  r.last_contact_on,
  ra.retention_rate,
  round(coalesce(e.expected_inheritance, 0) * (1 - ra.retention_rate), 2) as dollars_at_risk,
  round(coalesce(e.expected_inheritance, 0) * (1 - ra.retention_rate)
        / nullif(hz.years_to_transfer, 0), 2)   as priority_score
from public.heirs h
join public.households hh             on hh.id = h.household_id
left join public.advisors a           on a.id = hh.advisor_id
join public.heir_relationship r       on r.heir_id = h.id
join public.retention_assumptions ra  on ra.relationship_level = r.relationship_level
left join public.household_horizon hz on hz.household_id = hh.id
left join (
  select sh.heir_id, round(sum(acc.balance * sh.eventual_share_pct / 100), 2) as expected_inheritance
  from public.heir_account_shares sh
  join public.accounts acc on acc.id = sh.account_id
  group by sh.heir_id
) e on e.heir_id = h.id
where h.relationship <> 'charity'; -- charities are recorded but not ranked as future clients

-- Accounts where the paperwork does not fully say who inherits.
--   no_beneficiary_on_file      nothing recorded at all
--   primary_under_100 / over    primary shares don't add up to 100%
--   no_contingent_after_spouse  spouse is primary, nobody named after them
--   contingent_not_100          spouse is primary, contingent shares don't add up
create view public.account_beneficiary_gaps
with (security_invoker = true) as
select * from (
  select
    acc.id           as account_id,
    acc.household_id,
    hh.name          as household_name,
    acc.name         as account_name,
    acc.account_type,
    acc.balance,
    t.primary_total,
    t.contingent_total,
    round(acc.balance * greatest(0, 100 - t.next_gen_assigned) / 100, 2) as unassigned_balance,
    case
      when t.primary_rows = 0                                   then 'no_beneficiary_on_file'
      when t.primary_total < 100                                then 'primary_under_100'
      when t.primary_total > 100                                then 'primary_over_100'
      when t.spouse_primary > 0 and t.contingent_total = 0      then 'no_contingent_after_spouse'
      when t.spouse_primary > 0 and t.contingent_total <> 100   then 'contingent_not_100'
    end as gap
  from public.accounts acc
  join public.households hh on hh.id = acc.household_id
  cross join lateral (
    select
      count(*) filter (where bd.designation = 'primary')                                        as primary_rows,
      coalesce(sum(bd.share_pct) filter (where bd.designation = 'primary'), 0)                  as primary_total,
      coalesce(sum(bd.share_pct) filter (where bd.designation = 'primary'
                                           and bd.client_id is not null), 0)                    as spouse_primary,
      coalesce(sum(bd.share_pct) filter (where bd.designation = 'contingent'), 0)               as contingent_total,
      -- share of the account that is traceable to a named next-generation heir
      coalesce(sum(bd.share_pct) filter (where bd.designation = 'primary' and bd.heir_id is not null), 0)
        + coalesce(sum(bd.share_pct) filter (where bd.designation = 'contingent' and bd.heir_id is not null), 0)
          * coalesce(sum(bd.share_pct) filter (where bd.designation = 'primary' and bd.client_id is not null), 0) / 100
                                                                                                as next_gen_assigned
    from public.beneficiary_designations bd
    where bd.account_id = acc.id
  ) t
) g
where g.gap is not null;

-- One row per household.
create view public.household_summary
with (security_invoker = true) as
select
  hh.id   as household_id,
  hh.name as household_name,
  hh.firm_id,
  hh.advisor_id,
  a.full_name as advisor_name,
  coalesce(acct.total_aum, 0)      as total_aum,
  hz.years_to_transfer,
  coalesce(hp.heirs_total, 0)      as heirs_total,
  coalesce(hp.heirs_known, 0)      as heirs_known,      -- met, meaningful, client or spouse
  coalesce(hp.heirs_unknown, 0)    as heirs_unknown,    -- none or contacted only
  coalesce(hp.dollars_at_risk, 0)  as dollars_at_risk,
  coalesce(hp.priority_score, 0)   as priority_score,
  coalesce(gaps.unassigned_balance, 0) as unassigned_balance
from public.households hh
left join public.advisors a           on a.id = hh.advisor_id
left join public.household_horizon hz on hz.household_id = hh.id
left join (
  select household_id, sum(balance) as total_aum
  from public.accounts group by household_id
) acct on acct.household_id = hh.id
left join (
  select
    household_id,
    count(*)::int as heirs_total,
    (count(*) filter (where relationship_level in ('met','meaningful','client','spouse')))::int as heirs_known,
    (count(*) filter (where relationship_level in ('none','contacted')))::int as heirs_unknown,
    sum(dollars_at_risk) as dollars_at_risk,
    sum(priority_score)  as priority_score
  from public.heir_priority group by household_id
) hp on hp.household_id = hh.id
left join (
  select household_id, sum(unassigned_balance) as unassigned_balance
  from public.account_beneficiary_gaps group by household_id
) gaps on gaps.household_id = hh.id;

-- One row per advisor: the headline numbers for the top of the dashboard.
create view public.book_summary
with (security_invoker = true) as
select
  a.id        as advisor_id,
  a.full_name as advisor_name,
  a.firm_id,
  count(hs.household_id)::int                 as households,
  coalesce(sum(hs.total_aum), 0)              as total_aum,
  coalesce(sum(hs.dollars_at_risk), 0)        as dollars_at_risk,
  round(100 * coalesce(sum(hs.dollars_at_risk), 0)
        / nullif(sum(hs.total_aum), 0), 1)    as pct_aum_at_risk,
  coalesce(sum(hs.heirs_total), 0)::int       as heirs_total,
  coalesce(sum(hs.heirs_known), 0)::int       as heirs_known,
  coalesce(sum(hs.heirs_unknown), 0)::int     as heirs_unknown,
  coalesce(sum(hs.unassigned_balance), 0)     as unassigned_balance
from public.advisors a
left join public.household_summary hs on hs.advisor_id = a.id
group by a.id;


-- ---------------------------------------------------------------------
-- 4. Security: RLS on every table + explicit grants
--    New Supabase projects do NOT expose public tables to the API unless
--    you grant access, so the grants below are required, not optional.
--
--    Default here: only signed-in users can read or write.
--    Sign-in is handled by Clerk (added in Supabase as a third-party auth
--    provider). A signed-in Clerk user arrives as the `authenticated` role,
--    and their Clerk ID is available in SQL as  auth.jwt()->>'sub'.
--    Hackathon-simple (any signed-in user sees everything). Before real
--    client data goes in, scope the policies by firm_id.
-- ---------------------------------------------------------------------

do $$
declare t text;
begin
  foreach t in array array[
    'firms','advisors','households','clients','heirs','accounts',
    'documents','beneficiary_designations','interactions','retention_assumptions'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create policy "signed-in users: full access" on public.%I
         for all to authenticated using (true) with check (true)', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated, service_role', t);
  end loop;

  foreach t in array array[
    'heir_relationship','household_horizon','heir_account_shares','heir_priority',
    'account_beneficiary_gaps','household_summary','book_summary'
  ] loop
    execute format('grant select on public.%I to authenticated, service_role', t);
  end loop;
end $$;
