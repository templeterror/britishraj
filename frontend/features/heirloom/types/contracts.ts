// TypeScript mirrors of the Heirloom Relay API DTOs (plan Tasks 3-9).
// Names match the pydantic models. Where the plan fixes only a model's name and
// not every field, the shape below follows the domain model (Task 2) and is to be
// reconciled with contracts/heirloom.openapi.json once the backend track merges.

// ---- Envelope ---------------------------------------------------------------

export type RelayMode = "demo" | "clerk";

export interface Meta {
  revision: number;
  consent_revision: number;
  mode: RelayMode;
  degraded: string[];
}

export interface ApiErrorItem {
  code: string;
  message: string;
}

export interface Envelope<T> {
  data: T;
  meta: Meta;
  errors: ApiErrorItem[];
}

// ---- Identity, sessions (Task 3) --------------------------------------------

export type FamilyRole = "advisor" | "parent" | "adult_heir";
export type DemoPersona = "sarah" | "robert" | "james" | "other_advisor";

export interface PersonRef {
  id: string;
  display_name: string;
  role: FamilyRole;
}

export interface DemoSessionDTO {
  token: string;
  family_id: string;
  person: PersonRef;
}

/** What the browser keeps for the current demo persona. */
export interface RelaySession {
  token: string;
  familyId: string;
  person: { id: string; displayName: string; role: FamilyRole };
}

export interface RevisionDTO {
  revision: number;
  consent_revision: number;
}

export interface MeFamilyDTO {
  family_id: string;
  display_name: string;
  role: FamilyRole;
}

// ---- Shared record shapes (Task 4) ------------------------------------------

export interface FamilyDTO {
  id: string;
  display_name: string;
  as_of_year: number;
}

export interface PersonDTO {
  id: string;
  ref: string;
  display_name: string;
  role: FamilyRole;
  age: number | null;
}

export interface AssetTermsDTO {
  expected_return: number;
  annual_volatility: number;
  annual_fee: number;
  liquidatable_fraction: number | null;
  sale_delay_years: number | null;
  admin_delay_years: number;
  sale_cost_fraction: number;
  distribution_yield: number;
  admin_cost_fraction: number;
  partner_consent_required: boolean;
  partner_consent_process_documented: boolean;
}

export interface MarketEventDTO {
  title: string;
  url: string;
  published_at: string;
  proposed_stress: StressPreset | null;
}

export interface AssetDTO {
  id: string;
  ref: string;
  label: string;
  asset_kind: string;
  liquidity_class: string;
  value: number;
  liabilities: number;
  terms: AssetTermsDTO;
  market_events: MarketEventDTO[];
}

export type InstrumentStatus = "draft" | "reported" | "verified" | "superseded" | "contested";
export type IntentStatus = "proposed" | "verified" | "superseded" | "contested";

export interface InstrumentDTO {
  id: string;
  ref: string;
  title: string;
  kind: string;
  status: InstrumentStatus;
  effective_date: string;
  revocable: boolean;
  counsel_reviewed_at: string | null;
  source_title: string;
  source_excerpt: string | null;
  source_version: number;
}

export interface IntentDTO {
  id: string;
  ref: string;
  instrument_ref: string;
  asset_ref: string;
  beneficiary_id: string;
  beneficiary_display_name: string;
  allocation: string;
  conditions: string[];
  status: IntentStatus;
  advisor_verified: boolean;
  verified_by_display: string | null;
  verification_notes: string | null;
  confidence: number | null;
  valid_from: string | null;
  valid_to: string | null;
  counsel_reviewed_at: string | null;
}

export type DecisionStatus = "candidate" | "verified" | "rejected";

export interface SourceLocator {
  start_seconds?: number;
  end_seconds?: number;
  quoted_span?: string;
  [key: string]: unknown;
}

export interface DecisionDTO {
  id: string;
  ref: string;
  decision_date: string;
  asset_ref: string | null;
  action: string;
  rationale: string | null;
  alternatives: string[];
  verification_status: DecisionStatus;
  rationale_edited: boolean;
  advisor_note: string | null;
  valid_to: string | null;
  confidence: number | null;
  source_title: string | null;
  locator: SourceLocator | null;
  verified_by_display: string | null;
  shared_with_heir: boolean;
}

// ---- Heir goals, consent (Task 6) -------------------------------------------

export type GoalKind =
  | "business"
  | "home"
  | "education"
  | "philanthropy"
  | "wealth_preservation"
  | "other";
export type GoalFundingSource = "unknown" | "savings" | "family" | "external";

export interface GoalInput {
  goal_kind: GoalKind;
  description_private: string;
  amount_target: number | null;
  target_year: number | null;
  horizon_min_years: number | null;
  horizon_max_years: number | null;
  milestone: string | null;
  goal_funding_source?: GoalFundingSource;
}

