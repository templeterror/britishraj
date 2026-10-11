import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RelayApiError } from "@/features/heirloom/api/client";
import ApprovedMemory from "@/features/heirloom/components/ApprovedMemory";
import InvitationCard from "@/features/heirloom/components/InvitationCard";
import HeirScreen from "@/features/heirloom/screens/HeirScreen";
import { setSession } from "@/features/heirloom/session";
import type {
  HeirDecisionView,
  HeirGoalView,
  HeirSnapshot,
  InvitationView,
  MemoryAnswer,
} from "@/features/heirloom/types/contracts";
import { envelope } from "./advisorFixtures";
import {
  makeAnswer,
  makeHeirDecision,
  makeHeirGoal,
  makeHeirSnapshot,
  makeRetainDecision,
  RETAIN_TITLE,
} from "./heirFixtures";

const get = vi.hoisted(() => vi.fn());
const post = vi.hoisted(() => vi.fn());
const put = vi.hoisted(() => vi.fn());
const patch = vi.hoisted(() => vi.fn());
vi.mock("@/features/heirloom/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/heirloom/api/client")>();
  return { ...actual, default: { get, post, put, patch } };
});

const CONFLICT = "This goal was updated in another window.";
const SERVER_CONFLICT = `${CONFLICT} Reload to see it.`;
const GOAL_PATH = "/families/fam-1/heir-goals/goal-1";
const CONSENT_PATH = "/families/fam-1/consents/goal-1";
const ASK_PATH = "/families/fam-1/memory/ask";

/** What the API currently holds. A test changes it to play "another window"; the mocks below apply writes to it. */
interface ServerState {
  advisor: HeirSnapshot["advisor"];
  goal: HeirGoalView | null;
  sharing: { advisor_summary: boolean; advisor_detail: boolean };
  decisions: HeirDecisionView[];
  invitations: InvitationView[];
  answer: MemoryAnswer;
}
let server: ServerState;

beforeEach(() => {
  server = {
    advisor: makeHeirSnapshot().advisor,
    goal: makeHeirGoal(),
    sharing: { advisor_summary: false, advisor_detail: false },
    decisions: [],
    invitations: [],
    answer: makeAnswer(),
  };
  setSession({
    token: "demo-token",
    familyId: "fam-1",
    person: { id: "p-james", displayName: "James Morgan", role: "adult_heir" },
  });

  get.mockReset();
  get.mockImplementation(async (path: string) => {
    if (path.endsWith("/revision")) return envelope({ revision: 3, consent_revision: 1 });
    if (path.endsWith("/snapshot")) {
      return envelope(
        makeHeirSnapshot({
          advisor: { ...server.advisor },
          my_goals: server.goal ? [{ ...server.goal }] : [],
          sharing: { ...server.sharing },
          approved_decisions: server.decisions,
          invitations: server.invitations,
        }),
      );
    }
    throw new Error(`unexpected GET ${path}`);
  });

  // Mirrors the API's rules: a stale version is a 409, only the fields sent change.
  patch.mockReset();
  patch.mockImplementation(async (path: string, body: { version: number }) => {
    if (path !== GOAL_PATH) throw new Error(`unexpected PATCH ${path}`);
    if (!server.goal || body.version !== server.goal.version) {
      throw new RelayApiError(409, "version_conflict", SERVER_CONFLICT);
    }
    const { version, ...fields } = body;
    server.goal = { ...server.goal, ...fields, version: version + 1 };
    return envelope({ ...server.goal });
  });

  // Mirrors the consent rules: details on switches the summary on, summary off switches details off.
  put.mockReset();
  put.mockImplementation(async (path: string, body: { scope: string; active: boolean }) => {
    if (path !== CONSENT_PATH) throw new Error(`unexpected PUT ${path}`);
    if (body.scope === "goal_detail") {
      server.sharing.advisor_detail = body.active;
      if (body.active) server.sharing.advisor_summary = true;
    } else {
      server.sharing.advisor_summary = body.active;
      if (!body.active) server.sharing.advisor_detail = false;
    }
    return envelope({ consent_revision: 2 });
  });

  post.mockReset();
  post.mockImplementation(async (path: string, body: Record<string, unknown>) => {
    if (path === ASK_PATH) return envelope(server.answer);
    if (path === "/families/fam-1/heir-goals") {
      server.goal = { ...makeHeirGoal({ goal_id: "goal-new" }), ...body, version: 1 } as HeirGoalView;
      return envelope({ ...server.goal });
    }
    throw new Error(`unexpected POST ${path}`);
  });
});

