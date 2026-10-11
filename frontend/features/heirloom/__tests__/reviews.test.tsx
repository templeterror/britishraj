import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RelayApiError } from "@/features/heirloom/api/client";
import ActivityLog from "@/features/heirloom/components/ActivityLog";
import DecisionReview from "@/features/heirloom/components/DecisionReview";
import IntentReview from "@/features/heirloom/components/IntentReview";
import { AdvisorTabs } from "@/features/heirloom/screens/AdvisorScreen";
import type { ActivityRow } from "@/features/heirloom/types/contracts";
import { envelope, makeDecision, makeInstrument, makeIntent, makeSnapshot } from "./advisorFixtures";

const get = vi.hoisted(() => vi.fn());
const post = vi.hoisted(() => vi.fn());
vi.mock("@/features/heirloom/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/heirloom/api/client")>();
  return { ...actual, default: { get, post, patch: vi.fn() } };
});

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  post.mockResolvedValue(envelope({}));
});

function candidateCard() {
  return screen.getByRole("article", { name: "Keep the family LLC interest rather than force a sale" });
}

describe("DecisionReview", () => {
  it("rejecting without a note shows an inline error and makes no request", async () => {
    render(<DecisionReview snapshot={makeSnapshot({ decisions: [makeDecision()] })} onChanged={() => {}} />);

    await userEvent.click(within(candidateCard()).getByRole("button", { name: "Reject" }));

    expect(within(candidateCard()).getByRole("alert")).toHaveTextContent("Add a note explaining why");
    expect(post).not.toHaveBeenCalled();
  });

  it('shows "Rationale not documented" for a candidate with no rationale', () => {
    render(
      <DecisionReview snapshot={makeSnapshot({ decisions: [makeDecision({ rationale: null })] })} onChanged={() => {}} />,
    );
    expect(within(candidateCard()).getByText("Rationale not documented")).toBeInTheDocument();
  });

  it("shows the transcript excerpt with its time range and the extracted fields", () => {
    render(<DecisionReview snapshot={makeSnapshot({ decisions: [makeDecision()] })} onChanged={() => {}} />);
    const card = candidateCard();
    expect(within(card).getByText(/1:53–2:28/)).toBeInTheDocument();
    expect(within(card).getByText(/keep control of the business in the family/)).toBeInTheDocument();
    expect(within(card).getByText("Refinance the LLC debt")).toBeInTheDocument();
    expect(within(card).getByText("91%")).toBeInTheDocument();
  });

  it("lists candidates before verified decisions, with dates", () => {
    const verified = makeDecision({
      id: "d-reserve",
      ref: "decision-liquidity-reserve",
      decision_date: "2023-11-09",
      action: "Build a two-year liquidity reserve",
      verification_status: "verified",
      verified_by_display: "Sarah Lin",
    });
    render(<DecisionReview snapshot={makeSnapshot({ decisions: [verified, makeDecision()] })} onChanged={() => {}} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings).toEqual([
      "Keep the family LLC interest rather than force a sale",
      "Build a two-year liquidity reserve",
    ]);
    expect(screen.getByText(/9 Nov 2023/)).toBeInTheDocument();
  });

  it("verifies with an edited rationale", async () => {
    const onChanged = vi.fn();
    render(<DecisionReview snapshot={makeSnapshot({ decisions: [makeDecision()] })} onChanged={onChanged} />);
    const card = candidateCard();
    const rationale = within(card).getByLabelText("Rationale (edit before verifying)");
    await userEvent.clear(rationale);
    await userEvent.type(rationale, "Keep control in the family");
    await userEvent.click(within(card).getByRole("button", { name: "Verify" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/families/fam-1/decisions/d-retain-llc/verify", {
        approved: true,
        edited_rationale: "Keep control in the family",
        note: null,
      }),
    );
    expect(onChanged).toHaveBeenCalled();
  });

  it("verifies unchanged without sending an edited rationale", async () => {
    render(<DecisionReview snapshot={makeSnapshot({ decisions: [makeDecision()] })} onChanged={() => {}} />);
    await userEvent.click(within(candidateCard()).getByRole("button", { name: "Verify" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/families/fam-1/decisions/d-retain-llc/verify", {
        approved: true,
        edited_rationale: null,
        note: null,
      }),
    );
  });

  it("rejects and annotates with the note", async () => {
    render(<DecisionReview snapshot={makeSnapshot({ decisions: [makeDecision()] })} onChanged={() => {}} />);
    const card = candidateCard();
    await userEvent.type(within(card).getByLabelText("Note"), "Robert did not say this");
    await userEvent.click(within(card).getByRole("button", { name: "Annotate" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/families/fam-1/decisions/d-retain-llc/annotate", {
        note: "Robert did not say this",
      }),
    );
    // A saved annotation clears the note field.
    await waitFor(() => expect(within(card).getByLabelText("Note")).toHaveValue(""));
    await userEvent.type(within(card).getByLabelText("Note"), "Robert did not say this");
    await userEvent.click(within(card).getByRole("button", { name: "Reject" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/families/fam-1/decisions/d-retain-llc/verify", {
        approved: false,
        edited_rationale: null,
        note: "Robert did not say this",
      }),
    );
  });

  it("shows the server's message when a request fails", async () => {
    post.mockRejectedValueOnce(new RelayApiError(409, "invalid_transition", "A verified decision cannot be verified again."));
    render(<DecisionReview snapshot={makeSnapshot({ decisions: [makeDecision()] })} onChanged={() => {}} />);
    await userEvent.click(within(candidateCard()).getByRole("button", { name: "Verify" }));
    expect(await within(candidateCard()).findByRole("alert")).toHaveTextContent("cannot be verified again");
  });
});

