// Synthetic advisor-side DTO fixtures shared by the advisor UI tests.
import type {
  AdvisorSnapshot,
  InsightDTO,
  ScenarioResultDTO,
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
