# Heirloom Relay Domain Workstream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A demo-stable end-to-end Heirloom Relay vertical slice (synthetic Morgan family) — evidence-backed decision memory, verified estate intent graph, heir goals with two independent consents enforced server-side, a background transfer-aware forecast that raises advisor flags, and advisor action drafts — mounted at `/relay/*` without touching teammates' auth or integrations.

**Architecture:** FastAPI package `backend/app/heirloom/` owns all domain logic: SQLAlchemy persistence (SQLite locally, generated Postgres migration), server-resolved identity, per-audience DTOs, an in-process graph with a Neo4j adapter, a NumPy Monte Carlo engine and a deterministic classifier run synchronously by a readiness pipeline on every domain event. Next.js renders three client screens under `frontend/app/relay/` that call FastAPI directly with a Bearer token and poll a revision endpoint.

**Tech Stack:** Python 3.14, FastAPI 0.143, SQLAlchemy 2.1, NumPy 2.5, PyJWT 2.15, neo4j 6.4, pytest, httpx, ruff · Next.js 16.4, React 19.3, @xyflow/react 12, vitest 5, @testing-library/react, jsdom, CSS Modules.

**Spec:** `docs/superpowers/specs/2026-10-10-heirloom-relay-design.md` (read it; this plan argues from it). Blueprint: `~/Downloads/Heirloom_Relay_Claude_Build_Plan.md`.

## Global Constraints

- Do not modify: `frontend/app/layout.tsx`, `frontend/app/page.tsx`, `frontend/middleware.ts`, `frontend/lib/supabase.ts`, `frontend/app/sign-*`, `backend/app/settings.py`, existing `supabase/migrations/*`. Shared-file edits are additive only (`backend/requirements.txt`, `frontend/package.json`, `*.env.example`).
- Never import `app.settings` from heirloom code (its validators raise without Clerk keys).
- Role/actor never comes from request body or query string; `?view=`, `role`, `actor_user_id`, `org_id` in requests are ignored.
- Disallowed fields are absent from responses (separate DTOs per audience), never masked. All `/api/v1/families/*` responses carry `Cache-Control: no-store`.
- Response envelope: `{"data": ..., "meta": {"revision": int, "consent_revision": int, "mode": "demo"|"clerk", "degraded": [str]}, "errors": [{"code": str, "message": str}]}`.
- Consents default **off**. Scopes `estate_intent` and `balances` toward an heir are rejected with code `not_available_in_pilot`.
- No trade execution, no sending of messages, no death prediction, no inheritance promise. Forecast copy always says "if transfer were to occur in year N" and "illustrative".
- Model version string `relay-forecast-1.0`; default seed `40626`; paths `2000`; review threshold `0.5`; grid transfer years `(10, 20, 30)`; stress presets `base`, `exit_delay_24m`, `shock_30_y1`, `sale_haircut_20`.
- UI: product name "Heirloom Relay" only; no Kalshi logo/name. Tokens: accent `#00B67A` (light) / `#00DD94` (dark), ink `#0A0A0A`, bg `#FFFFFF`, hairline `#E6E6E6`, muted `#6B6B6B`; flat surfaces, no gradients; Inter via `next/font/google`; `font-variant-numeric: tabular-nums` on numbers. Every screen shows a "Mock data mode" badge when `meta.mode == "demo"`.
- Synthetic data only. Demo personas: `demo_sarah` (advisor), `demo_robert` (parent), `demo_james` (adult_heir) in org `org_relay_demo`; a second org `org_other` with `demo_other_advisor` and family `family-chen` exists only for isolation tests.
- After every task: `cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q` and (from Task 11) `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run` — all green before commit.

## Review Focus

- Sarah's tab has a flag sheet open when James revokes sharing → sheet closes and shows "James has not shared any current goals." on next revision poll (test in Task 13).
- James edits his goal in two tabs → second save gets 409 `version_conflict` and UI says the goal changed elsewhere, offering reload (tests in Task 6 and Task 15).
- Goal saved with no amount or no target year → pipeline yields "insufficient modeling data" relationship insight, never a 0%/100% probability (test in Task 8).
- Demo token rejected (backend restarted with a new secret, or expired) → UI clears session and returns to `/relay` picker instead of a blank screen (test in Task 11).
- Backend unreachable → screens render a recoverable error with Retry, not a crash or empty graph (test in Task 11).

---

## File Structure

```
backend/
  pyproject.toml                         ruff + pytest config (new)
  .gitignore                             .venv/, .data/ (new)
  requirements.txt                       + sqlalchemy numpy pyjwt[crypto] neo4j pytest httpx ruff
  app/__init__.py  app/main.py           create_app(); mounts heirloom router
  app/heirloom/
    __init__.py  config.py  envelope.py  db.py  models.py  ids.py
    context/auth_context.py  context/access.py
    dto/advisor.py  dto/parent.py  dto/heir.py  dto/common.py
    services/events.py  audit.py  seed.py  graph.py  projection.py  evidence.py
             intents.py  decisions.py  goals.py  consent.py  memory_qa.py
             readiness.py  classifier.py  insights.py  actions.py  heir_text_guard.py
             snapshots.py  integrations.py
    graph/repository.py  graph/memory.py  graph/neo4j_repo.py  graph/factory.py
    simulation/engine.py  simulation/scenarios.py
    providers/protocols.py  providers/mocks.py  providers/registry.py
    routers/demo.py  families.py  intents.py  decisions.py  goals.py  consents.py
            graph.py  insights.py  actions.py  memory.py  integrations.py  assets.py
    fixtures/morgan_family.json  chen_family.json  meeting_2026_04_15.txt
             estate_letter_2026.txt  draft_will_2024.txt  conflicting_amendment.txt  market_events.json
    scripts/emit_pg_migration.py  scripts/export_openapi.py
  tests/heirloom/conftest.py + test_*.py
supabase/migrations/20261010160000_heirloom_domain.sql   (generated)
contracts/heirloom.openapi.json                          (generated)
docs/integration_contracts.md   README_HEIRLOOM.md
frontend/
  vitest.config.mts  vitest.setup.ts
  app/relay/layout.tsx  app/relay/page.tsx  app/relay/{advisor,parent,heir}/page.tsx
  features/heirloom/
    session.ts  api/client.ts  types/contracts.ts  hooks/useRelayQuery.ts  hooks/useRevisionPoll.ts
    styles/tokens.module.css (+ one *.module.css per component)
    components/StateViews.tsx  ModeBadge.tsx  PersonaPicker.tsx  StatusLabel.tsx
               FamilyHeader.tsx  FlagFeed.tsx  FlagCard.tsx  FlagSheet.tsx  EvidencePath.tsx
               EvidenceDrawer.tsx  ValueFanChart.tsx  AccessibleCashChart.tsx  ExplainCalculation.tsx
               ActionPanel.tsx  FamilyGraph.tsx  graphNodes.tsx  IntentReview.tsx  DecisionReview.tsx
               ActivityLog.tsx  AssetTermsEditor.tsx  ParentSharing.tsx  HeirPreview.tsx
               GoalCheckIn.tsx  GoalSharing.tsx  MemoryAsk.tsx  ApprovedMemory.tsx  InvitationCard.tsx
    screens/AdvisorScreen.tsx  ParentScreen.tsx  HeirScreen.tsx
    __tests__/*.test.ts(x)
```

---

### Task 1: Backend skeleton, config, envelope, health

