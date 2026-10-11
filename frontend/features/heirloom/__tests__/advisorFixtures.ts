// Synthetic advisor-side DTO fixtures shared by the advisor UI tests.
import type {
  AdvisorDecisionDTO,
  AdvisorSnapshot,
  GraphDTO,
  HeirSharingView,
  InsightDTO,
  InstrumentDTO,
  IntentDTO,
  ScenarioResultDTO,
  SourceRef,
  StressPreset,
  YearQuantiles,
} from "@/features/heirloom/types/contracts";

export const META = { revision: 3, consent_revision: 1, mode: "demo" as const, degraded: [] };

export function envelope<T>(data: T) {
  return { data, meta: META, errors: [] };
}

export function makeSnapshot(overrides: Partial<AdvisorSnapshot> = {}): AdvisorSnapshot {
  return {
    family: { id: "fam-1", display_name: "Morgan family", as_of_year: 2026 },
    advisor: { id: "p-sarah", display_name: "Sarah Lin", role: "advisor" },
    people: [
      { id: "p-sarah", ref: "person-sarah", display_name: "Sarah Lin", role: "advisor", age: null },
      { id: "p-robert", ref: "person-robert", display_name: "Robert Morgan", role: "parent", age: null },
      { id: "p-james", ref: "person-james", display_name: "James Morgan", role: "adult_heir", age: 29 },
    ],
    assets: [
      {
        id: "a-llc",
        ref: "asset-family-llc",
        label: "40% interest, Morgan Family Holdings LLC",
        asset_kind: "private_business",
        liquidity_class: "illiquid",
        value: 5_000_000,
        liabilities: 1_200_000,
        terms: {
          expected_return: 0.055,
          annual_volatility: 0.22,
          annual_fee: 0,
          liquidatable_fraction: 0.25,
          sale_delay_years: 2,
          admin_delay_years: 0,
          sale_cost_fraction: 0.09,
          distribution_yield: 0.01,
          admin_cost_fraction: 0.01,
          partner_consent_required: true,
          partner_consent_process_documented: true,
        },
        market_events: [],
      },
    ],
    instruments: [],
    intents: [],
    decisions: [],
    goal_sharing: "summary",
    shared_goals: [],
    coverage: {
      decisions_verified: 4,
      decisions_total: 5,
      assets_with_verified_intent: 1,
      assets_total: 3,
      heirs_connected: 0,
      heirs_total: 1,
    },
    open_flags: 1,
    preserve_values: [
      "Family control of the business",
      "Avoid forced sales",
      "Long-term growth",
      "Charitable purpose",
    ],
    sources: [
      makeSource(),
      makeSource({
        ref: "source-note-2023-11-09",
        title: "Advisor meeting note, 2023-11-09",
        document_date: "2023-11-09",
        source_type: "meeting_note",
      }),
    ],
    sharing_policy: { estate_intent: "off", balances: "not_available_in_pilot" },
    ...overrides,
  };
}

export function makeSource(overrides: Partial<SourceRef> = {}): SourceRef {
  return {
    ref: "meeting-2026-04-15",
    title: "Meeting transcript, Robert Morgan and Sarah Lin, 2026-04-15",
    document_date: "2026-04-15",
    source_type: "transcript",
    ...overrides,
  };
}

/** A verified decision's sharing state toward James; by default never shared, with no provenance. */
export function makeHeirSharing(overrides: Partial<HeirSharingView> = {}): HeirSharingView {
  return {
    shared: false,
    recipient_person_id: "p-james",
    recipient_display: "James Morgan",
    recorded_via: null,
    recorded_by_display: null,
    basis_date: null,
    basis_note: null,
    basis_source_ref: null,
    basis_source_title: null,
    updated_at: null,
    ...overrides,
  };
}

const PRESETS: StressPreset[] = ["base", "exit_delay_24m", "shock_30_y1", "sale_haircut_20"];

