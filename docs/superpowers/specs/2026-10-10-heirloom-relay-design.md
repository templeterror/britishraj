# Heirloom Relay — domain intelligence + feature UI · Design spec

## Context
The user owns Heirloom Relay's domain workstream (blueprint `~/Downloads/Heirloom_Relay_Claude_Build_Plan.md`).
Goal: a demo-stable, 3–4 min end-to-end vertical slice on synthetic Morgan-family data, built into the shared
repo `~/britishraj` **without** rebuilding teammate A (Clerk/tenancy/shells) or teammate B (Plaid, Bright Data,
decision + alignment agents). Advisor (Sarah) is the buyer and primary demo surface. Success = blueprint §13
acceptance list + Phase-3 exit (goal yr 12→3 flips to timing qualification; sale delay changes cash, not value).

Decisions made in brainstorming (user-approved):
- **Own namespace**: screens at `/relay/advisor|parent|heir`; A's future `/advisor` etc. untouched.
- **Local-first storage with real adapters**: SQLAlchemy models → SQLite for demo; same models emitted as a
  Supabase migration (new `heirloom` schema); graph in-process by default, Neo4j driver when `NEO4J_URI` set.
- **Approach A**: Python/FastAPI owns domain, consent guard, projections, graph, NumPy forecast, classifier.
  Next.js is a typed client + UI with no business rules.
- **Forecast is a background pipeline**, not a studio: it raises flags; charts live only in the flag drill-down.
- **Look**: Kalshi-derived design language (`#00B67A` light / `#00DD94` dark green, black/white, flat, big
  tabular numerals). **No Kalshi logo or name** — product stays "Heirloom Relay".
- Scope: all P0 + heir memory Q&A. No LLM estate extraction, no post-death preview.

## Repo facts (main @ 6ac8802)
- Next.js 16.4 (AGENTS.md: breaking changes → read `node_modules/next/dist/docs/` before coding;
  `cacheComponents`, `partialPrefetching` on), React 19.3, @clerk/nextjs 7.9, inline styles, no Tailwind, no tests.
  Routes `/`, `/sign-in`, `/sign-up`; `middleware.ts` bare `clerkMiddleware()`; `lib/supabase.ts` Clerk-token client.
- `backend/` = `app/settings.py` only (its validators **raise** when Clerk keys are placeholders → don't import it
  in demo mode). `frontend/.env` already has `NEXT_PUBLIC_API_URL=http://localhost:8000`; settings has
  `frontend_origin` (CORS) and `clerk_jwks_url` (reuse in Clerk mode).
- Existing Supabase schema (heir_priority / retention "dollars at risk") is left untouched.
- Machine: node 22, Python 3.14 + numpy, uv, Chrome; no Docker/Java/Neo4j/Postgres.

## Architecture
```
frontend/app/relay/{layout,page}.tsx            temp chrome + DEMO persona picker (+ Reset demo)
frontend/app/relay/{advisor,parent,heir}/page.tsx   thin: mount one screen each
frontend/features/heirloom/
  screens/{Advisor,Parent,Heir}Screen.tsx
  components/  FlagFeed FlagCard FlagSheet EvidencePath EvidenceDrawer FamilyGraph(+nodes) ValueFanChart
               AccessibleCashChart ExplainCalculation IntentReview DecisionReview ActivityLog
               ConsentPanel GoalCheckIn HeirPreview MemoryAsk StateViews
  api/client.ts  hooks/{useFamily,useRevisionPoll}.ts  types/contracts.ts  styles/tokens.module.css
backend/app/main.py                              minimal create_app(); includes heirloom router (A/B can absorb)
backend/app/heirloom/
  config.py (HeirloomSettings: mode=demo|clerk, demo secret, db url, neo4j)  db.py  models.py  ids.py (uuid5)
  context/  auth_context.py (Clerk JWT via JWKS | HMAC demo token) access.py (FamilyAccess resolver)
  policy/   visibility.py  dto/{advisor,parent,heir}.py (separate response models per audience)
  services/ events.py consent.py goals.py intents.py decisions.py graph.py projection.py
            readiness.py (pipeline) insights.py actions.py memory_qa.py audit.py
  graph/    repository.py (protocol) memory.py neo4j_repo.py (MERGE on record_id, named param queries)
  simulation/ engine.py scenarios.py
  providers/ protocols.py mock_financial.py mock_market.py mock_decision.py rule_alignment.py
  routers/  families.py intents.py decisions.py goals.py consents.py graph.py insights.py actions.py
            memory.py integrations.py demo.py
  fixtures/ morgan_family.json meeting_2026_04_15.txt estate_letter_2026.txt draft_will_2024.txt
            conflicting_amendment.txt market_events.json
  scripts/  seed.py  emit_pg_migration.py
backend/tests/   (pytest)
supabase/migrations/20261010160000_heirloom_domain.sql   generated, `heirloom` schema, non-destructive
contracts/heirloom.openapi.json (generated)   docs/integration_contracts.md   README_HEIRLOOM.md
```
API: FastAPI `/api/v1`, envelope `{data, meta:{revision, mode, degraded?}, errors}`, `Cache-Control: no-store`
on all family routes. Endpoints = blueprint §9 table, plus `GET /families/{id}/revision`,
`GET /families/{id}/evidence/{ref}`, `GET /families/{id}/heir-preview` (parent), `POST /families/{id}/memory/ask`
(heir), `PATCH /families/{id}/assets/{id}/terms` (advisor), `POST /demo/sessions` + `POST /demo/reset`
(demo mode only). Browser calls FastAPI directly with `Authorization: Bearer <clerk token | demo token>`.