**Files:**
- Create: `backend/pyproject.toml`, `backend/.gitignore`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/heirloom/__init__.py`, `backend/app/heirloom/config.py`, `backend/app/heirloom/envelope.py`, `backend/tests/heirloom/conftest.py`, `backend/tests/heirloom/test_health.py`
- Modify: `backend/requirements.txt` (append deps listed in Tech Stack, unpinned minimums `sqlalchemy>=2.1`, `numpy>=2.4`, `pyjwt[crypto]>=2.10`, `neo4j>=6.0`, `pytest>=8`, `httpx>=0.28`, `ruff>=0.14`)

**Interfaces:**
- Produces: `HeirloomSettings` (pydantic-settings, env prefix `HEIRLOOM_`): `mode: Literal["demo","clerk"]="demo"`, `demo_secret: str="dev-only-demo-secret"`, `demo_token_ttl_s: int=43200`, `database_url: str="sqlite:///./.data/heirloom.db"`, `neo4j_uri: str|None=None`, `neo4j_user: str="neo4j"`, `neo4j_password: str|None=None`, `integration_token: str="dev-integration-token"`, `frontend_origin: str="http://localhost:3000"`, `clerk_domain: str|None=None`, `review_threshold: float=0.5`; `get_settings() -> HeirloomSettings` (lru_cache).
- Produces: `envelope.ok(data, meta: Meta) -> dict`, `Meta` (pydantic: revision, consent_revision, mode, degraded: list[str]=[]), `ApiError(Exception)(status: int, code: str, message: str)`, `install_error_handlers(app)`.
- Produces: `app.main.create_app(settings: HeirloomSettings|None=None) -> FastAPI` with CORS for `frontend_origin` (credentials off, `Authorization` header allowed) and router prefix `/api/v1`; module-level `app = create_app()`.
- Produces (test): `conftest.py` fixtures `settings` (demo mode, `database_url="sqlite://"`), `client` (TestClient on `create_app(settings)`).

- [ ] **Step 1: Write failing test** `test_health.py::test_health_envelope`: `GET /api/v1/health` → 200; body `{"data": {"status": "ok"}, "meta": {"mode": "demo", ...}, "errors": []}`; header `cache-control == "no-store"`. `test_unknown_route_uses_error_envelope`: `GET /api/v1/nope` → 404 and `body["errors"][0]["code"] == "not_found"`.
- [ ] **Step 2:** `cd backend && .venv/bin/pytest tests/heirloom/test_health.py -q` → FAIL (import error).
- [ ] **Step 3:** Implement the files above. A middleware sets `Cache-Control: no-store` on every `/api/v1` response. Handlers map `ApiError`, `HTTPException`, `RequestValidationError` (code `validation_error`, status 422) into the envelope. `pyproject.toml`: `[tool.ruff] line-length=110, target-version="py313"`, `[tool.pytest.ini_options] testpaths=["tests"]`, `pythonpath=["."]`.
- [ ] **Step 4:** Re-run → PASS; `.venv/bin/ruff check .` → clean.
- [ ] **Step 5: Commit** `feat(heirloom): backend skeleton with envelope and health`

---

### Task 2: Domain models, deterministic IDs, fixtures, seed

**Files:**
- Create: `app/heirloom/db.py`, `models.py`, `ids.py`, `services/seed.py`, all `fixtures/*`, `tests/heirloom/test_seed.py`
- Modify: `tests/heirloom/conftest.py` (add `db_session`, seeded `client`)

**Interfaces:**
- Produces: `ids.ref_id(ref: str) -> uuid.UUID` = `uuid5(NAMESPACE, ref)` with `NAMESPACE = uuid.UUID("5b0e8a4e-1f0c-4c1a-9d8e-6f1e2a3b4c5d")`.
- Produces: `db.make_engine(url) -> Engine` (SQLite: `schema_translate_map={"heirloom": None}`, `check_same_thread=False`, StaticPool for `sqlite://`); `db.SessionFactory`; FastAPI dep `db.get_session() -> Iterator[Session]` (commit on success, rollback on error).
- Produces: SQLAlchemy 2 declarative models, all with `__table_args__ = {"schema": "heirloom"}` and family tables carrying `organization_id: str`, `family_id: UUID`, `external_ref: str|None (unique per family)`. Tables and enum values exactly as spec §Data model / blueprint §5, plus: `Family.data_revision:int=0`, `Family.consent_revision:int=0`, `Family.as_of_year:int`, `Family.preserve_values: JSON list[str]`; `Asset.terms: JSON` (keys: `expected_return, annual_volatility, annual_fee, liquidatable_fraction, sale_delay_years, admin_delay_years, sale_cost_fraction, distribution_yield, admin_cost_fraction, partner_consent_required, partner_consent_process_documented`); `LegalInstrument.counsel_reviewed_at: datetime|None`; `TransferIntent.status ∈ {proposed, verified, superseded, contested}`; `DecisionRecord.verification_status ∈ {candidate, verified, rejected}`, `rationale_edited: bool`, `advisor_note: str|None`, `valid_to: date|None`; `HeirGoal` fields `goal_kind, description_private, amount_target, target_year, horizon_min_years, horizon_max_years, milestone, goal_funding_source, version`; `ConsentGrant(grantor_person_id, recipient_person_id, resource_type ∈ {heir_goal, decision}, resource_id, share_scope, active, effective_at, revoked_at, revision, recorded_by)`; `Insight.insight_key, input_hash, filter_tags JSON, payload JSON, review_status ∈ {new, reviewed, dismissed, actioned, invalidated}`; `AdvisorAction.status ∈ {draft, approved, completed, cancelled}`; `MarketEvent(family_id, asset_id, title, url, published_at, summary, proposed_stress)`; `DomainEvent.idempotency_key unique`; `AuditLog(actor_external_id, family_id|None, action, resource_type, resource_id|None, allowed, reason_code, at)`.
- Produces: `seed.reset_and_seed(session) -> None` (drops all heirloom rows, loads `morgan_family.json` + `chen_family.json`, idempotent); called on app startup in demo mode when DB empty.

**Fixture values (`morgan_family.json`, all synthetic):** org `org_relay_demo`, family ref `demo-morgan`, display "Morgan family", `as_of_year: 2026`, preserve_values `["Family control of the business", "Avoid forced sales", "Long-term growth", "Charitable purpose"]`. People: `person-sarah` Sarah Lin (advisor, `demo_sarah`), `person-robert` Robert Morgan (parent, `demo_robert`), `person-james` James Morgan (adult_heir, `demo_james`, age 29). Assets owned by Robert:
  - `asset-family-llc` "40% interest, Morgan Family Holdings LLC", private_business, illiquid, value 5000000, liabilities 1200000, terms `{expected_return:0.055, annual_volatility:0.22, annual_fee:0.0, liquidatable_fraction:0.25, sale_delay_years:2, admin_delay_years:0, sale_cost_fraction:0.09, distribution_yield:0.01, admin_cost_fraction:0.01, partner_consent_required:true, partner_consent_process_documented:true}`
  - `asset-public-stock` "Concentrated position, Northwind Robotics (NWRB)", public_equity, liquid, value 2400000, liabilities 0, terms expected_return 0.07, volatility 0.32, liquidatable_fraction 1.0, sale_delay_years 0, sale_cost 0.01, distribution_yield 0.015, partner_consent_required false
  - `asset-brokerage` "Diversified brokerage account", cash/other liquid, value 3100000.
  Instruments: `instr-draft-will-2024` (will, effective 2024-05-01, status superseded, source `draft_will_2024.txt`), `instr-estate-letter-2026` (letter_of_intent, effective 2026-03-02, revocable true, status verified, source `estate_letter_2026.txt`). Intents: `intent-2024-llc-split` (2024 will → LLC, beneficiary James, "one half of the LLC interest", status superseded, valid_to 2026-03-02); `intent-james-llc` (2026 letter → LLC → James, "Robert's 40% membership interest", conditions `["Subject to the LLC operating agreement's partner-consent provisions", "Revocable; may be amended by Robert at any time"]`, status verified, advisor_verified true, verified_by Sarah, confidence 0.93, valid_from 2026-03-02). Decisions (all Robert, advisor Sarah, asset as noted, sources as source_documents rows):
  1. `decision-avoid-reactive-sale` 2020-03-18, asset-public-stock, "Avoid a reactive sale during the market drawdown", rationale "Robert and Sarah documented a long investment horizon and agreed to review objectives before changing holdings.", verified.
  2. `decision-2021-llc-sale-preference` 2021-06-02, asset-family-llc, "Prefer an eventual sale of the LLC interest to fund family liquidity", verified, valid_to 2026-04-15.
  3. `decision-liquidity-reserve` 2023-11-09, asset-brokerage, "Build a two-year liquidity reserve", rationale "Robert wanted enough near-term cash to avoid relying on stock sales in a volatile market.", verified.
  4. `decision-retain-stock-tax` 2025-02-20, asset-public-stock, "Retain the concentrated stock position pending a tax review", verified.
  5. `decision-retain-llc` 2026-04-15, asset-family-llc, **not in morgan_family.json** — produced by `MockDecisionAnalysisProvider` from `meeting_2026_04_15.txt` during seed and stored as **candidate**: action "Keep the family LLC interest rather than force a sale", rationale "Retain family control of the business and avoid a forced sale in unfavorable conditions", alternatives `["Sell part of the interest", "Refinance the LLC debt", "Retain the holding"]`, locator `{start_seconds:113, end_seconds:148, quoted_span:"We want to keep control of the business in the family. I don't want to be forced to sell when the timing is wrong."}`, confidence 0.91.
  Goal: `goal-james-business` kind business, description "Build a software company; I expect to need roughly $500,000 in startup liquidity.", amount 500000, target_year 2038, horizon_min 8, horizon_max 12, milestone "Incorporate and raise a pre-seed round", funding_source unknown. `goal_presets.foundation`: kind philanthropy, "Endow a small family foundation", amount 250000, target_year 2051, horizon_min 20, horizon_max 25. No consent grants. `chen_family.json`: org `org_other`, family `family-chen`, one advisor `demo_other_advisor`, one asset, nothing else.
  Text fixtures: short synthetic documents (≤ 40 lines each) whose excerpts match the locators above; `conflicting_amendment.txt` is a 2026-09-01 "First Amendment" letter that names "Claire Morgan (Robert's niece)" for the same LLC interest; `market_events.json` has one event for `asset-public-stock` (title "Northwind Robotics discloses customer concentration risk in 10-Q", url `https://example.com/nwrb-10q`, published_at 2026-08-07, proposed_stress `shock_30_y1`).

- [ ] **Step 1: Write failing tests** `test_seed.py`:
  - `test_ref_id_is_deterministic`: `ref_id("asset-family-llc") == ref_id("asset-family-llc")` and `!= ref_id("asset-public-stock")`.
  - `test_seed_counts`: after `reset_and_seed`, Morgan family has 3 people, 3 assets, 2 instruments, 2 intents, 5 decisions (4 verified, 1 candidate `decision-retain-llc`), 1 goal, 0 consent grants; Chen family exists under `org_other`.
  - `test_seed_is_idempotent`: running twice yields the same counts and the same UUID for `intent-james-llc`.
  - `test_candidate_decision_has_locator`: `decision-retain-llc.source_locator["start_seconds"] == 113` and the quoted_span appears verbatim in `meeting_2026_04_15.txt`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS, ruff clean.
- [ ] **Step 5: Commit** `feat(heirloom): domain models, deterministic ids and Morgan fixtures`

---

### Task 3: Identity, demo sessions, family access, audit

**Files:**
- Create: `context/auth_context.py`, `context/access.py`, `services/audit.py`, `services/events.py`, `routers/demo.py`, `routers/families.py` (revision endpoint only for now), `tests/heirloom/test_access.py`
- Modify: `conftest.py` (helper `auth(client, persona) -> dict[str,str]` posting `/api/v1/demo/sessions`)

**Interfaces:**
- Produces: `RequestContext` (frozen dataclass: `external_user_id: str`, `organization_id: str`).
- Produces: `auth_context.issue_demo_token(external_user_id, organization_id, settings) -> str` — format `demo.<b64url(json{sub,org,exp})>.<b64url(hmac_sha256)>`; `auth_context.resolve_request_context(authorization: str|None, settings) -> RequestContext` (demo tokens verified with `hmac.compare_digest`; in clerk mode verify RS256 JWT via `jwt.PyJWKClient(f"https://{clerk_domain}/.well-known/jwks.json")`, issuer `https://{clerk_domain}`, org from `claims.get("org_id") or claims.get("o", {}).get("id")`); FastAPI dep `current_context`. Missing/invalid → `ApiError(401, "unauthenticated")`.
- Produces: `FamilyActor` (dataclass: `ctx`, `family: Family`, `person: FamilyPerson`, `role: Literal["advisor","parent","adult_heir"]`); `access.require_family(family_id: UUID, ctx, session) -> FamilyActor` → 404 `family_not_found` (and audit `allowed=False, reason_code="not_member"`) when family missing, org mismatch, or person not in family; `access.require_role(actor, *roles)` → 403 `forbidden_for_role` + audit.
- Produces: `audit.record(session, actor_external_id, family_id, action, resource_type, resource_id, allowed, reason_code) -> None`.
- Produces: `events.emit(session, family: Family, type: str, aggregate_ref: str, payload: dict, idempotency_key: str|None=None) -> bool` (False if duplicate key; increments `family.data_revision`; runs registered handlers synchronously); `events.register(type_or_star: str, handler: Callable[[Session, Family, DomainEvent], None])`.
- Produces routes: `POST /api/v1/demo/sessions {persona: "sarah"|"robert"|"james"|"other_advisor"}` → `{token, family_id, person: {id, display_name, role}}` (404 in clerk mode); `POST /api/v1/demo/reset` (demo mode, any demo token) → reseeds; `GET /api/v1/families/{family_id}/revision` → `{revision, consent_revision}`; `GET /api/v1/me/families` → families the caller belongs to.

- [ ] **Step 1: Write failing tests** `test_access.py`:
  - `test_missing_token_401`, `test_tampered_token_401` (flip one char of signature), `test_expired_token_401` (issue with ttl −1).
  - `test_member_can_read_revision` (sarah → 200, `data["revision"] >= 0`).
  - `test_cross_org_family_is_404`: other_advisor GET Morgan revision → 404 `family_not_found`; an audit row with `allowed=False` exists.
  - `test_forged_family_id_is_404`: sarah GET `family-chen` id → 404.
  - `test_role_and_view_params_ignored`: james GET `/families/{morgan}/revision?view=advisor&role=advisor` with JSON body `{"role":"advisor"}` returns 200 and the server's `FamilyActor.role` (exposed via `GET /api/v1/me/families` → `role`) is `"adult_heir"`.
  - `test_demo_sessions_disabled_in_clerk_mode`.
  - `test_event_idempotency`: emitting with the same key twice returns `True` then `False` and revision increments once.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS, ruff clean.
- [ ] **Step 5: Commit** `feat(heirloom): server-resolved identity, demo sessions, family access and audit`

---

### Task 4: Per-audience snapshots, graph repository, projection, evidence

**Files:**
- Create: `dto/common.py`, `dto/advisor.py`, `dto/parent.py`, `dto/heir.py`, `services/snapshots.py`, `graph/repository.py`, `graph/memory.py`, `graph/factory.py`, `services/graph.py`, `services/projection.py`, `services/evidence.py`, `routers/graph.py`; extend `routers/families.py`
- Test: `tests/heirloom/test_snapshots.py`, `tests/heirloom/test_graph.py`

**Interfaces:**
- Produces DTOs (pydantic, `model_config = ConfigDict(extra="forbid")`): `AdvisorSnapshot{family, advisor, people, assets(with value, liabilities, terms, market_events: list[{title, url, published_at, proposed_stress}] — empty until Task 10), instruments, intents, decisions(all statuses), goal_sharing: Literal["not_shared","summary","detail"], shared_goals: list[AdvisorGoalSummary|AdvisorGoalDetail], coverage{decisions_verified, decisions_total, assets_with_verified_intent, assets_total, heirs_connected, heirs_total}, open_flags:int}`; `ParentSnapshot{family, me, assets(own, with value), decisions(own, each with shared_with_heir: bool), intents(own, with counsel_reviewed_at), preserve_values, heirs: list[{person_id, display_name}], sharing: {decision_excerpts: int, estate_intent: "off", balances: "not_available_in_pilot"}}`; `HeirSnapshot{family: {id, display_name}, me, advisor: {display_name}, my_goals: list[HeirGoalView], sharing: {advisor_summary: bool, advisor_detail: bool}, approved_decisions: list[HeirDecisionView], invitations: list[InvitationView], planning_prompts: list[str]}`. `AdvisorGoalSummary{goal_id, kind, horizon_band:str, amount_band:str, amount_band_mid:int, horizon_max_years:int|None}`; `AdvisorGoalDetail` = summary + `{amount_target, target_year, milestone, description}`. `HeirDecisionView{decision_id, date, title, rationale, source_title, locator, verified_by_display}` (no asset value, no asset label beyond a generic `asset_kind`).
- Produces: `snapshots.build(actor, session) -> AdvisorSnapshot|ParentSnapshot|HeirSnapshot`; route `GET /api/v1/families/{id}/snapshot` returns the actor's DTO plus `meta`.
- Produces: `GraphRepository` Protocol: `upsert_nodes(org, family_id, nodes: list[GNode])`, `upsert_edges(org, family_id, edges: list[GEdge])`, `replace_family(org, family_id, nodes, edges)`, `read_family(org, family_id, as_of: date|None) -> tuple[list[GNode], list[GEdge]]`. `GNode(record_id, label, kind, classification, valid_from, valid_to, evidence_status, props)`, `GEdge(type, source_id, target_id, valid_from, valid_to, classification)`. `graph.factory.get_graph_repo() -> tuple[GraphRepository, list[str] degraded]`.
- Produces: `graph.rebuild_family_graph(session, family) -> None` (deterministic from SQL; registered as `"*"` event handler). Classifications: `internal_parent_advisor`, `private_heir`, `advisor_approved_goal`, `authorized_heir_history`, `family_member`, `advisor_only`. `INTENDED_FOR` edge only when intent `verified` and instrument status `verified` and `valid_to is None`; superseded/contested intents become nodes with `valid_to` set and no `INTENDED_FOR` edge. Never emit an `OWNS` edge from heir to asset.
- Produces: `projection.authorized_graph_projection(actor, session, as_of: date|None) -> GraphDTO{nodes, edges, evidence_refs, revision}` (re-checks grants in SQL per node; drops edges whose endpoints were dropped). Route `GET /api/v1/families/{id}/graph?as_of=YYYY-MM-DD`.
- Produces: `evidence.get(actor, session, record_ref: str) -> EvidenceDTO{record_ref, title, kind, status, qualifier, document_title, document_date, excerpt, locator}`; route `GET /api/v1/families/{id}/evidence/{record_ref}` → 404 `not_found` when unauthorized (no existence leak).

- [ ] **Step 1: Write failing tests.** `test_snapshots.py`:
  - `test_advisor_snapshot_has_no_goal_when_not_shared`: `goal_sharing == "not_shared"`, `shared_goals == []`, and the raw JSON text contains neither `"500000"` nor `"software company"`.
  - `test_heir_snapshot_has_no_estate_or_balances`: James's JSON has no keys `assets`, `intents`, `instruments` and the text contains none of `"LLC"`, `"5000000"`, `"intent-"`, `"Holdings"`.
  - `test_parent_snapshot_never_contains_heir_goal`: Robert's JSON text has no `"software company"` and no `my_goals`/`shared_goals` key.
  - `test_snapshot_cache_control_no_store`.
  `test_graph.py`:
  - `test_intended_for_only_for_verified_current_intent`: advisor graph has exactly one `INTENDED_FOR` edge (from `intent-james-llc` to `person-james`); the 2024 intent node has `valid_to == "2026-03-02"` and no `INTENDED_FOR`.
  - `test_candidate_decision_not_in_graph_as_verified`: node `decision-retain-llc` has `evidence_status == "candidate"`.
  - `test_heir_graph_excludes_private_parent_nodes`: James's projection has no node with classification `internal_parent_advisor`.
  - `test_as_of_before_2026_shows_2024_intent_current`: `as_of=2025-01-01` advisor projection shows the 2024 intent without `valid_to` relative to that date and no 2026 intent.
  - `test_rebuild_is_deterministic`: two rebuilds produce identical sorted node/edge lists.
  - `test_evidence_returns_transcript_excerpt_for_advisor` (decision-retain-llc → excerpt contains "keep control of the business") and `test_evidence_404_for_heir_on_intent`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS, ruff clean.
- [ ] **Step 5: Commit** `feat(heirloom): per-audience snapshots, graph projection and evidence`

---

### Task 5: Estate-intent and decision verification state machines

**Files:**
- Create: `services/intents.py`, `services/decisions.py`, `routers/intents.py`, `routers/decisions.py`, `tests/heirloom/test_verification.py`

**Interfaces:**
- Produces: `intents.import_fixture(actor, session, fixture_ref: Literal["conflicting_amendment"]) -> list[TransferIntent]` (advisor only; creates instrument status `reported` + `proposed` intents via a deterministic fixture extractor; emits `estate_intent.extracted.v1`).
- Produces: `intents.verify(actor, session, intent_id, verified: bool, notes: str|None, source_version: int) -> TransferIntent` (advisor only; 409 `stale_source` if `source_version != source_documents.revision`). On verify: if another current verified intent on the same asset names a different beneficiary → both become `contested`; else `verified`. Reject → status `superseded` is NOT used; rejected candidates get status `proposed` with `advisor_verified=False` and `verification_notes`. Emits `estate_intent.verified.v1`.
- Produces: `intents.set_instrument_status(actor, session, instrument_id, status: Literal["superseded"]) -> LegalInstrument` (advisor; sets its intents to `superseded`, `valid_to=today`).
- Produces: `intents.mark_counsel_reviewed(actor, session, intent_id)` (parent on own intents, or advisor).
- Produces: `decisions.verify(actor, session, decision_id, approved: bool, edited_rationale: str|None, note: str|None) -> DecisionRecord` (advisor only; only from `candidate`; approved → `verified` (`rationale_edited=True` if edited), else `rejected` and `note` required → 422 `note_required`); `decisions.annotate(actor, session, decision_id, note)`; `decisions.request_correction(actor, session, decision_id, note)` (parent, own decisions → emits `decision.correction_requested.v1`, sets advisor_note). Emits `decision.verified.v1`.
- Routes: `POST /families/{id}/estate-intents/import {fixture_ref}`, `POST /families/{id}/estate-intents/{intent_id}/verify {verified, notes, source_version}`, `POST /families/{id}/estate-intents/{intent_id}/counsel-reviewed`, `POST /families/{id}/instruments/{instrument_id}/status {status}`, `GET /families/{id}/decisions?status=`, `POST /families/{id}/decisions/{decision_id}/verify {approved, edited_rationale, note}`, `POST /families/{id}/decisions/{decision_id}/annotate {note}`, `POST /families/{id}/decisions/{decision_id}/request-correction {note}`.

- [ ] **Step 1: Write failing tests** `test_verification.py`:
  - `test_imported_amendment_is_candidate_and_no_edge`: after import, the new intent is `proposed` and the graph still has exactly one `INTENDED_FOR` edge.
  - `test_verifying_conflicting_amendment_contests_both`: verify amendment → both intents `contested`; graph has zero `INTENDED_FOR` edges.
  - `test_superseding_2026_letter_removes_edge`.
  - `test_stale_source_version_409`.
  - `test_heir_cannot_verify_intent_403`, `test_parent_cannot_verify_decision_403`.
  - `test_decision_verify_candidate_to_verified` (graph node evidence_status becomes `verified`; audit row written).
  - `test_decision_reject_requires_note_422`, `test_cannot_verify_already_verified_409` (code `invalid_transition`).
  - `test_edited_rationale_marks_edited`.
  - `test_parent_counsel_reviewed_sets_timestamp`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS, ruff clean.
- [ ] **Step 5: Commit** `feat(heirloom): estate-intent and decision verification`

---

### Task 6: Heir goals, consents, revocation chain, heir preview, memory Q&A

**Files:**
- Create: `services/goals.py`, `services/consent.py`, `services/memory_qa.py`, `routers/goals.py`, `routers/consents.py`, `routers/memory.py`, `tests/heirloom/test_goals_consent.py`, `tests/heirloom/test_memory_qa.py`

**Interfaces:**
- Produces: `goals.create(actor, session, data: GoalInput) -> HeirGoal` (adult_heir only); `goals.update(actor, session, goal_id, data: GoalPatch) -> HeirGoal` (owner only; `data.version` must equal stored → else 409 `version_conflict`; increments version; emits `heir_goal.updated.v1`). `GoalInput{goal_kind, description_private: str (1..2000), amount_target: int|None (> 0, ≤ 1_000_000_000), target_year: int|None (as_of_year < y ≤ as_of_year+50), horizon_min_years: int|None, horizon_max_years: int|None, milestone: str|None, goal_funding_source = "unknown"}`; invalid → 422.
- Produces: `consent.set_grant(actor, session, resource_id: UUID, scope, recipient_person_id: UUID, active: bool) -> ConsentState{grant, consent_revision}`. Rules: heir may grant `goal_summary`/`goal_detail` on own goals to the family advisor; `goal_detail` on ⇒ also activates `goal_summary`; `goal_summary` off ⇒ also deactivates `goal_detail`. Parent may grant `decision_excerpt` on own **verified** decisions to an adult_heir in the family. `estate_intent`/`balances` → 422 `not_available_in_pilot`. Any other combination → 403. Every change: `family.consent_revision += 1`, emit `consent.changed.v1`.
- Produces: `consent.goal_view_for_advisor(session, family, goal) -> AdvisorGoalSummary|AdvisorGoalDetail|None` (single source used by snapshots, projection, readiness). `amount_band`: round to nearest 100,000 → `"about $500K"`; `horizon_band`: `"8–12 years"` from min/max or `"by {target_year}"`; `amount_band_mid` = rounded value.
- Produces: `consent.on_consent_changed` handler: insights for the family with `consent_revision` < current and goal-derived (`payload.goal_ref` set) → `review_status="invalidated"`, `payload` replaced with `{"withdrawn": "consent_revoked"}`; unsent actions (`draft`/`approved`) on those insights → `cancelled`, `draft_text=""`. (Readiness recompute after this is wired in Task 8.)
- Produces: `GET /families/{id}/heir-preview` (parent only) → `{approved_decisions: list[HeirDecisionView]}` computed by the same function the heir snapshot uses (`snapshots.heir_approved_decisions(session, family, heir_person)`).
- Produces: `memory_qa.ask(actor, session, question: str) -> MemoryAnswer{status: "answered"|"refused", reason: str|None, matches: list[{decision_id, title, date, excerpt, source_title, locator, verified_by_display, score}]}` (adult_heir only). Tokenize lowercase `[a-z]+`, drop stopwords, score = count of distinct question terms found in `title + rationale + quoted_span`; return top 3 with score ≥ 1 over **heir-approved decisions only**. Questions containing any of `inherit, inheritance, will, estate, beneficiary, trust, worth, balance, how much` → refused, reason `"Heirloom can't answer questions about estate plans, balances or inheritance."`. No matches → refused, reason `"No approved record answers that."`. Route `POST /families/{id}/memory/ask {question}`.
- Routes: `POST /families/{id}/heir-goals`, `PATCH /families/{id}/heir-goals/{goal_id}`, `PUT /families/{id}/consents/{resource_id} {scope, recipient_person_id, active}`.

- [ ] **Step 1: Write failing tests** `test_goals_consent.py`:
  - `test_goal_saved_private_by_default` (advisor snapshot `goal_sharing == "not_shared"` after James PATCHes).
  - `test_summary_share_exposes_bands_only`: after James grants summary, advisor `shared_goals[0]` has `amount_band == "about $500K"`, `horizon_band == "8–12 years"` and the JSON has no `description`/`amount_target` keys.
  - `test_detail_share_implies_summary_and_revoke_summary_revokes_detail`.
  - `test_revocation_removes_goal_from_every_advisor_endpoint`: grant, then revoke; snapshot, graph and evidence (`/evidence/goal-james-business` → 404) responses for Sarah contain no goal id, no `"about $500K"`; `consent_revision` increased by 2. (Insight-level revocation is tested in Task 8.)
  - `test_version_conflict_409` (two PATCHes with the same version → second 409 `version_conflict`).
  - `test_goal_validation_422` for amount 0, amount −5, target_year 2020.
  - `test_estate_intent_scope_rejected` (Robert PUT scope `estate_intent` → 422 `not_available_in_pilot`).
  - `test_parent_cannot_share_candidate_decision_403`, `test_heir_cannot_grant_decision_excerpt_403`.
  - `test_heir_preview_matches_heir_view`: Robert shares `decision-liquidity-reserve`; `GET /heir-preview` equals James's `approved_decisions`; neither contains `"3100000"` or the asset label.
  `test_memory_qa.py`:
  - `test_family_control_question_answered_after_sharing`: Sarah verifies `decision-retain-llc`, Robert shares it, James asks "Why was family control important?" → `status == "answered"`, first match `decision_id` is that decision, excerpt contains "keep control of the business".
  - `test_unshared_record_not_retrievable` (same question before sharing → refused "No approved record answers that.").
  - `test_inheritance_question_refused`.
  - `test_advisor_cannot_use_heir_qa_403`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS, ruff clean.
- [ ] **Step 5: Commit** `feat(heirloom): heir goals, consent grants with revocation, heir preview and memory Q&A`

---

### Task 7: Forecast simulation engine

**Files:**
- Create: `simulation/engine.py`, `simulation/scenarios.py`, `tests/heirloom/test_engine.py`

**Interfaces:**
- Produces (frozen dataclasses): `AssetTerms(starting_value, attributable_debt, expected_return, annual_volatility, annual_fee, liquidatable_fraction: float|None, sale_delay_years: int|None, admin_delay_years, sale_cost_fraction, distribution_yield, admin_cost_fraction, partner_consent_required: bool, partner_consent_process_documented: bool)`; `ScenarioInput(terms, transfer_year: int, goal_year: int, goal_amount_today: float, inflation_rate: float = 0.025, horizon_years: int = 30, paths: int = 2000, seed: int = 40626, preset: StressPreset = "base")`; `YearQuantiles(year, p10, p50, p90)`; `ScenarioResult(value_nominal: list[YearQuantiles], value_real: list[YearQuantiles], cash_by_year: list[YearQuantiles], cash_at_goal: YearQuantiles, goal_nominal: float, p_cash_covers_goal: float|None, shortfall_share: float|None, sale_completion_year: int|None, transfer_after_goal: bool, admin_cost_at_transfer_p50: float, limitations: list[str], seed, model_version, input_hash: str)`.
- Produces: `scenarios.apply_preset(terms, preset) -> tuple[AssetTerms, float year1_shock_multiplier]`: `exit_delay_24m` → sale_delay +2; `shock_30_y1` → multiplier 0.70; `sale_haircut_20` → sale_cost +0.20; `base` → unchanged, 1.0.
- Produces: `engine.run_scenario(inp: ScenarioInput) -> ScenarioResult` and `engine.run_grid(base: ScenarioInput, transfer_years=(10,20,30), presets=PRESETS) -> dict[tuple[int,str], ScenarioResult]`; `MODEL_VERSION = "relay-forecast-1.0"`; `input_hash` = sha256 of canonical JSON of the input (+ model version).

Algorithm (the parts the tests don't fully determine):
```
rng = np.random.Generator(np.random.PCG64(seed))           # one generator per run_scenario call
Z = rng.standard_normal((paths, horizon))
drift = log(1 + mu - fee) - 0.5 * sigma**2
V[:,0] = starting_value; V[:,t] = V[:,t-1] * exp(drift + sigma*Z[:,t-1]); V[:,1] *= shock
real[:,t] = V[:,t] / (1+i)**t
cash_by_goal_year(G):                                      # vectorised over paths, for each G in 0..horizon
  if T > G: 0
  S = T + admin_delay + sale_delay
  sale = f * max(0, V[:,S] - debt) * (1 - sale_cost) if S <= G else 0
  dist = sum(d * V[:,t] for t in T..G)                      # distributions paid to the holder of the interest
  cash = max(0, sale + dist - admin_cost_fraction * V[:,T])
goal_nominal = goal_amount_today * (1+i)**goal_year
p_cash_covers_goal = mean(cash_at_goal >= goal_nominal)
unknown terms (f is None or sale_delay is None or (partner_consent_required and not documented))
  → p_cash_covers_goal = None, shortfall_share = None, limitation "Material access terms unknown — attorney review required"
quantiles: np.percentile(x, [10, 50, 90], method="linear")
```
Limitations always include "Illustrative assumptions; not a prediction", "Taxes not modeled", "Hypothetical transfer timing; no mortality modeled".

- [ ] **Step 1: Write failing tests** `test_engine.py` (use fixture LLC terms; goal 500000 today, goal_year 12, transfer 10 unless stated):
  - `test_fixed_seed_reproducible`: two runs → identical `cash_at_goal` and `value_nominal` lists, identical `input_hash`.
  - `test_quantiles_ordered`: every `YearQuantiles` has `p10 <= p50 <= p90`.
  - `test_zero_cash_before_transfer`: `cash_by_year[g].p90 == 0` for all `g < 10`.
  - `test_transfer_after_goal_is_zero_and_flagged`: transfer 20, goal 12 → `transfer_after_goal is True`, `cash_at_goal.p90 == 0`.
  - `test_delay_changes_cash_not_value`: base vs `exit_delay_24m` → `value_nominal` identical, base `cash_at_goal.p50` > delayed `cash_at_goal.p50`.
  - `test_debt_and_costs_subtracted_once`: with sigma 0, mu 0, d 0, admin 0, f 1, sale_cost 0.1, debt 1_000_000, start 5_000_000, delay 0, T=G=10 → `cash_at_goal.p50 == pytest.approx(3_600_000)`.
  - `test_inflation_conversion`: `goal_nominal == pytest.approx(500000 * 1.025**12)`; real value at year 0 equals nominal.
  - `test_cash_never_negative` (admin_cost_fraction 0.9, debt 10_000_000 → all cash quantiles ≥ 0).
  - `test_stress_lowers_liquidity`: `shock_30_y1` and `sale_haircut_20` each give `p_cash_covers_goal` ≤ base.
  - `test_unknown_terms_give_none`: `liquidatable_fraction=None` → `p_cash_covers_goal is None` and limitation text present.
  - `test_golden_story`: base `p_cash_covers_goal >= 0.70`; `exit_delay_24m` `p_cash_covers_goal <= 0.15`. (If the fixture misses these bands, tune only `distribution_yield`/`sale_delay` in the fixture, record the observed values in the test as exact `pytest.approx(…, abs=1e-12)` pins, and note the values in the commit message.)
  - `test_grid_shape`: `run_grid` returns 12 entries keyed `(T, preset)`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS (also time `run_grid`: must be < 0.5 s), ruff clean.
- [ ] **Step 5: Commit** `feat(heirloom): seeded transfer-aware forecast engine`

---

### Task 8: Classifier, readiness pipeline, insights and forecast endpoints

**Files:**
- Create: `services/classifier.py`, `services/readiness.py`, `services/insights.py`, `routers/insights.py`, `tests/heirloom/test_classifier.py`, `tests/heirloom/test_readiness.py`

**Interfaces:**
- Consumes: `engine.run_grid`, `consent.goal_view_for_advisor`, `events.register`.
- Produces: `AuthorizedAlignmentContext(family_ref, as_of_year, intent: IntentFacts|None, conflict: bool, asset: AssetFacts, goal: AdvisorGoalSummary|AdvisorGoalDetail|None, decision_refs: list[str], consent_revision: int)` built only by `readiness.build_context(session, family, intent, goal) -> AuthorizedAlignmentContext`.
- Produces: `classifier.classify(ctx: AuthorizedAlignmentContext, grid: dict[tuple[int,str], ScenarioResult]|None, threshold: float) -> list[InsightDraft]`. `InsightDraft{type: Literal["liquidity_gap","timing_gap","timing_review","legal_review","relationship_opportunity"], insight_key, title, summary, why_now, known: list[str], conditional: list[str], contact: list[str], headline_probability: float|None, headline_condition: str, scenario_rows: list[{transfer_year, preset, p, cash_p50, value_p50}], evidence: list[{kind, ref, label, status}], filter_tags: list[str], goal_ref: str|None, assumptions: dict}`. Order exactly: no goal → `[]`; intent None/unverified → `[relationship_opportunity]` (summary built from goal fields only); conflict → `[legal_review]`; goal year G = `horizon_max_years` (or `target_year - as_of_year`) missing → `[relationship_opportunity]` with `headline_condition="Insufficient modeling data: goal timing or amount not shared"` and `headline_probability=None`; eligible T = grid years ≤ G; none → `[timing_gap, timing_review]`; any eligible (T, preset) with `p` not None and `p < threshold` → `[liquidity_gap]` whose headline is the **lowest** p and whose condition names the preset and T (e.g. "if transfer occurred in year 10 and exit took 24 months longer"), with base p in `known`; all `p is None` → `[liquidity_gap]` with `headline_probability=None`, condition "Access terms unknown — attorney review"; else `[relationship_opportunity]` with `known` containing "No modeled mismatch under these assumptions". `filter_tags` map: liquidity_gap → `needs_parent_review, scenario_mismatch`; timing_gap → `heir_conversation, scenario_mismatch`; timing_review → `needs_parent_review`; legal_review → `legal_source_conflict`; relationship_opportunity → `heir_conversation`. Goal amount used = `amount_target` (detail) else `amount_band_mid` (summary). Evidence for liquidity/timing: estate instrument, intent, asset, latest verified decision on the asset (if any), goal (consented), forecast scenario ids.
- Produces: `readiness.recompute(session, family) -> RecomputeResult{created: int, kept: int, invalidated: int}` registered for events `estate_intent.*`, `decision.verified.v1`, `heir_goal.updated.v1`, `consent.changed.v1` (after the consent handler), `asset.terms_updated.v1`, `market_context.updated.v1`, `alignment.candidate_accepted.v1`. Persists `forecast_scenarios`/`forecast_results` per grid cell (cached in-process by `input_hash + consent_revision`); upserts `Insight` by `insight_key` (same `input_hash` keeps review_status; changed → new row `new`, old row `invalidated`); active insights not produced this run → `invalidated`.
- Produces: `insights.list_for_advisor(actor, session, status: str|None, tag: str|None) -> list[InsightDTO]` (excludes `invalidated` and any whose `consent_revision != family.consent_revision` when goal-derived — defensive double check); advisor only (heir/parent → 403). `insights.set_review(actor, session, insight_id, review_status: Literal["reviewed","dismissed"])`.
- Routes: `GET /families/{id}/insights?status=&tag=`, `POST /families/{id}/insights/{insight_id}/review {review_status}`, `GET /families/{id}/forecasts/{scenario_id}` (advisor; 404 if its goal is no longer consented) → `ScenarioResultDTO` (all `ScenarioResult` fields + `settings`, `computed_at`).

- [ ] **Step 1: Write failing tests** `test_classifier.py` (pure, with hand-built contexts and the real grid):
  - `test_no_goal_no_insights`, `test_unverified_intent_relationship_only` (summary contains no "LLC", "intend", "estate", "inherit").
  - `test_conflict_legal_review`, `test_goal_before_earliest_transfer_is_timing` (G=3 → types `["timing_gap","timing_review"]`, no liquidity_gap).
  - `test_golden_liquidity_gap_names_exit_delay`: G=12 → one `liquidity_gap`, `headline_probability <= 0.15`, condition mentions "24 months", `known` includes the base probability ≥ 0.70.
  - `test_foundation_no_mismatch`: G=25, amount 250000 → `[relationship_opportunity]` with "No modeled mismatch" in `known`.
  - `test_missing_timing_is_insufficient_data`.
  - `test_unknown_terms_no_reassuring_number`.
  `test_readiness.py` (API-level):
  - `test_no_flag_until_james_shares`: Sarah `GET /insights` → `[]`; James grants summary → one `liquidity_gap` whose evidence kinds ⊇ `{"estate_instrument","estate_intent","asset","goal","forecast"}` (the seeded LLC decision is still a candidate, so no `"decision"` yet); after Sarah verifies `decision-retain-llc`, evidence kinds also include `"decision"`. Evidence `kind` values used everywhere: `estate_instrument, estate_intent, asset, decision, goal, forecast`.
  - `test_goal_year_3_flips_to_timing` (James PATCH target_year 2029, horizon 2–3 → types `{timing_gap, timing_review}`; previous liquidity_gap gone).
  - `test_foundation_goal_recomputes` (PATCH to preset → only relationship_opportunity).
  - `test_revocation_removes_insight_and_forecast`: grant → insight + forecast id; revoke → `GET /insights` empty, `GET /forecasts/{id}` 404, graph has no goal node.
  - `test_superseding_letter_invalidates_asset_alert` (→ relationship_opportunity only).
  - `test_heir_insights_403`.
  - `test_review_status_persists_across_identical_recompute`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS, ruff clean.
- [ ] **Step 5: Commit** `feat(heirloom): deterministic classifier and background readiness pipeline`

---

### Task 9: Advisor actions, heir-safe text guard, asset terms

**Files:**
- Create: `services/heir_text_guard.py`, `services/actions.py`, `routers/actions.py`, `routers/assets.py`, `tests/heirloom/test_actions.py`

**Interfaces:**
- Produces: `heir_text_guard.find_violations(text: str, family_terms: list[str]) -> list[str]`; base terms `["inherit", "bequest", "estate", "beneficiar", "intended for", "trust", "llc", "will "]`, regex `\$\s?\d|\d[\d,]{3,}`; family terms = asset labels + instrument titles (case-insensitive). `HeirUnsafeText(ApiError 422, code "heir_unsafe_text")` lists hits.
- Produces: `actions.create(actor, session, insight_id, action_type, draft_text: str|None) -> AdvisorAction` (advisor; default draft from template; `heir_intro` drafts validated by guard); `actions.update(actor, session, action_id, status, draft_text=None, outcome_note=None)`. Transitions: draft→approved|cancelled, approved→completed|cancelled; else 409 `invalid_transition`; `completed` requires `outcome_note` (422 `outcome_required`). Creating/approving an action sets insight `review_status="actioned"`. Emits `advisor_action.updated.v1`.
- Templates (exact copy):
  - `parent_review`: "Agenda — review with Robert (and estate counsel if he wishes)\n1. Confirm the 2026 estate planning letter still reflects Robert's intent for the LLC interest.\n2. Review the operating agreement's partner-consent and sale provisions and how they would apply after a transfer.\n3. Discuss whether Robert wants the plan to address liquidity for whoever receives the interest.\nRobert's portfolio continues to be managed for Robert's own objectives; nothing here is a recommendation to change it."
  - `heir_intro`: "Hi James, thanks for sharing your plans to build a company. If it would help, I'd be glad to offer a no-pressure planning conversation about funding options and timing for your own goals. Best, Sarah" (must pass the guard).
- Produces: heir snapshot `invitations` = approved/completed `heir_intro` actions → `{from_display: "Sarah Lin", text, status}`.
- Produces: `PATCH /families/{id}/assets/{asset_id}/terms {sale_delay_years?, liquidatable_fraction?, partner_consent_process_documented?, distribution_yield?}` (advisor; validated ranges: delay 0..10, fraction 0..1 or null, yield 0..0.2) → emits `asset.terms_updated.v1` (pipeline recomputes).
- Routes: `POST /families/{id}/insights/{insight_id}/actions {action_type, draft_text?}`, `PATCH /families/{id}/actions/{action_id} {status, draft_text?, outcome_note?}`, `GET /families/{id}/actions`, `GET /families/{id}/activity` (advisor: actions + audit rows + domain events, newest first, max 50, no payload bodies).
- Produces: `AdvisorActionDTO{id, insight_id, insight_key, action_type, status, draft_text, outcome_note, created_at, updated_at}` for `GET /families/{id}/actions` (and the POST/PATCH responses). `insight_key` is joined from `advisor_actions.insight_id` → `insights.insight_key`. Actions are never re-pointed on recompute: an action keeps the `insight_id` it was created on, and clients group a flag's actions by `insight_key` across the rows a recompute creates. Client rule (Task 12 `ActionPanel`): the latest same-key action of a type is shown as the flag's action, except a `completed` action whose `updated_at` is earlier than the current row's `created_at` (the flag recurred after completion), which lets the advisor draft a new action for the recurrence. Completing an action sets its `updated_at` to the completion time.

- [ ] **Step 1: Write failing tests** `test_actions.py`:
  - `test_default_heir_intro_passes_guard`, `test_heir_intro_mentioning_llc_rejected_422`, `test_heir_intro_with_amount_rejected_422`.
  - `test_action_lifecycle` (draft→approved→completed with note; completed without note → 422; completed→draft → 409).
  - `test_heir_sees_invitation_only_after_approval` (James snapshot `invitations` empty for draft, one item after approve, text equals template).
  - `test_revocation_cancels_and_purges_unsent_drafts` (draft heir_intro → James revokes → action `cancelled`, `draft_text == ""`).
  - `test_actions_list_carries_insight_key` (create `parent_review` on the liquidity_gap insight → PATCH asset terms so the pipeline creates a new insight row → `GET /actions` returns the action with its original `insight_id` and `insight_key` equal to the new active row's `insight_key`).
  - `test_terms_patch_changes_flag`: set `sale_delay_years` 0 → liquidity_gap headline probability increases; set `liquidatable_fraction` null → headline None with "attorney review".
  - `test_parent_review_template_has_no_portfolio_change_recommendation` (contains "managed for Robert's own objectives").
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS, ruff clean.
- [ ] **Step 5: Commit** `feat(heirloom): advisor actions with heir-safe text guard and asset terms`

---

### Task 10: Integration ingest, providers, Neo4j adapter, migration + OpenAPI + contracts doc

**Files:**
- Create: `providers/protocols.py`, `providers/mocks.py`, `providers/registry.py`, `services/integrations.py`, `routers/integrations.py`, `graph/neo4j_repo.py`, `scripts/emit_pg_migration.py`, `scripts/export_openapi.py`, `supabase/migrations/20261010160000_heirloom_domain.sql`, `contracts/heirloom.openapi.json`, `docs/integration_contracts.md`, `tests/heirloom/test_integrations.py`, `tests/heirloom/test_neo4j_repo.py`, `tests/heirloom/test_artifacts.py`
- Modify: `services/seed.py` (use registry's decision provider), `graph/factory.py` (Neo4j selection + degraded fallback)

**Interfaces:**
- Produces Protocols mirroring blueprint §11: `FinancialDataProvider.get_asset_snapshot(family_ref) -> list[AssetSnapshot]`, `.get_holdings(family_ref) -> list[Holding]`; `MarketContextProvider.get_events(asset_ref) -> list[SourcedMarketEvent{title, url, published_at, summary, proposed_stress}]`; `DecisionAnalysisProvider.extract_decisions(source: MeetingSource{source_ref, text, document_date}) -> list[CandidateDecision]` (shape = blueprint §5 example JSON); `AlignmentAnalysisProvider.propose_insights(ctx: AuthorizedAlignmentContext) -> list[CandidateInsight]` (shape = blueprint §9 example JSON). Mocks: `MockFinancialDataProvider`, `MockMarketContextProvider`, `MockDecisionAnalysisProvider` (deterministic: finds fixture locator span in text), `RuleBasedAlignmentProvider` (wraps `classifier.classify`). `registry.get_providers() -> Providers` is the single swap point (env `HEIRLOOM_PROVIDER_*` names; only `mock` implemented).
- Produces routes (header `X-Integration-Token` must equal `integration_token`, else 401): `POST /api/v1/integrations/decisions/ingest` (CandidateDecision; unique `external_event_id` → duplicate returns 200 `{status:"duplicate"}`; always stored as `candidate`; missing rationale stored as `null`); `POST /api/v1/integrations/market-context/ingest` (SourcedMarketEvent + `asset_ref`; stored; emits `market_context.updated.v1`); `POST /api/v1/integrations/alignment/ingest` (CandidateInsight) → validation: family exists; `transfer_intent_id` verified & current; `heir_goal_id` consented at current revision; every evidence id exists in family and is advisor-authorized; deterministic classifier yields an insight of a compatible type for the same pair. Failure → 422 with `errors[].code ∈ {unknown_family, intent_not_verified, goal_not_consented, unknown_evidence, classifier_disagrees}` + audit. Success → explanation stored on the matching insight as `payload.agent_explanation` with label "agent explanation (unverified)".
- Produces: `Neo4jGraphRepository(driver)` implementing `GraphRepository` with module constants `UPSERT_NODE = "MERGE (n:Node {record_id: $record_id, organization_id: $org, family_id: $family_id}) SET n += $props, n.kind = $kind ..."`, `UPSERT_EDGE`, `DELETE_FAMILY`, `READ_FAMILY` — every query parameterized and scoped by `$org` + `$family_id`; uses `session.execute_write`. `factory.get_graph_repo()` returns Neo4j repo when `neo4j_uri` set and `driver.verify_connectivity()` succeeds, else memory repo with `degraded=["graph"]` (surfaced in `meta.degraded`).
- Produces: `emit_pg_migration.main()` writes `CREATE SCHEMA IF NOT EXISTS heirloom;` + `CreateTable`/`CreateIndex` compiled for `postgresql` + `ALTER TABLE heirloom.<t> ENABLE ROW LEVEL SECURITY;` for every table (no policies = deny for `anon`/`authenticated`; backend uses the service key). `export_openapi.main()` writes `contracts/heirloom.openapi.json` from `create_app().openapi()` (sorted keys).
- `docs/integration_contracts.md`: sections Teammate A (RequestContext contract, Clerk claim mapping, how to mount screens in `/advisor|/parent|/heir`, the one-line import), Teammate B (each provider protocol + ingest endpoint with request/response JSON examples, validation codes, idempotency), Env vars, Mock vs real table, open TODOs (Clerk org claim name; Plaid account→asset ref reconciliation; Neo4j instance).

- [ ] **Step 1: Write failing tests** `test_integrations.py`:
  - `test_ingest_requires_token_401`, `test_decision_ingest_idempotent` (second post → `duplicate`, one row), `test_ingested_decision_is_candidate_even_if_payload_says_verified`, `test_missing_rationale_stored_null`.
  - `test_alignment_rejects_unconsented_goal_422` (`goal_not_consented`), `test_alignment_rejects_unverified_intent_422`, `test_alignment_rejects_unknown_evidence_422`, `test_alignment_accepted_adds_unverified_explanation`.
  - `test_market_event_ingest_triggers_recompute` (revision increments; event appears in advisor snapshot `assets[].market_events`).
  `test_neo4j_repo.py` (fake driver recording `(query, params)`):
  - `test_all_queries_parameterized_and_scoped`: every recorded query contains `$org` and `$family_id`, no f-string-interpolated ids (assert record ids appear only in params).
  - `test_factory_falls_back_when_unreachable` (`neo4j_uri="bolt://127.0.0.1:1"` → memory repo, `degraded == ["graph"]`; snapshot meta shows it).
  `test_artifacts.py`:
  - `test_pg_migration_up_to_date`: regenerated SQL equals committed file.
  - `test_openapi_up_to_date`: regenerated JSON equals committed file.
- [ ] **Step 2:** FAIL. **Step 3:** Implement; run `.venv/bin/python -m app.heirloom.scripts.emit_pg_migration` and `... export_openapi` to create the committed artifacts. **Step 4:** PASS, ruff clean.
- [ ] **Step 5: Commit** `feat(heirloom): integration ingest with validation, providers, neo4j adapter, contracts`

---

### Task 11: Frontend foundation — deps, tokens, client, session, relay shell, persona picker

**Files:**
- Modify: `frontend/package.json` (deps `@xyflow/react@^12.12.0`; devDeps `vitest@^5.0.3`, `@vitejs/plugin-react@^6.1.2`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`; script `"test": "vitest run"`)
- Create: `vitest.config.mts`, `vitest.setup.ts`, `features/heirloom/session.ts`, `api/client.ts`, `types/contracts.ts`, `hooks/useRelayQuery.ts`, `hooks/useRevisionPoll.ts`, `styles/tokens.module.css`, `components/StateViews.tsx`, `components/ModeBadge.tsx`, `components/StatusLabel.tsx`, `components/PersonaPicker.tsx`, `app/relay/layout.tsx`, `app/relay/page.tsx`, `app/relay/{advisor,parent,heir}/page.tsx` (each renders a placeholder screen until Tasks 12–15), `__tests__/client.test.ts`, `__tests__/session.test.ts`, `__tests__/stateViews.test.tsx`

**Interfaces:**
- Before coding: read `node_modules/next/dist/docs/01-app/03-api-reference/01-directives/use-client.md`, `01-getting-started/13-fonts.md`, `03-api-reference/03-file-conventions/layout.md`. Extract `~/Downloads/kalshi-brand-kit.zip` into the scratchpad and view the `03 Brand Assets` PNGs to calibrate spacing/type (do not copy logos into the repo).
- Produces: `session.ts`: `getSession(): RelaySession|null`, `setSession(s: RelaySession)`, `clearSession()` — `sessionStorage` key `heirloom.relay.session`, all access in try/catch. `RelaySession{token, familyId, person: {id, displayName, role}}`.
- Produces: `api/client.ts`: `class RelayApiError extends Error {status: number; code: string}`; `createRelayClient(opts: {baseUrl: string; getToken: () => string|null; onUnauthenticated?: () => void; fetchImpl?: typeof fetch}) -> {get<T>(path): Promise<Envelope<T>>, post<T>(path, body?), put<T>(path, body), patch<T>(path, body)}` — sends `Authorization: Bearer`, `cache: "no-store"`; non-2xx → throws `RelayApiError` from `errors[0]`; 401 → calls `onUnauthenticated` then throws; network failure → `RelayApiError(0, "network_error")`. Default export `relay` built from `process.env.NEXT_PUBLIC_API_URL` whose `onUnauthenticated` clears the session and navigates to `/relay`.
- Produces: `types/contracts.ts` — TS mirrors of every DTO in Tasks 3–9 (names identical to the pydantic models), `Envelope<T>{data: T; meta: Meta; errors: ApiErrorItem[]}`.
- Produces: `useRelayQuery<T>(path: string|null, deps?: unknown[]) -> {data: T|undefined, meta, error: RelayApiError|undefined, loading: boolean, reload(): void}`; `useRevisionPoll(familyId: string|null, onChange: () => void, intervalMs = 2500)` (polls `/families/{id}/revision`, calls `onChange` when `revision` or `consent_revision` differs from last seen; pauses when `document.hidden`).
- Produces components: `<LoadingState label/>`, `<EmptyState title body/>`, `<ErrorState error onRetry/>`, `<ModeBadge mode/>` ("Mock data mode"), `<StatusLabel tone label date? scope?/>` (small caps "VERIFIED · 15 APR 2026 · ADVISOR-ONLY").
- Produces pages: `/relay` = `<PersonaPicker/>` (three cards: "Sarah Lin — Lead advisor", "Robert Morgan — Client", "James Morgan — Adult family member"; banner "Synthetic Morgan family · demo mode · no real client data"; **Reset demo** button → `POST /demo/reset`); choosing a persona → `POST /demo/sessions`, `setSession`, `router.push("/relay/{advisor|parent|heir}")`. `app/relay/layout.tsx` loads Inter (`next/font/google`, `variable: "--font-inter"`), renders a slim top bar "Heirloom Relay" + current persona + "Switch persona" link + ModeBadge, and a comment `// TEMPORARY chrome for the /relay namespace; teammate A's shells will host the screens.`
- Tokens (`tokens.module.css`, `:global(:root)`): `--hr-bg:#FFFFFF; --hr-ink:#0A0A0A; --hr-muted:#6B6B6B; --hr-line:#E6E6E6; --hr-surface:#F7F7F7; --hr-accent:#00B67A; --hr-accent-ink:#007A52; --hr-accent-soft:#E6F8F1; --hr-warn:#B26A00; --hr-warn-soft:#FFF4E0; --hr-danger:#C2352B; --hr-lock:#8A8A8A; --hr-radius:12px; --hr-radius-sm:8px;` spacing scale 4/8/12/16/24/32/48; dark-mode block under `@media (prefers-color-scheme: dark)` swaps bg `#0B0B0B`, ink `#F5F5F5`, line `#262626`, accent `#00DD94`.

- [ ] **Step 1: Write failing tests**:
  - `client.test.ts`: `sends bearer and no-store` (mock fetch asserts header + `cache`); `throws RelayApiError with server code` (envelope `errors:[{code:"forbidden_for_role"}]`, status 403); `401 triggers onUnauthenticated`; `network failure becomes network_error`.
  - `session.test.ts`: round-trip; `getSession` returns null when `sessionStorage.getItem` throws.
  - `stateViews.test.tsx`: `ErrorState` renders message and calls `onRetry` on click.
- [ ] **Step 2:** `npx vitest run` → FAIL. **Step 3:** Implement. **Step 4:** `npx vitest run && npx tsc --noEmit && npm run lint` → PASS.
- [ ] **Step 5: Boot check:** start backend `cd backend && HEIRLOOM_MODE=demo .venv/bin/uvicorn app.main:app --port 8000` and `cd frontend && npm run dev`; open `http://localhost:3000/relay` in Chrome. Expected: picker renders and picking Sarah lands on `/relay/advisor`. **If the root `ClerkProvider` blocks rendering without `frontend/.env.local` keys**, do not edit A's layout: stop and report to the user (options: shared dev Clerk keys in `.env.local`, or Clerk keyless dev mode).
- [ ] **Step 6: Commit** `feat(relay-ui): frontend foundation, typed client, demo persona picker`

---

### Task 12: Advisor flags — header, feed, card, sheet, charts, evidence path/drawer, actions

**Files:**
- Create: `components/FamilyHeader.tsx`, `FlagFeed.tsx`, `FlagCard.tsx`, `FlagSheet.tsx`, `EvidencePath.tsx`, `EvidenceDrawer.tsx`, `ValueFanChart.tsx`, `AccessibleCashChart.tsx`, `ExplainCalculation.tsx`, `ActionPanel.tsx`, `AssetTermsEditor.tsx`, `screens/AdvisorScreen.tsx` (flags region), CSS modules, `__tests__/flagCard.test.tsx`, `__tests__/flagSheet.test.tsx`, `__tests__/charts.test.tsx`
- Modify: `app/relay/advisor/page.tsx` (render `<AdvisorScreen/>`)

**Interfaces:**
- Before writing charts: invoke the `dataviz` skill and follow it (palette from tokens; value band = ink at 12% + median line ink; accessible cash = accent band + accent median; goal line warn dashed; transfer marker vertical muted dashed; shortfall zone = warn-soft rect where cash p50 < goal at G).
- Consumes: `AdvisorSnapshot`, `InsightDTO`, `ScenarioResultDTO`, `EvidenceDTO`, routes from Tasks 4, 8, 9.
- Produces: `<FamilyHeader snapshot/>` — family name, "Advisor: Sarah Lin", synthetic assets under advisement (sum of values, labeled "synthetic"), coverage chips ("4 of 5 decisions verified", "1 of 3 assets with verified intent", "Heirs connected 0 of 1"), open flags. No "$ at risk".
- Produces: `<FlagFeed insights onSelect/>` with filter chips `Needs parent review | Heir conversation | Legal source conflict | Scenario mismatch` (map to `filter_tags`), empty state "No open flags. James has not shared any current goals." when `snapshot.goal_sharing == "not_shared"`, else "No open flags under current assumptions.".
- Produces: `<FlagCard insight onOpen/>` — big tabular `headline_probability` as "6%" (or "Unknown" when null) with caption = `headline_condition`; title; `why_now`; three evidence chips; StatusLabel "REVIEW REQUIRED · ILLUSTRATIVE".
- Produces: `<FlagSheet insightId onClose/>` (right side sheet): `<EvidencePath evidence onStep/>` breadcrumbs `Estate instrument → Named interest → Asset & liquidity → Robert's rationale → James's goal → Modeled transfer → Flag → Action`, each step opens `<EvidenceDrawer recordRef/>` (fetches `/evidence/{ref}`); transfer-year toggle 10/20/30 and preset row (Base / Exit +24 mo / −30% shock / Sale haircut 20%) selecting a `scenario_rows` entry → fetch `/forecasts/{id}`; `<ValueFanChart result transferYear goalYear/>` titled "Paper value of the interest (P10–P90)"; `<AccessibleCashChart result goalYear goalNominal/>` titled "Accessible cash by year, if transfer occurred in year N"; `<ExplainCalculation result/>` (paths, seed, model version, input hash, assumptions table, limitations, "Illustrative assumptions — not a prediction, not advice"); `<ActionPanel insight/>` with "Review plan with client" (`parent_review`) and "Invite consenting heir to a meeting" (`heir_intro`, hidden for legal_review) showing draft text, Approve / Mark completed (outcome note) / Cancel, footer "Nothing is sent. Drafts stay inside Heirloom Relay for your review."; `<AssetTermsEditor asset onSaved/>` inside the asset evidence drawer (sale delay, liquidatable fraction, partner-consent documented).
- Sheet closes automatically when its insight disappears after a revision change.

- [ ] **Step 1: Write failing tests**:
  - `flagCard.test.tsx`: renders "6%" and condition; renders "Unknown" when `headline_probability` null.
  - `flagSheet.test.tsx`: `closes when insight no longer in list` (rerender FlagFeed/sheet container with empty list → sheet gone and empty-state copy "James has not shared any current goals." shown) — Review Focus item 1.
  - `charts.test.tsx`: ValueFanChart renders one `<line data-testid="transfer-marker">` at the transfer year x-position; AccessibleCashChart renders `data-testid="shortfall-zone"` only when cash p50 at goal < goal nominal.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** vitest + tsc + lint PASS.
- [ ] **Step 5: Browser check:** as Sarah, with James sharing summary (via API or James tab), the flag appears; open sheet; toggle Exit +24 mo → value chart unchanged, cash chart collapses. Screenshot.
- [ ] **Step 6: Commit** `feat(relay-ui): advisor flag feed, evidence path and forecast drill-down`

---

### Task 13: Advisor graph and review tabs

**Files:**
- Create: `components/FamilyGraph.tsx`, `graphNodes.tsx`, `IntentReview.tsx`, `DecisionReview.tsx`, `ActivityLog.tsx`, CSS modules, `__tests__/familyGraph.test.tsx`, `__tests__/reviews.test.tsx`
- Modify: `screens/AdvisorScreen.tsx` (graph section + tabs `Flags | Knowledge graph | Estate intents | Decision memory | Activity`, revision polling wired via `useRevisionPoll`)

**Interfaces:**
- Consumes: `GraphDTO`, `EvidenceDTO`, routes from Tasks 4–5, 9.
- Produces: `<FamilyGraph familyId/>` — `@xyflow/react` `ReactFlow` with `nodeTypes` for `person, asset, instrument, intent, decision, goal, forecast, insight, restriction`; deterministic layered layout (column by kind: person → instrument/intent → asset/restriction → decision → goal/forecast/insight); lock badge on `advisor_only`/`internal_parent_advisor`; candidate/superseded nodes dashed with StatusLabel; `INTENDED_FOR` edge labeled "intended for (revocable)"; "As of" date input → refetch `?as_of=`; node click → `EvidenceDrawer`. Import `@xyflow/react/dist/style.css` in the component.
- Produces: `<IntentReview snapshot/>` — per instrument: status label (draft / verified document / superseded / unknown conflict), document excerpt beside extracted intent fields (asset, beneficiary, allocation, conditions, confidence), Verify / Reject buttons, "Import synthetic amendment" button (`fixture_ref: "conflicting_amendment"`), "Mark superseded".
- Produces: `<DecisionReview snapshot/>` — candidates first: transcript excerpt with `start_seconds–end_seconds`, extracted action/rationale/alternatives/confidence, Verify (optional edited rationale) / Reject (note required) / Annotate; verified list with dates; rationale null → "Rationale not documented".
- Produces: `<ActivityLog familyId/>` — `/activity` rows.

- [ ] **Step 1: Write failing tests**:
  - `familyGraph.test.tsx` (mock client): renders a node per DTO node and a lock badge for advisor-only nodes; renders no node for ids absent from the DTO.
  - `reviews.test.tsx`: Reject without note shows inline error and makes no request; candidate with null rationale shows "Rationale not documented".
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** vitest + tsc + lint PASS.
- [ ] **Step 5: Browser check:** verify `decision-retain-llc` in Decision memory → graph node turns solid; click the `INTENDED_FOR` edge's intent node → drawer shows the dated 2026 letter excerpt; click the decision → transcript excerpt with 1:53–2:28. Screenshot.
- [ ] **Step 6: Commit** `feat(relay-ui): interactive family graph and verification tabs`

---

### Task 14: Parent screen

**Files:**
- Create: `components/ParentSharing.tsx`, `HeirPreview.tsx`, `screens/ParentScreen.tsx`, CSS, `__tests__/parent.test.tsx`
- Modify: `app/relay/parent/page.tsx`

**Interfaces:**
- Consumes: `ParentSnapshot`, `PUT /consents/{decision_id}`, `GET /heir-preview`, `POST /decisions/{id}/request-correction`, `POST /estate-intents/{id}/counsel-reviewed`.
- Produces: header "Your story. Your choice." + "Welcome, Robert. Decide which explanations James may see. Nothing is shared unless you switch it on."; "What I want to preserve" list from `preserve_values`; decision history with per-decision switch "Share this explanation with James" (only verified decisions; candidates show "Awaiting Sarah's verification"), "Request a correction" (note); fixed rows "Estate-plan details — Off (not shareable in this pilot)" and "Account balances — Not available in this pilot"; `<HeirPreview/>` "Exactly what James sees" (renders `/heir-preview` with the same `ApprovedMemory` component the heir uses); estate intent card "Your 2026 estate planning letter" with "Mark reviewed with counsel" (copy: "Recording a review is not a legal execution or amendment."). No portfolio-change suggestions anywhere.

- [ ] **Step 1: Write failing test** `parent.test.tsx`: toggling a share switch calls `PUT /consents/{id}` with `{scope:"decision_excerpt", recipient_person_id: <james id>, active:true}` and refreshes the preview; candidate decisions render no switch.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** vitest + tsc + lint PASS.
- [ ] **Step 5: Commit** `feat(relay-ui): parent sharing controls and exact heir preview`

---

### Task 15: Heir screen

**Files:**
- Create: `components/GoalCheckIn.tsx`, `GoalSharing.tsx`, `ApprovedMemory.tsx`, `MemoryAsk.tsx`, `InvitationCard.tsx`, `screens/HeirScreen.tsx`, CSS, `__tests__/heir.test.tsx`
- Modify: `app/relay/heir/page.tsx`

**Interfaces:**
- Consumes: `HeirSnapshot`, `PATCH /heir-goals/{id}`, `PUT /consents/{goal_id}`, `POST /memory/ask`.
- Produces: header "Your future, on your terms." + "Welcome, James. Your goals stay yours. You choose whether Sarah, your family's advisor, can help."; `<GoalCheckIn goal onSaved/>` (kind select incl. business/home/education/philanthropy/wealth_preservation/other, narrative, optional amount, target year, next milestone; preset buttons "Start a company" and "Endow a foundation"; line "Your information is private unless you choose to share it."; on 409 `version_conflict` shows "This goal was updated in another window." with Reload); `<GoalSharing sharing/>` two switches "Share a goal summary with Sarah (type, rough amount, timeframe)" and "Also share full details (exact amount, year, milestone, your notes)" — independent of anything about family records; 2–3 `planning_prompts`; `<ApprovedMemory decisions/>` with citations and "Verified by Sarah Lin" + empty state "Robert hasn't shared any decision explanations yet."; `<MemoryAsk/>` (suggested question "Why was family control important?"; refusal reasons shown verbatim); `<InvitationCard/>` when `invitations` non-empty. No inheritance wording; no asset names, values or beneficiary info.

- [ ] **Step 1: Write failing tests** `heir.test.tsx`: 409 renders the conflict message with a Reload button (Review Focus item 2); turning detail on while summary off sends detail grant and both switches show on after refresh; refused answer renders its reason text; rendered heir screen text (with a full mocked snapshot) contains none of "inherit", "LLC", "$5", "beneficiary".
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** vitest + tsc + lint PASS.
- [ ] **Step 5: Commit** `feat(relay-ui): heir goal check-in, sharing controls and approved memory`

---

### Task 16: Docs, env examples, full verification and golden demo

**Files:**
- Create: `README_HEIRLOOM.md`
- Modify: `backend/.env.example`, `frontend/.env.example` (append commented optional `HEIRLOOM_*` / `NEO4J`-related vars; nothing required), `docs/integration_contracts.md` (final mock-vs-real table)

**Interfaces:**
- `README_HEIRLOOM.md`: what it is (one paragraph), run commands (backend venv + uvicorn, frontend dev, `/relay`), demo script (8 beats matching spec Verification), test commands, regenerate artifacts commands, mock vs real table (Clerk mode: implemented, unverified without keys; Neo4j adapter: implemented, tested with fake driver only; Plaid/Bright Data/decision/alignment agents: mocked; Supabase migration: generated, not applied), known risks.

- [ ] **Step 1:** Run the full suites: `cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q` and `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`. Expected: all pass; record counts.
- [ ] **Step 2:** Golden demo in Chrome (claude-in-chrome; record a GIF `heirloom_relay_golden_demo.gif`, screenshots per beat), two tabs (Sarah, James):
  1. Reset demo → Sarah: Decision memory → verify "Keep the family LLC interest" → transcript excerpt shown.
  2. Graph → intent node → 2026 letter excerpt "advisor-only".
  3. James tab: share summary; goal shows $500K / 2038 → Sarah's tab gets a flag within ~3 s without reload.
  4. Open flag: three+ evidence links; Exit +24 mo → value steady, cash collapses; 10→20 toggle shows "transfer after goal" explanation.
  5. Draft "Review plan with client" and "Invite consenting heir"; approve the invite → James sees invitation, no estate details.
  6. James: target year 2029 → Sarah sees timing/independent-financing flag; foundation preset → no-mismatch relationship flag; sharing off → Sarah's flags gone, "James has not shared any current goals."; also confirm via `curl -H "Authorization: Bearer <sarah token>" localhost:8000/api/v1/families/<id>/insights` returns `[]`.
  7. Robert: share "Keep the family LLC interest" explanation → heir preview updates → James asks "Why was family control important?" → cited answer; "How much will I inherit?" → refusal.
  8. Sarah: Import synthetic amendment → verify → legal source conflict flag.
- [ ] **Step 3:** Fix anything found (with a regression test where applicable), re-run Step 1.
- [ ] **Step 4: Commit** `docs(heirloom): README, env examples, demo evidence`
- [ ] **Step 5:** Request whole-branch review (superpowers:requesting-code-review), then deliver the handoff report: (a) file-by-file changes, (b) commands, (c) screenshots/GIF, (d) test results, (e) adapter contracts, (f) mock vs real, (g) risks/blockers.