export function makeInsight(overrides: Partial<InsightDTO> = {}): InsightDTO {
  return {
    id: "ins-1",
    type: "liquidity_gap",
    insight_key: "liquidity_gap:asset-family-llc:goal-james-business",
    title: "Liquidity for James's goal depends on how fast the LLC interest could be sold",
    summary: "Paper value is steady across presets; accessible cash is not.",
    why_now: "James shared a business goal in year 12.",
    known: ["Base 81%"],
    conditional: [],
    contact: [],
    headline_probability: 0.06,
    headline_condition: "if transfer occurred in year 10 and exit took 24 months longer",
    scenario_rows: [10, 20, 30].flatMap((t) =>
      PRESETS.map((preset) => ({
        transfer_year: t,
        preset,
        p: t === 10 ? (preset === "exit_delay_24m" ? 0.06 : 0.81) : 0,
        cash_p50: 0,
        value_p50: 0,
        scenario_id: `sc-${t}-${preset}`,
      })),
    ),
    evidence: [
      { kind: "estate_instrument", ref: "instr-estate-letter-2026", label: "Estate planning letter, 2026", status: "verified" },
      { kind: "estate_intent", ref: "intent-james-llc", label: "Robert's 40% membership interest", status: "verified" },
      { kind: "asset", ref: "asset-family-llc", label: "Morgan Family Holdings LLC", status: "verified" },
      { kind: "decision", ref: "decision-retain-llc", label: "Keep the family LLC interest", status: "verified" },
      { kind: "goal", ref: "goal-james-business", label: "Business goal (summary)", status: "verified" },
      { kind: "forecast", ref: "sc-10-exit_delay_24m", label: "Forecast", status: "verified" },
    ],
    filter_tags: ["needs_parent_review", "scenario_mismatch"],
    goal_ref: "goal-james-business",
    assumptions: {},
    review_status: "new",
    consent_revision: 1,
    created_at: "2026-10-10T12:00:00Z",
    ...overrides,
  };
}

function q(year: number, p50: number): YearQuantiles {
  return { year, p10: p50 * 0.6, p50, p90: p50 * 1.6 };
}

/** 31 years (0..30) of synthetic quantiles; cash is zero before the transfer year. */
export function makeResult(opts: {
  transferYear?: number;
  goalYear?: number;
  goalNominal?: number;
  cashAtGoalP50?: number;
  preset?: StressPreset;
} = {}): ScenarioResultDTO {
  const transferYear = opts.transferYear ?? 10;
  const goalYear = opts.goalYear ?? 12;
  const goalNominal = opts.goalNominal ?? 672_444;
  const cashAtGoalP50 = opts.cashAtGoalP50 ?? 900_000;
  const years = Array.from({ length: 31 }, (_, y) => y);
  const value = years.map((y) => q(y, 5_000_000 * 1.04 ** y));
  const cash = years.map((y) =>
    y < transferYear ? { year: y, p10: 0, p50: 0, p90: 0 } : q(y, y === goalYear ? cashAtGoalP50 : 800_000),
  );
  return {
    value_nominal: value,
    value_real: value,
    cash_by_year: cash,
    cash_at_goal: q(goalYear, cashAtGoalP50),
    goal_nominal: goalNominal,
    p_cash_covers_goal: cashAtGoalP50 >= goalNominal ? 0.81 : 0.06,
    shortfall_share: 0.2,
    sale_completion_year: transferYear + 2,
    transfer_after_goal: transferYear > goalYear,
    admin_cost_at_transfer_p50: 50_000,
    limitations: [
      "Illustrative assumptions; not a prediction",
      "Taxes not modeled",
      "Hypothetical transfer timing; no mortality modeled",
    ],
    seed: 40626,
    model_version: "relay-forecast-1.0",
    input_hash: "abc123def456",
    settings: {
      transfer_year: transferYear,
      goal_year: goalYear,
      goal_amount_today: 500_000,
      inflation_rate: 0.025,
      horizon_years: 30,
      paths: 2000,
      preset: opts.preset ?? "base",
    },
    computed_at: "2026-10-10T12:00:00Z",
  };
}

export function makeInstrument(overrides: Partial<InstrumentDTO> = {}): InstrumentDTO {
  return {
    id: "i-letter",
    ref: "instr-estate-letter-2026",
    title: "Estate planning letter, 2026",
    kind: "letter_of_intent",
    status: "verified",
    effective_date: "2026-03-02",
    revocable: true,
    counsel_reviewed_at: null,
    source_title: "estate_letter_2026.txt",
    source_excerpt: "I intend my 40% membership interest in Morgan Family Holdings LLC to pass to my son James.",
    source_version: 1,
    ...overrides,
  };
}

export function makeIntent(overrides: Partial<IntentDTO> = {}): IntentDTO {
  return {
    id: "t-james-llc",
    ref: "intent-james-llc",
    instrument_ref: "instr-estate-letter-2026",
    asset_ref: "asset-family-llc",
    beneficiary_id: "p-james",
    beneficiary_display_name: "James Morgan",
    allocation: "Robert's 40% membership interest",
    conditions: [
      "Subject to the LLC operating agreement's partner-consent provisions",
      "Revocable; may be amended by Robert at any time",
    ],
    status: "verified",
    advisor_verified: true,
    verified_by_display: "Sarah Lin",
    verification_notes: null,
    confidence: 0.93,
    valid_from: "2026-03-02",
    valid_to: null,
    counsel_reviewed_at: null,
    ...overrides,
  };
}

