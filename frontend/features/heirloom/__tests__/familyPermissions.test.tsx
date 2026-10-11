import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RelayApiError } from "@/features/heirloom/api/client";
import FamilyPermissions from "@/features/heirloom/components/FamilyPermissions";
import type { AdvisorDecisionDTO, GoalSharingLevel, HeirDecisionView } from "@/features/heirloom/types/contracts";
import { envelope, makeDecision, makeHeirSharing, makeSnapshot } from "./advisorFixtures";
import { makeRetainDecision } from "./heirFixtures";

const get = vi.hoisted(() => vi.fn());
const put = vi.hoisted(() => vi.fn());
vi.mock("@/features/heirloom/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/heirloom/api/client")>();
  return { ...actual, default: { get, put, post: vi.fn(), patch: vi.fn() } };
});

const PREVIEW_PATH = "/families/fam-1/heir-preview";
const CONSENT_PATH = "/families/fam-1/consents/d-retain";
const NOTE = "Robert asked that James can read why we kept the LLC interest";
const TRANSCRIPT_TITLE = "Meeting transcript, Robert Morgan and Sarah Lin, 2026-04-15";
const SHARE = "Record Robert's instruction to share";
const STOP = "Record instruction to stop sharing";

function verified(overrides: Partial<AdvisorDecisionDTO> = {}): AdvisorDecisionDTO {
  return makeDecision({
    verification_status: "verified",
    verified_by_display: "Sarah Lin",
    heir_sharing: makeHeirSharing(),
    ...overrides,
  });
}

function advisorRecordedShare() {
  return makeHeirSharing({
    shared: true,
    recorded_via: "advisor_recorded",
    recorded_by_display: "Sarah Lin",
    basis_date: "2026-04-15",
    basis_note: NOTE,
    basis_source_ref: "meeting-2026-04-15",
    basis_source_title: TRANSCRIPT_TITLE,
    updated_at: "2026-10-10T12:00:00Z",
  });
}

/** What James currently sees; a test changes it to play "the server applied the instruction". */
let preview: HeirDecisionView[];

beforeEach(() => {
  preview = [];
  get.mockReset();
  get.mockImplementation(async (path: string) => {
    if (path === PREVIEW_PATH) return envelope({ approved_decisions: preview });
    throw new Error(`unexpected GET ${path}`);
  });
  put.mockReset();
  put.mockResolvedValue(envelope({ grant: {}, consent_revision: 2 }));
});

function tab(decisions: AdvisorDecisionDTO[], goalSharing: GoalSharingLevel, onChanged: () => void) {
  return (
    <FamilyPermissions
      familyId="fam-1"
      snapshot={makeSnapshot({ decisions, goal_sharing: goalSharing })}
      onChanged={onChanged}
    />
  );
}

function renderTab(decisions: AdvisorDecisionDTO[], extra: { goal_sharing?: GoalSharingLevel } = {}) {
  const onChanged = vi.fn();
  const goalSharing = extra.goal_sharing ?? "summary";
  const { rerender } = render(tab(decisions, goalSharing, onChanged));
  return { onChanged, update: (next: AdvisorDecisionDTO[]) => rerender(tab(next, goalSharing, onChanged)) };
}

function row(name: string) {
  return screen.getByRole("article", { name });
}

const RETAIN_ROW = "Keep the family LLC interest rather than force a sale";

async function openForm(buttonName = SHARE) {
  await userEvent.click(within(row(RETAIN_ROW)).getByRole("button", { name: buttonName }));
  return screen.getByRole("form", { name: /instruction/i });
}

async function fillForm(
  form: HTMLElement,
  values: { date?: string; note?: string; source?: string },
) {
  if (values.date) await userEvent.type(within(form).getByLabelText("Conversation date"), values.date);
  if (values.note) await userEvent.type(within(form).getByLabelText("What Robert said"), values.note);
  if (values.source) await userEvent.selectOptions(within(form).getByLabelText("Source (optional)"), values.source);
}