describe("IntentReview", () => {
  const amendment = makeInstrument({
    id: "i-amend",
    ref: "instr-first-amendment-2026",
    title: "First Amendment to estate planning letter",
    status: "reported",
    effective_date: "2026-09-01",
    source_excerpt: "names Claire Morgan (Robert's niece) for the same LLC interest",
    source_version: 2,
  });
  const proposed = makeIntent({
    id: "t-claire",
    ref: "intent-claire-llc",
    instrument_ref: "instr-first-amendment-2026",
    beneficiary_display_name: "Claire Morgan",
    status: "proposed",
    advisor_verified: false,
    verified_by_display: null,
    confidence: 0.74,
  });

  function renderIntents(onChanged = () => {}) {
    const snapshot = makeSnapshot({
      instruments: [
        makeInstrument(),
        amendment,
        makeInstrument({ id: "i-will", ref: "instr-draft-will-2024", title: "Draft will, 2024", status: "superseded" }),
      ],
      intents: [makeIntent(), proposed],
    });
    return render(<IntentReview snapshot={snapshot} onChanged={onChanged} />);
  }

  const card = (title: string) => screen.getByRole("article", { name: title });

  it("labels each instrument and shows the excerpt beside the extracted fields", () => {
    renderIntents();
    expect(within(card("Estate planning letter, 2026")).getByText(/verified document/i)).toBeInTheDocument();
    expect(within(card("First Amendment to estate planning letter")).getByText(/^draft/i)).toBeInTheDocument();
    expect(within(card("Draft will, 2024")).getByText(/superseded/i)).toBeInTheDocument();

    const letter = card("Estate planning letter, 2026");
    expect(within(letter).getByText(/pass to my son James/)).toBeInTheDocument();
    expect(within(letter).getByText("40% interest, Morgan Family Holdings LLC")).toBeInTheDocument();
    expect(within(letter).getByText("James Morgan")).toBeInTheDocument();
    expect(within(letter).getByText("Robert's 40% membership interest")).toBeInTheDocument();
    expect(within(letter).getByText(/partner-consent provisions/)).toBeInTheDocument();
    expect(within(letter).getByText("93%")).toBeInTheDocument();
  });

  it("labels an instrument with a contested intent as an unknown conflict", () => {
    const snapshot = makeSnapshot({
      instruments: [makeInstrument()],
      intents: [makeIntent({ status: "contested" })],
    });
    render(<IntentReview snapshot={snapshot} onChanged={() => {}} />);
    expect(within(card("Estate planning letter, 2026")).getByText(/unknown conflict/i)).toBeInTheDocument();
  });

  it("imports the synthetic amendment", async () => {
    const onChanged = vi.fn();
    renderIntents(onChanged);
    await userEvent.click(screen.getByRole("button", { name: "Import synthetic amendment" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/families/fam-1/estate-intents/import", { fixture_ref: "conflicting_amendment" }),
    );
    expect(onChanged).toHaveBeenCalled();
  });

  it("verifies and rejects a proposed intent against its source version", async () => {
    renderIntents();
    const amend = card("First Amendment to estate planning letter");
    await userEvent.click(within(amend).getByRole("button", { name: "Verify" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/families/fam-1/estate-intents/t-claire/verify", {
        verified: true,
        notes: null,
        source_version: 2,
      }),
    );
    await userEvent.type(within(amend).getByLabelText("Verification notes"), "Unsigned copy");
    await userEvent.click(within(amend).getByRole("button", { name: "Reject" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/families/fam-1/estate-intents/t-claire/verify", {
        verified: false,
        notes: "Unsigned copy",
        source_version: 2,
      }),
    );
    // Only a proposed intent can be verified.
    expect(within(card("Estate planning letter, 2026")).queryByRole("button", { name: "Verify" })).toBeNull();
  });

  it("marks an instrument superseded, and not one that already is", async () => {
    renderIntents();
    await userEvent.click(within(card("Estate planning letter, 2026")).getByRole("button", { name: "Mark superseded" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/families/fam-1/instruments/i-letter/status", { status: "superseded" }),
    );
    expect(within(card("Draft will, 2024")).queryByRole("button", { name: "Mark superseded" })).toBeNull();
  });

  it("asks for a reload when the source changed since it was opened", async () => {
    const onChanged = vi.fn();
    post.mockRejectedValueOnce(
      new RelayApiError(409, "stale_source", "The source document changed since you opened it. Reload and review again."),
    );
    renderIntents(onChanged);
    const amend = card("First Amendment to estate planning letter");
    await userEvent.click(within(amend).getByRole("button", { name: "Verify" }));
    expect(await within(amend).findByRole("alert")).toHaveTextContent("source document changed");
    expect(onChanged).toHaveBeenCalled();
  });
});

describe("ActivityLog", () => {
  it("lists activity rows newest first as returned", async () => {
    const rows: ActivityRow[] = [
      { at: "2026-10-10T12:05:00Z", kind: "audit", summary: "decision.verify decision-retain-llc", actor_display: "Sarah Lin", allowed: true },
      { at: "2026-10-10T12:00:00Z", kind: "audit", summary: "family.read", actor_display: null, allowed: false },
    ];
    get.mockResolvedValue(envelope(rows));
    render(<ActivityLog familyId="fam-1" />);

    const items = await screen.findAllByRole("listitem");
    expect(get).toHaveBeenCalledWith("/families/fam-1/activity");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText("decision.verify decision-retain-llc")).toBeInTheDocument();
    expect(within(items[0]).getByText(/Sarah Lin/)).toBeInTheDocument();
    expect(within(items[1]).getByText("Denied")).toBeInTheDocument();
  });

  it("refetches when the refresh key changes", async () => {
    get.mockResolvedValue(envelope([]));
    const { rerender } = render(<ActivityLog familyId="fam-1" refreshKey={0} />);
    await screen.findByText("No activity yet");
    rerender(<ActivityLog familyId="fam-1" refreshKey={1} />);
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });

  it("shows an empty state when there is no activity", async () => {
    get.mockResolvedValue(envelope([]));
    render(<ActivityLog familyId="fam-1" />);
    expect(await screen.findByText("No activity yet")).toBeInTheDocument();
  });
});

describe("AdvisorTabs", () => {
  it("switches between the advisor views by click and arrow keys", async () => {
    get.mockImplementation(async (path: string) => {
      if (path.endsWith("/activity")) return envelope([]);
      throw new Error(`unexpected GET ${path}`);
    });
    render(
      <AdvisorTabs
        familyId="fam-1"
        snapshot={makeSnapshot({ decisions: [makeDecision()] })}
        insights={[]}
        refreshKey={0}
        onChanged={() => {}}
      />,
    );
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Flags",
      "Knowledge graph",
      "Estate intents",
      "Decision memory",
      "Activity",
    ]);
    expect(screen.getByRole("tab", { name: "Flags" })).toHaveAttribute("aria-selected", "true");

    await userEvent.click(screen.getByRole("tab", { name: "Decision memory" }));
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName("Decision memory");
    expect(candidateCard()).toBeInTheDocument();

    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Activity" })).toHaveFocus();
    expect(await screen.findByText("No activity yet")).toBeInTheDocument();
  });
});