export interface GoalPatch extends Partial<GoalInput> {
  version: number;
}

export interface HeirGoalView {
  goal_id: string;
  ref: string;
  goal_kind: GoalKind;
  description_private: string;
  amount_target: number | null;
  target_year: number | null;
  horizon_min_years: number | null;
  horizon_max_years: number | null;
  milestone: string | null;
  goal_funding_source: GoalFundingSource;
  version: number;
}

export interface AdvisorGoalSummary {
  goal_id: string;
  kind: GoalKind;
  horizon_band: string;
  amount_band: string;
  amount_band_mid: number;
  horizon_max_years: number | null;
}

export interface AdvisorGoalDetail extends AdvisorGoalSummary {
  amount_target: number | null;
  target_year: number | null;
  milestone: string | null;
  description: string;
}

export type GoalSharingLevel = "not_shared" | "summary" | "detail";
export type ShareScope =
  | "goal_summary"
  | "goal_detail"
  | "decision_excerpt"
  | "estate_intent"
  | "balances";

export interface ConsentPutBody {
  scope: ShareScope;
  recipient_person_id: string;
  active: boolean;
}

export interface ConsentGrantDTO {
  resource_id: string;
  resource_type: "heir_goal" | "decision";
  share_scope: ShareScope;
  recipient_person_id: string;
  active: boolean;
  revision: number;
}

export interface ConsentState {
  grant: ConsentGrantDTO;
  consent_revision: number;
}

export interface HeirDecisionView {
  decision_id: string;
  date: string;
  title: string;
  rationale: string | null;
  source_title: string | null;
  locator: SourceLocator | null;
  verified_by_display: string | null;
  asset_kind: string | null;
}

export interface HeirPreviewDTO {
  approved_decisions: HeirDecisionView[];
}

export interface MemoryMatch {
  decision_id: string;
  title: string;
  date: string;
  excerpt: string | null;
  source_title: string | null;
  locator: SourceLocator | null;
  verified_by_display: string | null;
  score: number;
}

export interface MemoryAnswer {
  status: "answered" | "refused";
  reason: string | null;
  matches: MemoryMatch[];
}

export interface MemoryAskBody {
  question: string;
}

// ---- Snapshots (Task 4) -----------------------------------------------------

export interface CoverageDTO {
  decisions_verified: number;
  decisions_total: number;
  assets_with_verified_intent: number;
  assets_total: number;
  heirs_connected: number;
  heirs_total: number;
}

export interface AdvisorSnapshot {
  family: FamilyDTO;
  advisor: PersonRef;
  people: PersonDTO[];
  assets: AssetDTO[];
  instruments: InstrumentDTO[];
  intents: IntentDTO[];
  decisions: DecisionDTO[];
  goal_sharing: GoalSharingLevel;
  shared_goals: Array<AdvisorGoalSummary | AdvisorGoalDetail>;
  coverage: CoverageDTO;
  open_flags: number;
}

export interface ParentSnapshot {
  family: FamilyDTO;
  me: PersonRef;
  assets: AssetDTO[];
  decisions: DecisionDTO[];
  intents: IntentDTO[];
  preserve_values: string[];
  heirs: Array<{ person_id: string; display_name: string }>;
  sharing: {
    decision_excerpts: number;
    estate_intent: "off";
    balances: "not_available_in_pilot";
  };
}

export interface InvitationView {
  from_display: string;
  text: string;
  status: ActionStatus;
}

export interface HeirSnapshot {
  family: { id: string; display_name: string };
  me: PersonRef;
  /**
   * `person_id` is the recipient of the goal-sharing grants (PUT /consents requires it). The plan's
   * HeirSnapshot carries only `display_name`; the backend needs to add the id (see Task 15 report).
   */
  advisor: { display_name: string; person_id?: string };
  my_goals: HeirGoalView[];
  sharing: { advisor_summary: boolean; advisor_detail: boolean };
  approved_decisions: HeirDecisionView[];
  invitations: InvitationView[];
  planning_prompts: string[];
}

// ---- Graph, evidence (Task 4) -----------------------------------------------

export type GraphClassification =
  | "internal_parent_advisor"
  | "private_heir"
  | "advisor_approved_goal"
  | "authorized_heir_history"
  | "family_member"
  | "advisor_only";

export type GraphNodeKind =
  | "person"
  | "asset"
  | "instrument"
  | "intent"
  | "decision"
  | "goal"
  | "forecast"
  | "insight"
  | "restriction";

export type EvidenceStatus = "verified" | "candidate" | "superseded" | "contested" | "unknown";

export interface GNode {
  record_id: string;
  label: string;
  kind: GraphNodeKind;
  classification: GraphClassification;
  valid_from: string | null;
  valid_to: string | null;
  evidence_status: EvidenceStatus;
  props: Record<string, unknown>;
}