describe("FamilyPermissions", () => {
  it("states what the advisor records, with the legal note and the fixed rows", async () => {
    renderTab([verified()]);

    expect(screen.getByRole("heading", { name: "Robert's sharing instructions" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Record what Robert asked you to share with James. Each change must cite the conversation it came from.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Estate-plan details — Off (not shareable in this pilot)")).toBeInTheDocument();
    expect(screen.getByText("Account balances — Not available in this pilot")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Recorded instructions are an illustrative record, not a legally sufficient client authorization. Production use requires written client authorization and compliance review.",
      ),
    ).toBeInTheDocument();

    const preserve = screen.getByRole("region", { name: "What Robert wants to preserve" });
    expect(within(preserve).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "Family control of the business",
      "Avoid forced sales",
      "Long-term growth",
      "Charitable purpose",
    ]);
    await screen.findByRole("region", { name: "Exactly what James sees" });
  });

  it("submits recorded instruction with basis", async () => {
    const { onChanged } = renderTab([verified({ id: "d-retain" })]);
    const form = await openForm();

    await fillForm(form, { date: "2026-04-15", note: NOTE, source: "meeting-2026-04-15" });
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(put).toHaveBeenCalledTimes(1);
    expect(put).toHaveBeenCalledWith(CONSENT_PATH, {
      scope: "decision_excerpt",
      recipient_person_id: "p-james",
      active: true,
      basis: { conversation_date: "2026-04-15", note: NOTE, source_ref: "meeting-2026-04-15" },
    });
    // The form closes once the server has recorded the change.
    expect(screen.queryByRole("form", { name: /instruction/i })).not.toBeInTheDocument();
  });

  it("sends no source_ref when no source is chosen, and trims the note", async () => {
    renderTab([verified({ id: "d-retain" })]);
    const form = await openForm();

    await fillForm(form, { date: "2026-04-15", note: `  ${NOTE}  ` });
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    expect(put.mock.calls[0][1].basis).toStrictEqual({ conversation_date: "2026-04-15", note: NOTE });
  });

  it("records an instruction to stop sharing with active false", async () => {
    renderTab([verified({ id: "d-retain", heir_sharing: advisorRecordedShare() })]);
    const form = await openForm(STOP);

    await fillForm(form, { date: "2026-05-02", note: "Robert asked us to stop sharing this with James for now" });
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    expect(put.mock.calls[0][1]).toMatchObject({ scope: "decision_excerpt", active: false });
  });

  it("empty note blocks submit", async () => {
    const { onChanged } = renderTab([verified({ id: "d-retain" })]);
    const form = await openForm();

    await fillForm(form, { date: "2026-04-15" });
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));

    expect(within(form).getByRole("alert")).toHaveTextContent("Write what Robert said");
    expect(within(form).getByLabelText("What Robert said")).toBeInvalid();
    // A note of only spaces is empty too.
    await userEvent.type(within(form).getByLabelText("What Robert said"), "   ");
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("Write what Robert said");
    expect(put).not.toHaveBeenCalled();
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("a missing or future conversation date blocks submit", async () => {
    renderTab([verified({ id: "d-retain" })]);
    const form = await openForm();

    await fillForm(form, { note: NOTE });
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("Enter the date of the conversation");

    await userEvent.type(within(form).getByLabelText("Conversation date"), "2099-01-01");
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("The conversation date can't be in the future");
    expect(put).not.toHaveBeenCalled();
  });

  it("shows the server's message inline and keeps the form open when the change is refused", async () => {
    put.mockRejectedValueOnce(
      new RelayApiError(422, "unknown_source", "That source is not a conversation in this family's record."),
    );
    const { onChanged } = renderTab([verified({ id: "d-retain" })]);
    const form = await openForm();

    await fillForm(form, { date: "2026-04-15", note: NOTE, source: "meeting-2026-04-15" });
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));

    expect(await within(form).findByRole("alert")).toHaveTextContent(
      "That source is not a conversation in this family's record.",
    );
    expect(onChanged).not.toHaveBeenCalled();
    // What the advisor typed is still there to correct.
    expect(within(form).getByLabelText("What Robert said")).toHaveValue(NOTE);
  });

  it("records what the advisor chose even if the sharing state changes while the form is open", async () => {
    const { update } = renderTab([verified({ id: "d-retain" })]);
    const form = await openForm();
    await fillForm(form, { date: "2026-04-15", note: NOTE });

    // A refetch (say Robert shared it himself) arrives mid-entry and flips the row to "Shared".
    update([verified({ id: "d-retain", heir_sharing: makeHeirSharing({ shared: true, recorded_via: "self" }) })]);
    expect(screen.getByRole("form", { name: "Record instruction to share" })).toBeInTheDocument();
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    expect(put.mock.calls[0][1]).toMatchObject({ active: true });
  });

  it("cancel closes the form without a request", async () => {
    renderTab([verified({ id: "d-retain" })]);
    const form = await openForm();

    await userEvent.click(within(form).getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("form", { name: /instruction/i })).not.toBeInTheDocument();
    expect(within(row(RETAIN_ROW)).getByRole("button", { name: SHARE })).toHaveFocus();
    expect(put).not.toHaveBeenCalled();
  });

  it("candidate decision has no control", () => {
    renderTab([makeDecision({ id: "d-cand", verification_status: "candidate", heir_sharing: null })]);

    const candidate = row(RETAIN_ROW);
    expect(within(candidate).getByText("Verify in Decision memory first")).toBeInTheDocument();
    expect(within(candidate).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /instruction/ })).not.toBeInTheDocument();
  });

  it("rejected decision has no control", () => {
    renderTab([makeDecision({ verification_status: "rejected", heir_sharing: null })]);
    expect(within(row(RETAIN_ROW)).getByText("Verify in Decision memory first")).toBeInTheDocument();
    expect(within(row(RETAIN_ROW)).queryByRole("button")).not.toBeInTheDocument();
  });

  it("verified and never shared says Not shared and offers to record a share", () => {
    renderTab([verified()]);
    const r = row(RETAIN_ROW);
    expect(within(r).getByText("Not shared")).toBeInTheDocument();
    expect(within(r).queryByText(/Recorded by/)).not.toBeInTheDocument();
    expect(within(r).getByRole("button", { name: SHARE })).toBeInTheDocument();
  });

  it("shows provenance for advisor-recorded share", () => {
    renderTab([verified({ heir_sharing: advisorRecordedShare() })]);

    const r = row(RETAIN_ROW);
    expect(within(r).getByText("Shared with James")).toBeInTheDocument();
    expect(within(r).getByText("Recorded by Sarah Lin from a conversation on 15 Apr 2026")).toBeInTheDocument();
    expect(within(r).getByText(NOTE)).toBeInTheDocument();
    expect(within(r).getByText(`Source: ${TRANSCRIPT_TITLE}`)).toBeInTheDocument();
    expect(within(r).getByRole("button", { name: STOP })).toBeInTheDocument();
    expect(within(r).queryByRole("button", { name: SHARE })).not.toBeInTheDocument();
  });

  it("says Shared by Robert when Robert shared it himself", () => {
    renderTab([verified({ heir_sharing: makeHeirSharing({ shared: true, recorded_via: "self" }) })]);

    const r = row(RETAIN_ROW);
    expect(within(r).getByText("Shared with James")).toBeInTheDocument();
    expect(within(r).getByText("Shared by Robert")).toBeInTheDocument();
    expect(within(r).queryByText(/Recorded by/)).not.toBeInTheDocument();
  });

  it("keeps the latest recorded instruction visible after sharing is stopped", () => {
    renderTab([
      verified({
        heir_sharing: {
          ...advisorRecordedShare(),
          shared: false,
          basis_date: "2026-05-02",
          basis_note: "Robert asked us to stop sharing this",
        },
      }),
    ]);

    const r = row(RETAIN_ROW);
    expect(within(r).getByText("Not shared")).toBeInTheDocument();
    expect(within(r).getByText("Recorded by Sarah Lin from a conversation on 2 May 2026")).toBeInTheDocument();
    expect(within(r).getByText("Robert asked us to stop sharing this")).toBeInTheDocument();
    expect(within(r).getByRole("button", { name: SHARE })).toBeInTheDocument();
  });

  it("lists decisions newest first with date and status", () => {
    renderTab([
      verified({ id: "d-old", action: "Build a two-year liquidity reserve", decision_date: "2023-11-09" }),
      verified({ id: "d-retain" }),
    ]);
    const titles = screen.getAllByRole("heading", { level: 4 }).map((h) => h.textContent);
    expect(titles).toEqual([RETAIN_ROW, "Build a two-year liquidity reserve"]);
    expect(within(row("Build a two-year liquidity reserve")).getByText(/9 Nov 2023/)).toBeInTheDocument();
  });

  it("james consent is read-only", () => {
    renderTab([verified()], { goal_sharing: "detail" });

    const own = screen.getByRole("region", { name: "James's own sharing" });
    expect(within(own).getByText("James controls whether you see his goals.")).toBeInTheDocument();
    expect(within(own).getByText("Details shared")).toBeInTheDocument();
    expect(within(own).queryAllByRole("button")).toHaveLength(0);
    expect(within(own).queryAllByRole("checkbox")).toHaveLength(0);
    expect(within(own).queryAllByRole("switch")).toHaveLength(0);
    expect(own.querySelector("input, select, textarea, button")).toBeNull();
  });

  it.each([
    ["not_shared", "Not shared"],
    ["summary", "Summary shared"],
    ["detail", "Details shared"],
  ] as const)("shows James's current goal sharing %s as %s", (level, text) => {
    renderTab([], { goal_sharing: level });
    expect(within(screen.getByRole("region", { name: "James's own sharing" })).getByText(text)).toBeInTheDocument();
  });

  it("heir preview refetches after a recorded change", async () => {
    renderTab([verified({ id: "d-retain" })]);
    const heirView = screen.getByRole("region", { name: "Exactly what James sees" });
    expect(await within(heirView).findByText("Robert hasn't shared any decision explanations yet.")).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(1);

    // The server applies the instruction; James now sees the explanation.
    preview = [makeRetainDecision({ decision_id: "d-retain" })];
    const form = await openForm();
    await fillForm(form, { date: "2026-04-15", note: NOTE });
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));

    // Exactly what James sees is rendered by the same component James's own screen uses.
    expect(
      await within(heirView).findByRole("article", {
        name: "Keep control of the family business rather than force a sale",
      }),
    ).toBeInTheDocument();
    expect(get.mock.calls.filter(([path]) => path === PREVIEW_PATH)).toHaveLength(2);
  });

  it("shows a recoverable error instead of a stale preview when the refetch fails", async () => {
    preview = [makeRetainDecision()];
    renderTab([verified({ id: "d-retain" })]);
    const heirView = screen.getByRole("region", { name: "Exactly what James sees" });
    await within(heirView).findByRole("article");

    get.mockRejectedValueOnce(new RelayApiError(500, "http_error", "Server error"));
    const form = await openForm();
    await fillForm(form, { date: "2026-04-15", note: NOTE });
    await userEvent.click(within(form).getByRole("button", { name: "Save recorded instruction" }));

    expect(await within(heirView).findByRole("alert")).toHaveTextContent("Server error");
    expect(within(heirView).queryByRole("article")).not.toBeInTheDocument();
    await userEvent.click(within(heirView).getByRole("button", { name: "Retry" }));
    expect(await within(heirView).findByRole("article")).toBeInTheDocument();
  });
});