## Data model (`heirloom` schema)
Blueprint §5 tables: families, family_people, assets (+`terms_json`: liquidatable_fraction, sale_delay_years,
sale_cost_fraction, distribution_yield, partner_consent_required, lockup), legal_instruments, transfer_intents,
source_documents, decision_records, heir_goals (versioned), consent_grants, forecast_scenarios,
forecast_results, insights, advisor_actions, domain_events (unique idempotency_key), audit_log; plus
`families.consent_revision`. IDs: uuid5 from business refs (`asset-family-llc`), ref kept in `external_ref`.
`organization_id` = A's org id as text, no FK into A's tables.

**Fixtures (Morgan, synthetic):** Robert (parent), James (29, heir), Sarah Lin (advisor). Assets: 40% family-LLC
interest ($5M, $1.2M debt, 25% liquidatable, 2-yr sale delay, partner consent), concentrated public stock,
liquid brokerage. Instruments: 2024 draft will (superseded), 2026 estate-planning letter naming James for the
LLC interest (verified), optional conflicting amendment. 5 decisions 2020–2026; the 2026-04-15 "retain LLC
interest" arrives as a **candidate** via MockDecisionAnalysisProvider for live verification. James goals:
business ($500K, yrs 8–12) and foundation (after yr 20). Consents default **off**.

## Identity, access, privacy
- `auth_context` returns `RequestContext{external_user_id, organization_id}` only. Clerk mode: verify JWT with
  JWKS. Demo mode: HMAC-signed token from `POST /demo/sessions` (server picks the person). Role never read from
  request body/query.
- `FamilyAccess`: org match + person ∈ family_people → domain role. Forged/cross-org family → 404 + audit.
- Visibility (enforced by distinct DTOs; disallowed fields are absent, never masked):
  - Sarah: assets/balances, intents, all decisions (incl. candidates), insights/actions; James's goal only via
    active grant — `goal_summary` (kind + horizon band) or `goal_detail` (amount, year).
  - Robert: own assets/decisions/intents, grants he gives, heir preview; never James's goal.
  - James: own goals; only decisions Robert approved individually (`decision_excerpt` per record); no
    assets, balances, intents, insights; sees "Sarah offered a planning conversation" once an heir_intro is approved.
- Revocation chain: consent change → `consent_revision++` → insights on old revision `invalidated` and filtered
  on read → unsent goal-derived drafts cancelled + text purged → projection drops goal node → advisor copy
  "James has not shared any current goals." Audit allowed + denied sensitive reads.

## Graph
Blueprint §5 node/edge types; each carries record_id, valid_from/valid_to, observed_at, evidence_status,
classification. `INTENDED_FOR` only when intent verified **and** instrument current; supersession sets valid_to.
Never an ownership edge. `authorized_graph_projection(ctx, family, as_of)` = graph read → SQL-policy filter →
DTO `{nodes, edges, evidence_refs, revision}`. Neo4j unreachable → fall back to memory repo, `meta.degraded=true`.