/**
 * Everything a person can read under `root`: the text nodes (with a space between them so that word
 * boundaries survive) and the current value of every text field, which is not in a text node.
 */
function screenText(root: HTMLElement): string {
  const parts: string[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) parts.push(node.textContent ?? "");
  root.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input, textarea").forEach((el) => parts.push(el.value));
  return parts.join(" ").replace(/\s+/g, " ");
}

const narrativeField = () => screen.findByLabelText("What are you working toward?");
const summarySwitch = () => screen.findByRole("switch", { name: /Share a goal summary with Sarah/ });
const detailSwitch = () => screen.findByRole("switch", { name: /Also share full details/ });

describe("HeirScreen", () => {
  it("welcomes the family member and says their information is private", async () => {
    render(<HeirScreen />);

    expect(await screen.findByRole("heading", { level: 1, name: "Your future, on your terms." })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Welcome, James. Your goals stay yours. You choose whether Sarah, your family's advisor, can help.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Your information is private unless you choose to share it.")).toBeInTheDocument();
    expect(screen.getByText("What would you want to have in place before your next milestone?")).toBeInTheDocument();
  });

  it("asks for a persona when no one is signed in, and for the family member persona on another role's session", async () => {
    window.sessionStorage.clear();
    const { unmount } = render(<HeirScreen />);
    expect(screen.getByText("No persona selected")).toBeInTheDocument();
    unmount();

    setSession({
      token: "demo-token",
      familyId: "fam-1",
      person: { id: "p-sarah", displayName: "Sarah Lin", role: "advisor" },
    });
    render(<HeirScreen />);
    expect(screen.getByText("This view is for family members")).toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
  });

  it("shows a recoverable error when the snapshot cannot load", async () => {
    get.mockImplementation(async () => {
      throw new RelayApiError(0, "network_error", "Failed to fetch");
    });
    render(<HeirScreen />);

    expect(await screen.findByText("Can't reach Heirloom Relay")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

describe("GoalCheckIn", () => {
  it("saves an edited goal against the version it loaded", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);

    const narrative = await narrativeField();
    expect(narrative).toHaveValue(makeHeirGoal().description_private);
    expect(screen.getByLabelText("Rough amount you expect to need (optional)")).toHaveValue(500000);
    await user.clear(narrative);
    await user.type(narrative, "Open a design studio");
    await user.click(screen.getByRole("button", { name: "Save goal" }));

    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(GOAL_PATH, {
        goal_kind: "business",
        description_private: "Open a design studio",
        amount_target: 500000,
        target_year: 2038,
        horizon_min_years: 8,
        horizon_max_years: 12,
        milestone: "Incorporate and raise a pre-seed round",
        version: 1,
      }),
    );
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    // The refetched goal is version 2, so a second save sends that version.
    await waitFor(() => expect(get.mock.calls.filter(([p]) => String(p).endsWith("/snapshot")).length).toBe(2));
    await user.type(narrative, " and a studio dog");
    await user.click(screen.getByRole("button", { name: "Save goal" }));
    await waitFor(() => expect(patch).toHaveBeenLastCalledWith(GOAL_PATH, expect.objectContaining({ version: 2 })));
    expect(screen.queryByText(CONFLICT)).not.toBeInTheDocument();
  });

  it("says the goal was updated in another window on a 409, and Reload brings in the new goal", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    const narrative = await narrativeField();

    // Another window saves first.
    server.goal = makeHeirGoal({ description_private: "Build a software company with a co-founder", version: 2 });
    await user.clear(narrative);
    await user.type(narrative, "Open a design studio");
    await user.click(screen.getByRole("button", { name: "Save goal" }));

    expect(await screen.findByText(CONFLICT)).toBeInTheDocument();
    expect(patch).toHaveBeenCalledWith(GOAL_PATH, expect.objectContaining({ version: 1 }));
    expect(narrative).toHaveValue("Open a design studio"); // the person's edit is not thrown away yet

    await user.click(screen.getByRole("button", { name: "Reload" }));

    await waitFor(() => expect(narrative).toHaveValue("Build a software company with a co-founder"));
    expect(screen.queryByText(CONFLICT)).not.toBeInTheDocument();
    // Saving again works against the reloaded version.
    await user.click(screen.getByRole("button", { name: "Save goal" }));
    await waitFor(() => expect(patch).toHaveBeenLastCalledWith(GOAL_PATH, expect.objectContaining({ version: 2 })));
  });

  it("takes in a change from another window when the form has no unsaved edits", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    const narrative = await narrativeField();

    server.goal = makeHeirGoal({ description_private: "Build a software company with a co-founder", version: 2 });
    await user.click(await summarySwitch()); // any write refetches the snapshot

    await waitFor(() => expect(narrative).toHaveValue("Build a software company with a co-founder"));
    expect(screen.queryByText(CONFLICT)).not.toBeInTheDocument();
  });

  it("keeps unsaved edits through a refresh, then reports the conflict on save", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    const narrative = await narrativeField();
    await user.clear(narrative);
    await user.type(narrative, "Open a design studio");

    server.goal = makeHeirGoal({ description_private: "Build a software company with a co-founder", version: 2 });
    await user.click(await summarySwitch());
    await waitFor(() => expect(get.mock.calls.filter(([p]) => String(p).endsWith("/snapshot")).length).toBe(2));
    expect(narrative).toHaveValue("Open a design studio");

    await user.click(screen.getByRole("button", { name: "Save goal" }));
    expect(await screen.findByText(CONFLICT)).toBeInTheDocument();
  });

  it("the example buttons fill the form, and saving sends the example's timeframe too", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    await narrativeField();

    await user.click(screen.getByRole("button", { name: "Endow a foundation" }));

    expect(screen.getByLabelText("Kind of goal")).toHaveValue("philanthropy");
    expect(screen.getByLabelText("What are you working toward?")).toHaveValue("Endow a small family foundation");
    expect(screen.getByLabelText("Rough amount you expect to need (optional)")).toHaveValue(250000);
    expect(screen.getByLabelText("Target year (optional)")).toHaveValue(2051);
    expect(screen.getByLabelText("Next milestone (optional)")).toHaveValue("");
    expect(patch).not.toHaveBeenCalled(); // nothing is saved until the person saves

    await user.click(screen.getByRole("button", { name: "Save goal" }));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(GOAL_PATH, {
        goal_kind: "philanthropy",
        description_private: "Endow a small family foundation",
        amount_target: 250000,
        target_year: 2051,
        horizon_min_years: 20,
        horizon_max_years: 25,
        milestone: null,
        version: 1,
      }),
    );

    await user.click(screen.getByRole("button", { name: "Start a company" }));
    expect(screen.getByLabelText("Kind of goal")).toHaveValue("business");
    expect(screen.getByLabelText("Target year (optional)")).toHaveValue(2038);
  });

  it("offers every kind of goal", async () => {
    render(<HeirScreen />);
    const kinds = within(await screen.findByLabelText("Kind of goal"))
      .getAllByRole("option")
      .map((o) => (o as HTMLOptionElement).value);
    expect(kinds).toEqual(["business", "home", "education", "philanthropy", "wealth_preservation", "other"]);
  });

  it("clears the timeframe when the target year is changed by hand, so it never disagrees with the year", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    const year = await screen.findByLabelText("Target year (optional)");
    await user.clear(year);
    await user.type(year, "2045");
    await user.click(screen.getByRole("button", { name: "Save goal" }));

    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        GOAL_PATH,
        expect.objectContaining({ target_year: 2045, horizon_min_years: null, horizon_max_years: null }),
      ),
    );
  });

  it("saves amount, year and milestone as null when left blank", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    await user.clear(await screen.findByLabelText("Rough amount you expect to need (optional)"));
    await user.clear(screen.getByLabelText("Target year (optional)"));
    await user.clear(screen.getByLabelText("Next milestone (optional)"));
    await user.click(screen.getByRole("button", { name: "Save goal" }));

    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        GOAL_PATH,
        expect.objectContaining({ amount_target: null, target_year: null, milestone: null }),
      ),
    );
  });

  it("checks the form before sending anything", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    const narrative = await narrativeField();

    await user.clear(narrative);
    await user.click(screen.getByRole("button", { name: "Save goal" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Describe what you're working toward.");

    await user.type(narrative, "Buy a first home");
    const amount = screen.getByLabelText("Rough amount you expect to need (optional)");
    await user.clear(amount);
    await user.type(amount, "-5");
    await user.click(screen.getByRole("button", { name: "Save goal" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Amount must be a whole number above 0");

    expect(patch).not.toHaveBeenCalled();
  });

  it("shows the server's message when it refuses the goal", async () => {
    const user = userEvent.setup();
    patch.mockRejectedValueOnce(new RelayApiError(422, "validation_error", "Target year must be within 50 years."));
    render(<HeirScreen />);
    await user.click(await screen.findByRole("button", { name: "Save goal" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Target year must be within 50 years.");
    expect(screen.queryByRole("button", { name: "Reload" })).not.toBeInTheDocument();
  });

  it("creates the first goal when there is none yet, and switches nothing on", async () => {
    const user = userEvent.setup();
    server.goal = null;
    render(<HeirScreen />);

    await user.selectOptions(await screen.findByLabelText("Kind of goal"), "home");
    await user.type(screen.getByLabelText("What are you working toward?"), "Buy a first home");
    await user.click(screen.getByRole("button", { name: "Save goal" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/families/fam-1/heir-goals", {
        goal_kind: "home",
        description_private: "Buy a first home",
        amount_target: null,
        target_year: null,
        horizon_min_years: null,
        horizon_max_years: null,
        milestone: null,
      }),
    );
    expect(patch).not.toHaveBeenCalled();
    expect(put).not.toHaveBeenCalled();
    // Once the goal exists the sharing switches become usable (and are still off).
    await waitFor(() => expect(screen.getByRole("switch", { name: /Share a goal summary/ })).toBeEnabled());
    expect(screen.getByRole("switch", { name: /Share a goal summary/ })).not.toBeChecked();
  });
});

describe("GoalSharing", () => {
  it("starts with both switches off and says Sarah sees nothing until one is on", async () => {
    render(<HeirScreen />);

    expect(await summarySwitch()).not.toBeChecked();
    expect(await detailSwitch()).not.toBeChecked();
    expect(
      screen.getByRole("switch", {
        name: "Share a goal summary with Sarah (type, rough amount, timeframe)",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("switch", {
        name: "Also share full details (exact amount, year, milestone, your notes)",
      }),
    ).toBeInTheDocument();
    expect(put).not.toHaveBeenCalled();
  });

  it("turning details on while the summary is off sends the detail grant, and both switches are on after the refresh", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    const summary = await summarySwitch();
    const detail = await detailSwitch();

    await user.click(detail);

    expect(put).toHaveBeenCalledTimes(1);
    expect(put).toHaveBeenCalledWith(CONSENT_PATH, {
      scope: "goal_detail",
      recipient_person_id: "p-sarah",
      active: true,
    });
    await waitFor(() => expect(summary).toBeChecked());
    expect(detail).toBeChecked();
  });

  it("turning the summary on sends only the summary grant", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    const summary = await summarySwitch();

    await user.click(summary);

    expect(put).toHaveBeenCalledWith(CONSENT_PATH, {
      scope: "goal_summary",
      recipient_person_id: "p-sarah",
      active: true,
    });
    await waitFor(() => expect(summary).toBeChecked());
    expect(await detailSwitch()).not.toBeChecked();
  });

  it("turning the summary off while details are on revokes it, and both switches are off after the refresh", async () => {
    const user = userEvent.setup();
    server.sharing = { advisor_summary: true, advisor_detail: true };
    render(<HeirScreen />);
    const summary = await summarySwitch();
    const detail = await detailSwitch();
    expect(summary).toBeChecked();
    expect(detail).toBeChecked();

    await user.click(summary);

    expect(put).toHaveBeenCalledWith(CONSENT_PATH, {
      scope: "goal_summary",
      recipient_person_id: "p-sarah",
      active: false,
    });
    await waitFor(() => expect(summary).not.toBeChecked());
    expect(detail).not.toBeChecked();
  });

  it("leaves the switch where the server has it and says so when the change fails", async () => {
    const user = userEvent.setup();
    put.mockRejectedValueOnce(new RelayApiError(403, "consent_not_permitted", "You cannot change this."));
    render(<HeirScreen />);
    const summary = await summarySwitch();

    await user.click(summary);

    expect(await screen.findByRole("alert")).toHaveTextContent("You cannot change this.");
    expect(summary).not.toBeChecked();
  });

  it("cannot be switched on before there is a goal to share", async () => {
    server.goal = null;
    render(<HeirScreen />);

    expect(await summarySwitch()).toBeDisabled();
    expect(await detailSwitch()).toBeDisabled();
    expect(screen.getByText("Save a goal first, then choose what to share.")).toBeInTheDocument();
  });

  it("sends nothing and says why when the advisor's account id is missing from the snapshot", async () => {
    const user = userEvent.setup();
    // What a backend that does not yet name the recipient would send.
    server.advisor = { display_name: "Sarah Lin" } as HeirSnapshot["advisor"];
    render(<HeirScreen />);
    const summary = await summarySwitch();
    const detail = await detailSwitch();

    expect(summary).toBeDisabled();
    expect(detail).toBeDisabled();
    expect(
      screen.getByText("Sharing isn't available yet because Sarah's account could not be identified. Nothing has been shared."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Save a goal first, then choose what to share.")).not.toBeInTheDocument();
    await user.click(summary);
    await user.click(detail);
    expect(put).not.toHaveBeenCalled();
  });

  it("asks for a goal first, not for an account id, when there is no goal and no advisor id", async () => {
    server.goal = null;
    server.advisor = { display_name: "Sarah Lin" } as HeirSnapshot["advisor"];
    render(<HeirScreen />);

    expect(await summarySwitch()).toBeDisabled();
    expect(screen.getByText("Save a goal first, then choose what to share.")).toBeInTheDocument();
    expect(screen.queryByText(/could not be identified/)).not.toBeInTheDocument();
  });
});

describe("ApprovedMemory", () => {
  it("shows each explanation with its source, quoted words and who verified it", () => {
    render(
      <ApprovedMemory
        decisions={[
          makeHeirDecision(),
          makeHeirDecision({
            decision_id: "d-retain",
            date: "2026-04-15",
            title: "Retain the family business holding",
            rationale: null,
            source_title: "Meeting transcript, Robert Morgan and Sarah Lin, 2026-04-15",
            locator: { start_seconds: 113, end_seconds: 148, quoted_span: "We want to keep control of the business in the family." },
          }),
        ]}
      />,
    );

    const reserve = screen.getByRole("article", { name: "Build a two-year liquidity reserve" });
    expect(within(reserve).getByText("9 Nov 2023")).toBeInTheDocument();
    // The meeting note quotes the rationale word for word, so the sentence is shown once.
    expect(within(reserve).getAllByText(/Robert wanted enough near-term cash/)).toHaveLength(1);
    expect(within(reserve).getByText("Source: Advisor meeting note, 2023-11-09 · Page 1")).toBeInTheDocument();
    expect(within(reserve).getByText("Verified by Sarah Lin")).toBeInTheDocument();

    const retained = screen.getByRole("article", { name: "Retain the family business holding" });
    expect(within(retained).getByText("Rationale not documented")).toBeInTheDocument();
    expect(within(retained).getByText(/We want to keep control of the business in the family\./)).toBeInTheDocument();
    expect(
      within(retained).getByText("Source: Meeting transcript, Robert Morgan and Sarah Lin, 2026-04-15 · 1:53–2:28"),
    ).toBeInTheDocument();
  });

  it("explains an empty list, and lets a caller word it for its own audience", () => {
    const { rerender } = render(<ApprovedMemory decisions={[]} />);
    expect(screen.getByText("Robert hasn't shared any decision explanations yet.")).toBeInTheDocument();

    rerender(<ApprovedMemory decisions={[]} emptyText="Nothing is shared with James yet." />);
    expect(screen.getByText("Nothing is shared with James yet.")).toBeInTheDocument();
    expect(screen.queryByText("Robert hasn't shared any decision explanations yet.")).not.toBeInTheDocument();
  });

  it("is what the family member screen renders for the shared decisions", async () => {
    server.decisions = [makeHeirDecision()];
    render(<HeirScreen />);

    expect(await screen.findByRole("article", { name: "Build a two-year liquidity reserve" })).toBeInTheDocument();
    expect(screen.queryByText("Robert hasn't shared any decision explanations yet.")).not.toBeInTheDocument();
  });

  it("shows the empty state on the screen when nothing is shared", async () => {
    render(<HeirScreen />);
    expect(await screen.findByText("Robert hasn't shared any decision explanations yet.")).toBeInTheDocument();
  });
});

describe("MemoryAsk", () => {
  const askRegion = () => screen.findByRole("region", { name: "Ask about a shared decision" });

  it("asks the suggested question in one click and cites the approved record that answers it", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    const region = within(await askRegion());

    await user.click(region.getByRole("button", { name: "Why was family control important?" }));

    expect(post).toHaveBeenCalledWith(ASK_PATH, { question: "Why was family control important?" });
    expect(await region.findByText(RETAIN_TITLE)).toBeInTheDocument();
    expect(region.getByText(/keep control of the business in the family/)).toBeInTheDocument();
    expect(
      region.getByText("Source: Meeting transcript, Robert Morgan and Sarah Lin, 2026-04-15 · 1:53–2:28"),
    ).toBeInTheDocument();
    expect(region.getByText("Verified by Sarah Lin")).toBeInTheDocument();
    expect(region.getByRole("textbox", { name: "Your question" })).toHaveValue("Why was family control important?");
  });

  it("shows a refusal reason exactly as the server words it", async () => {
    const user = userEvent.setup();
    const reason = "Heirloom can't answer questions about estate plans, balances or inheritance.";
    server.answer = { status: "refused", reason, matches: [] };
    render(<HeirScreen />);
    const region = within(await askRegion());

    await user.type(region.getByRole("textbox", { name: "Your question" }), "What will I get?");
    await user.click(region.getByRole("button", { name: "Ask" }));

    expect(post).toHaveBeenCalledWith(ASK_PATH, { question: "What will I get?" });
    expect(await region.findByText(reason)).toBeInTheDocument();
    expect(region.queryByRole("article")).not.toBeInTheDocument();
  });

  it("shows 'No approved record answers that.' when nothing matches", async () => {
    const user = userEvent.setup();
    server.answer = { status: "refused", reason: "No approved record answers that.", matches: [] };
    render(<HeirScreen />);
    const region = within(await askRegion());

    await user.type(region.getByRole("textbox", { name: "Your question" }), "Why a reserve?");
    await user.click(region.getByRole("button", { name: "Ask" }));

    expect(await region.findByText("No approved record answers that.")).toBeInTheDocument();
  });

  it("will not send an empty question, and replaces the previous answer with the next one", async () => {
    const user = userEvent.setup();
    render(<HeirScreen />);
    const region = within(await askRegion());
    expect(region.getByRole("button", { name: "Ask" })).toBeDisabled();

    await user.click(region.getByRole("button", { name: "Why was family control important?" }));
    await region.findByText(RETAIN_TITLE);

    server.answer = { status: "refused", reason: "No approved record answers that.", matches: [] };
    const box = region.getByRole("textbox", { name: "Your question" });
    await user.clear(box);
    await user.type(box, "Why a reserve?");
    await user.click(region.getByRole("button", { name: "Ask" }));

    expect(await region.findByText("No approved record answers that.")).toBeInTheDocument();
    expect(region.queryByText(RETAIN_TITLE)).not.toBeInTheDocument();
  });

  it("says so when the question could not be asked", async () => {
    const user = userEvent.setup();
    post.mockRejectedValueOnce(new RelayApiError(500, "http_error", "Request failed with status 500"));
    render(<HeirScreen />);
    const region = within(await askRegion());

    await user.click(region.getByRole("button", { name: "Why was family control important?" }));

    expect(await region.findByRole("alert")).toHaveTextContent("Request failed with status 500");
  });
});

describe("InvitationCard", () => {
  const invitation: InvitationView = {
    from_display: "Sarah Lin",
    text: "Sarah would like to invite you to a short meeting about your goals and how she can help.",
    status: "approved",
  };

  it("shows who invited the family member and the invitation text", () => {
    render(<InvitationCard invitation={invitation} />);
    expect(screen.getByText("An invitation from Sarah Lin")).toBeInTheDocument();
    expect(screen.getByText(invitation.text)).toBeInTheDocument();
  });

  it("appears on the screen only when there are invitations", async () => {
    const { unmount } = render(<HeirScreen />);
    await narrativeField();
    expect(screen.queryByText(/An invitation from/)).not.toBeInTheDocument();
    unmount();

    server.invitations = [invitation];
    render(<HeirScreen />);
    expect(await screen.findByText("An invitation from Sarah Lin")).toBeInTheDocument();
  });
});

describe("heir screen wording", () => {
  it("shows no inheritance wording, asset names, values or beneficiary information, including in the answer to a question", async () => {
    const user = userEvent.setup();
    // The decision Robert shares in the demo, with a goal narrative of the family member's own that
    // carries no dollar amount, so that the text fields can be scanned along with the page.
    server.goal = makeHeirGoal({ description_private: "Build a software company with two friends." });
    server.decisions = [
      makeHeirDecision(),
      makeRetainDecision(),
      makeHeirDecision({
        decision_id: "d-avoid",
        date: "2020-03-18",
        title: "Avoid a reactive sale during the market drawdown",
        rationale: "Robert and Sarah documented a long investment horizon and agreed to review objectives before changing holdings.",
        source_title: "Advisor meeting note, 2020-03-18",
        locator: { page: 1, quoted_span: "Robert and Sarah documented a long investment horizon and agreed to review objectives before changing holdings." },
        asset_kind: "public_equity",
      }),
    ];
    server.invitations = [
      {
        from_display: "Sarah Lin",
        text: "Sarah would like to invite you to a short meeting about your goals and how she can help.",
        status: "approved",
      },
    ];
    server.sharing = { advisor_summary: true, advisor_detail: true };
    render(<HeirScreen />);
    await screen.findByRole("article", { name: RETAIN_TITLE });
    const region = within(await screen.findByRole("region", { name: "Ask about a shared decision" }));
    await user.click(region.getByRole("button", { name: "Why was family control important?" }));
    expect(await region.findByText(/keep control of the business in the family/)).toBeInTheDocument();

    const text = screenText(document.body);

    // The scan sees the shared decision, the answer, the invitation and what is typed into the goal.
    expect(text).toContain(RETAIN_TITLE);
    expect(text).toContain("Verified by Sarah Lin");
    expect(text).toContain("An invitation from Sarah Lin");
    expect(text).toContain("Build a software company with two friends.");
    expect(text).not.toMatch(/inherit/i);
    expect(text).not.toContain("LLC");
    expect(text).not.toContain("$5");
    expect(text).not.toMatch(/beneficiar/i);
  });
});