export function makeDecision(overrides: Partial<AdvisorDecisionDTO> = {}): AdvisorDecisionDTO {
  return {
    id: "d-retain-llc",
    ref: "decision-retain-llc",
    decision_date: "2026-04-15",
    asset_ref: "asset-family-llc",
    action: "Keep the family LLC interest rather than force a sale",
    rationale: "Retain family control of the business and avoid a forced sale in unfavorable conditions",
    alternatives: ["Sell part of the interest", "Refinance the LLC debt", "Retain the holding"],
    verification_status: "candidate",
    rationale_edited: false,
    advisor_note: null,
    valid_to: null,
    confidence: 0.91,
    source_title: "Meeting transcript, 15 Apr 2026",
    locator: {
      start_seconds: 113,
      end_seconds: 148,
      quoted_span:
        "We want to keep control of the business in the family. I don't want to be forced to sell when the timing is wrong.",
    },
    verified_by_display: null,
    shared_with_heir: false,
    heir_sharing: null,
    ...overrides,
  };
}

/** A small advisor graph: the 2026 letter's verified intent toward James, a candidate decision, a forecast and a flag. */
export function makeGraph(overrides: Partial<GraphDTO> = {}): GraphDTO {
  const node = (n: Partial<GraphDTO["nodes"][number]> & Pick<GraphDTO["nodes"][number], "record_id" | "label" | "kind">) => ({
    classification: "internal_parent_advisor" as const,
    valid_from: null,
    valid_to: null,
    evidence_status: "verified" as const,
    props: {},
    ...n,
  });
  return {
    nodes: [
      node({ record_id: "person-robert", label: "Robert Morgan", kind: "person", classification: "family_member" }),
      node({ record_id: "person-james", label: "James Morgan", kind: "person", classification: "family_member" }),
      node({ record_id: "instr-estate-letter-2026", label: "Estate planning letter, 2026", kind: "instrument" }),
      node({ record_id: "intent-james-llc", label: "Robert's 40% membership interest", kind: "intent" }),
      node({ record_id: "asset-family-llc", label: "40% interest, Morgan Family Holdings LLC", kind: "asset" }),
      node({
        record_id: "decision-retain-llc",
        label: "Keep the family LLC interest rather than force a sale",
        kind: "decision",
        evidence_status: "candidate",
      }),
      // Generated records carry no verification state: the backend marks forecasts and flags "unknown".
      node({
        record_id: "forecast-sc-10-exit_delay_24m",
        label: "Illustrative: if transfer were to occur in year 10",
        kind: "forecast",
        classification: "advisor_only",
        evidence_status: "unknown",
      }),
      node({
        record_id: "insight-liquidity",
        label: "Liquidity review",
        kind: "insight",
        classification: "advisor_only",
        evidence_status: "unknown",
      }),
    ],
    edges: [
      { type: "OWNS", source_id: "person-robert", target_id: "asset-family-llc", valid_from: null, valid_to: null, classification: "internal_parent_advisor" },
      { type: "DOCUMENTS", source_id: "instr-estate-letter-2026", target_id: "intent-james-llc", valid_from: null, valid_to: null, classification: "internal_parent_advisor" },
      { type: "INTENDED_FOR", source_id: "intent-james-llc", target_id: "person-james", valid_from: "2026-03-02", valid_to: null, classification: "internal_parent_advisor" },
      { type: "CONCERNS", source_id: "decision-retain-llc", target_id: "asset-family-llc", valid_from: null, valid_to: null, classification: "internal_parent_advisor" },
      { type: "MODELS", source_id: "forecast-sc-10-exit_delay_24m", target_id: "asset-family-llc", valid_from: null, valid_to: null, classification: "advisor_only" },
      // An edge whose endpoint the projection dropped: no node may be invented for it.
      { type: "STATED", source_id: "person-james", target_id: "goal-james-business", valid_from: null, valid_to: null, classification: "private_heir" },
    ],
    evidence_refs: ["asset-family-llc", "decision-retain-llc", "instr-estate-letter-2026", "intent-james-llc"],
    revision: 7,
    ...overrides,
  };
}