## Background readiness pipeline
Triggers (synchronous, in-request): intent verified/superseded, goal updated, consent changed, asset terms
edited, market context ingested, alignment candidate ingested. `readiness.recompute(family)`:
1. Build `AuthorizedAlignmentContext` server-side after consent checks (unshared goal ⇒ no derivatives).
2. For each (verified intent, consented goal): scenario grid T∈{10,20,30} × {base, exit delay +24m, −30% yr-1
   shock, 20% sale haircut}, 2,000 paths, cached by input-hash + consent_revision.
3. Deterministic classifier → upsert insights, invalidate stale, refresh projection, emit events.
Other windows poll `GET /revision` every ~2.5 s and refetch on change.

**Engine** (`relay-forecast-1.0`, `numpy.random.Generator(PCG64(seed))`):
- `log(V[t+1]/V[t]) = ln(1+μ−fee) − ½σ² + σZ`; nominal + real series; model only the interest the intent names.
- Goal nominal `A_nom = A_today·(1+i)^G`.
- Accessible cash at G given hypothetical transfer T: if T>G → 0 (timing, not shortfall). Else sale completes
  S=T+admin_delay+sale_delay; if S≤G proceeds = f·max(0, V_S−D)·(1−sale_cost) (debt/costs once) + Σ_{T..G} d·V_t;
  floor 0; admin cost reported separately. Unknown terms ⇒ probability `null`, "unknown — attorney review".
- Outputs: per-year P10/P50/P90 value; cash quantiles at G; P(cash ≥ A_nom | T, terms); shortfall share;
  limitations; seed, model_version, input hash.

**Classifier** (blueprint §7 order): goal unshared → nothing · intent unverified → relationship_opportunity
(no estate facts) · instruments conflict → legal review · G < earliest modeled T → timing_gap/independent
financing + timing review · base or any standard stress P < 0.5 (configurable) → conditional readiness gap
naming the breaking condition ("Base 81% · exit delay +24m 6% · paper value unchanged") · else no known
mismatch + relationship opportunity. Each insight stores evidence ids, assumption snapshot, consent_revision,
model_version. Fixture terms tuned so golden numbers tell this story; tests pin them.

Golden behavior: goal yr 12 / T=10 → stress-revealed readiness gap · goal yr 3 → timing/independent need ·
foundation yr 20+ → no mismatch + philanthropy conversation · sharing off → insight gone (API + graph) ·
2026 letter superseded → asset-specific alert invalidated.

## Advisor actions & integrations
- Deterministic draft templates: `parent_review` (agenda for Robert + estate counsel; never proposes changing his
  portfolio for James) and `heir_intro` (business-funding conversation). Lifecycle draft→approved→completed
  (outcome note)/cancelled; insight new→reviewed→actioned/dismissed/invalidated. Nothing is ever sent.
- Server guard rejects heir-facing text mentioning the asset, intent, beneficiary terms or amounts.
- B ingest: decisions → idempotent candidate → Sarah verifies; market context → sourced timestamped event,
  may propose stress preset + invalidate caches, never return forecasts; alignment → re-validate family, verified
  current intent, consent at current revision, evidence ids exist/authorized, classifier agreement; else 422 +
  reason codes + audit; accepted agent text labeled "agent explanation (unverified)".
- Providers (Python protocols mirroring blueprint §11 TS interfaces): FinancialDataProvider,
  MarketContextProvider, DecisionAnalysisProvider, AlignmentAnalysisProvider; mocks from fixtures; one
  `providers/registry.py` mapping file is the swap point.