export interface GEdge {
  type: string;
  source_id: string;
  target_id: string;
  valid_from: string | null;
  valid_to: string | null;
  classification: GraphClassification;
}

export interface GraphDTO {
  nodes: GNode[];
  edges: GEdge[];
  evidence_refs: string[];
  revision: number;
}

export interface EvidenceDTO {
  record_ref: string;
  title: string;
  kind: EvidenceKind;
  status: string;
  qualifier: string | null;
  document_title: string | null;
  document_date: string | null;
  excerpt: string | null;
  locator: SourceLocator | null;
}

// ---- Verification (Task 5) --------------------------------------------------

export interface ImportIntentBody {
  fixture_ref: "conflicting_amendment";
}

export interface VerifyIntentBody {
  verified: boolean;
  notes: string | null;
  source_version: number;
}

export interface InstrumentStatusBody {
  status: "superseded";
}

export interface VerifyDecisionBody {
  approved: boolean;
  edited_rationale: string | null;
  note: string | null;
}

export interface NoteBody {
  note: string;
}

// ---- Forecast, insights (Tasks 7-8) -----------------------------------------

export type StressPreset = "base" | "exit_delay_24m" | "shock_30_y1" | "sale_haircut_20";
export type EvidenceKind =
  | "estate_instrument"
  | "estate_intent"
  | "asset"
  | "decision"
  | "goal"
  | "forecast";
export type InsightType =
  | "liquidity_gap"
  | "timing_gap"
  | "timing_review"
  | "legal_review"
  | "relationship_opportunity";
export type InsightFilterTag =
  | "needs_parent_review"
  | "heir_conversation"
  | "legal_source_conflict"
  | "scenario_mismatch";
export type InsightReviewStatus = "new" | "reviewed" | "dismissed" | "actioned" | "invalidated";

export interface YearQuantiles {
  year: number;
  p10: number;
  p50: number;
  p90: number;
}

export interface ScenarioRow {
  transfer_year: number;
  preset: StressPreset;
  p: number | null;
  cash_p50: number;
  value_p50: number;
  /** Id for GET /forecasts/{scenario_id} (ruling R5: every row carries one). */
  scenario_id: string;
}

export interface EvidenceItem {
  kind: EvidenceKind;
  ref: string;
  label: string;
  status: string;
}

export interface InsightDTO {
  id: string;
  type: InsightType;
  insight_key: string;
  title: string;
  summary: string;
  why_now: string;
  known: string[];
  conditional: string[];
  contact: string[];
  headline_probability: number | null;
  headline_condition: string;
  scenario_rows: ScenarioRow[];
  evidence: EvidenceItem[];
  filter_tags: InsightFilterTag[];
  goal_ref: string | null;
  assumptions: Record<string, unknown>;
  review_status: InsightReviewStatus;
  consent_revision: number;
  created_at: string;
}

export interface ReviewInsightBody {
  review_status: "reviewed" | "dismissed";
}

export interface ScenarioResultDTO {
  value_nominal: YearQuantiles[];
  value_real: YearQuantiles[];
  cash_by_year: YearQuantiles[];
  cash_at_goal: YearQuantiles;
  goal_nominal: number;
  p_cash_covers_goal: number | null;
  shortfall_share: number | null;
  sale_completion_year: number | null;
  transfer_after_goal: boolean;
  admin_cost_at_transfer_p50: number;
  limitations: string[];
  seed: number;
  model_version: string;
  input_hash: string;
  settings: {
    transfer_year: number;
    goal_year: number;
    goal_amount_today: number;
    inflation_rate: number;
    horizon_years: number;
    paths: number;
    preset: StressPreset;
  } & Record<string, unknown>;
  computed_at: string;
}

// ---- Actions, asset terms (Task 9) ------------------------------------------

export type ActionType = "parent_review" | "heir_intro";
export type ActionStatus = "draft" | "approved" | "completed" | "cancelled";

export interface AdvisorActionDTO {
  id: string;
  insight_id: string;
  /** The flag's stable key. A recompute can give the same flag a new insight id; the key survives. */
  insight_key: string;
  action_type: ActionType;
  status: ActionStatus;
  draft_text: string;
  outcome_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateActionBody {
  action_type: ActionType;
  draft_text?: string | null;
}

export interface UpdateActionBody {
  status: ActionStatus;
  draft_text?: string | null;
  outcome_note?: string | null;
}

export interface AssetTermsPatch {
  sale_delay_years?: number;
  liquidatable_fraction?: number | null;
  partner_consent_process_documented?: boolean;
  distribution_yield?: number;
}

export interface ActivityRow {
  at: string;
  kind: "action" | "audit" | "event";
  summary: string;
  actor_display: string | null;
  allowed: boolean | null;
}
