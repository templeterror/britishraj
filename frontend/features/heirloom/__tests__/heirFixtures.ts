// Synthetic family-member (heir) DTO fixtures, using the Morgan seed values, for the heir UI tests.
import type {
  HeirDecisionView,
  HeirGoalView,
  HeirSnapshot,
  MemoryAnswer,
  MemoryMatch,
} from "@/features/heirloom/types/contracts";

export function makeHeirGoal(overrides: Partial<HeirGoalView> = {}): HeirGoalView {
  return {
    goal_id: "goal-1",
    ref: "goal-james-business",
    goal_kind: "business",
    description_private: "Build a software company; I expect to need roughly $500,000 in startup liquidity.",
    amount_target: 500000,
    target_year: 2038,
    horizon_min_years: 8,
    horizon_max_years: 12,
    milestone: "Incorporate and raise a pre-seed round",
    goal_funding_source: "unknown",
    version: 1,
    ...overrides,
  };
}

export function makeHeirDecision(overrides: Partial<HeirDecisionView> = {}): HeirDecisionView {
  return {
    decision_id: "d-reserve",
    date: "2023-11-09",
    title: "Build a two-year liquidity reserve",
    rationale: "Robert wanted enough near-term cash to avoid relying on stock sales in a volatile market.",
    source_title: "Advisor meeting note, 2023-11-09",
    locator: {
      page: 1,
      quoted_span: "Robert wanted enough near-term cash to avoid relying on stock sales in a volatile market.",
    },
    verified_by_display: "Sarah Lin",
    asset_kind: "brokerage",
    ...overrides,
  };
}

export function makeHeirSnapshot(overrides: Partial<HeirSnapshot> = {}): HeirSnapshot {
  return {
    family: { id: "fam-1", display_name: "Morgan family" },
    me: { id: "p-james", display_name: "James Morgan", role: "adult_heir" },
    advisor: { display_name: "Sarah Lin", person_id: "p-sarah" },
    my_goals: [makeHeirGoal()],
    sharing: { advisor_summary: false, advisor_detail: false },
    approved_decisions: [],
    invitations: [],
    planning_prompts: [
      "What would you want to have in place before your next milestone?",
      "Which parts of your plan could you fund on your own, and where would advice help?",
      "What would you like to talk through with your family's advisor?",
    ],
    ...overrides,
  };
}

/**
 * The title of the decision Robert shares in the golden demo, as the family member must see it: the
 * brief allows no asset names on this screen, so the title carries none. The seeded decision's
 * action_text is "Keep the family LLC interest rather than force a sale", and the backend currently
 * serves that text as the title (HeirDecisionView and MemoryMatch), so this fixture is the contract
 * the backend has to meet, not what it does today. The wording test fails if this ever names the LLC.
 */
export const RETAIN_TITLE = "Keep control of the family business rather than force a sale";

/** The Morgan decision Robert shares in the demo, as the family member sees it. */
export function makeRetainDecision(overrides: Partial<HeirDecisionView> = {}): HeirDecisionView {
  return makeHeirDecision({
    decision_id: "d-retain",
    date: "2026-04-15",
    title: RETAIN_TITLE,
    rationale: "Retain family control of the business and avoid a forced sale in unfavorable conditions",
    source_title: "Meeting transcript, Robert Morgan and Sarah Lin, 2026-04-15",
    locator: {
      start_seconds: 113,
      end_seconds: 148,
      quoted_span:
        "We want to keep control of the business in the family. I don't want to be forced to sell when the timing is wrong.",
    },
    asset_kind: "private_business",
    ...overrides,
  });
}

/** The Morgan answer to "Why was family control important?" once Robert shares that decision. */
export function makeControlMatch(overrides: Partial<MemoryMatch> = {}): MemoryMatch {
  return {
    decision_id: "d-retain",
    title: RETAIN_TITLE,
    date: "2026-04-15",
    excerpt: "We want to keep control of the business in the family. I don't want to be forced to sell when the timing is wrong.",
    source_title: "Meeting transcript, Robert Morgan and Sarah Lin, 2026-04-15",
    locator: { start_seconds: 113, end_seconds: 148 },
    verified_by_display: "Sarah Lin",
    score: 3,
    ...overrides,
  };
}

export function makeAnswer(overrides: Partial<MemoryAnswer> = {}): MemoryAnswer {
  return { status: "answered", reason: null, matches: [makeControlMatch()], ...overrides };
}