## UI (Kalshi-derived)
Tokens: white bg, near-black ink, `#00B67A` accent (`#00DD94` dark), hairline borders, flat (no gradients),
Inter via next/font, tabular numerals; small-caps status labels ("VERIFIED · 15 APR 2026 · ADVISOR-ONLY");
"Mock data mode" badge on every screen. Charts = hand-built SVG (load `dataviz` skill before writing them).
- `/relay`: persona cards Sarah/Robert/James, demo banner, Reset demo.
- Advisor: family header (no "$ at risk"); flag feed with filters (Needs parent review / Heir conversation /
  Legal source conflict / Scenario mismatch), Kalshi-style card = big conditional % + condition; side sheet with
  evidence-path breadcrumbs → source drawers, value fan + accessible-cash charts, 10/20/30 toggle, stress row,
  Explain the calculation, two actions; React Flow graph (custom nodes by class, lock badge, as-of slider,
  click → evidence drawer); tabs Estate intents (instrument text vs candidates, verify/reject, status),
  Decision memory (candidate vs transcript excerpt, verify/reject/annotate), Activity (actions + audit).
- Parent: decision history + request correction, "What I want to preserve", per-decision share toggles,
  estate-intent facts off, balances "not available in this pilot", server-computed exact Heir preview,
  "Mark reviewed with counsel".
- Heir: goal check-in (kind, narrative, optional amount, target year, milestone; "Your information is private
  unless you choose to share it"), independent summary/detail share switches, 2–3 planning prompts, approved
  memory + Ask (deterministic keyword retrieval over approved excerpts only; refusal "No approved record answers
  that."), advisor invitation card, empty states, no inheritance wording.
- All blueprint UI states (loading … mock data mode) implemented.

## Shared-file edits (additive only)
`backend/requirements.txt` (+sqlalchemy, numpy, pyjwt[crypto], neo4j, pytest, httpx, ruff),
`frontend/package.json` (+@xyflow/react, vitest), `.env.example` files (+optional HEIRLOOM_MODE,
HEIRLOOM_DEMO_SECRET, NEO4J_URI/USER/PASSWORD). `settings.py`, middleware, layout, existing migrations untouched.

## Build order (each phase ends with ruff + pytest + tsc + eslint + vitest, fix failures)
0. Branch `feature/heirloom-domain`; save this spec to `docs/superpowers/specs/2026-10-10-heirloom-relay-design.md`;
   invoke `superpowers:writing-plans` for the task-level plan; extract + view Kalshi brand-asset PNGs (scratchpad);
   `npm install`, read Next 16.4 docs (routing, client components, next/font, env); uv venv for backend.
1. Contracts + skeleton: `docs/integration_contracts.md`, provider protocols, main.py, envelope, context/access, demo sessions.
2. Models, uuid5 ids, fixtures, seed, PG migration emitter, repositories.
3. Graph repo (memory + neo4j), projection, evidence endpoint; React Flow graph + drawer.
4. Estate-intent import/verify + decision verify state machines + review UIs.
5. Heir goals (versioned) + consents + revocation chain + parent heir preview + memory Q&A.
6. Simulation engine + scenario grid + classifier + readiness pipeline + flag feed/sheet/charts.
7. Advisor actions + heir-safe text guard + activity/audit UI.
8. Integration ingest endpoints + validation; mock providers wired via registry.
9. Full test matrix, OpenAPI export, README_HEIRLOOM.md, polish, Chrome-driven golden demo (screenshots + GIF).

## Verification
- `cd backend && uv run pytest` — forecast invariants (fixed seed ⇒ fixed percentiles; P10≤P50≤P90; zero cash
  before transfer; delay changes cash not value; no double subtraction; inflation conversion; non-negative cash;
  stress lowers liquidity), classifier cases, permissions (forged family_id, cross-org, `?view=advisor`, role in
  body ignored), revocation via direct API calls, graph (verified-only edges, superseded), ingest validation,
  blueprint integration tests 1–12 (incl. Neo4j down ⇒ degraded meta).
- `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`.
- Run `uv run uvicorn app.main:app --port 8000` + `npm run dev`; drive golden demo in Chrome via /relay:
  verify decision → open flag (3 evidence links) → James edits goal/sharing → flag recomputes/disappears in
  Sarah's window → goal yr 3 timing flag → stress shows value steady / cash collapses → Robert approves one
  decision → James asks "Why was family control important?" → actions drafted, nothing sent. Capture screenshots/GIF.
- Handoff report: file-by-file changes, commands, demo evidence, test results, adapter contracts, mock vs real
  table (Clerk mode wired but unverified without keys; Neo4j adapter untested without an instance; all B
  providers mocked), risks/blockers.
