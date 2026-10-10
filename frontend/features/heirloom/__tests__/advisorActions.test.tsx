import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ActionPanel from "@/features/heirloom/components/ActionPanel";
import AssetTermsEditor from "@/features/heirloom/components/AssetTermsEditor";
import type { AdvisorActionDTO } from "@/features/heirloom/types/contracts";
import { envelope, makeInsight, makeSnapshot } from "./advisorFixtures";

const get = vi.hoisted(() => vi.fn());
const post = vi.hoisted(() => vi.fn());
const patch = vi.hoisted(() => vi.fn());
vi.mock("@/features/heirloom/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/heirloom/api/client")>();
  return { ...actual, default: { get, post, patch } };
});

function action(overrides: Partial<AdvisorActionDTO>): AdvisorActionDTO {
  return {
    id: "act-1",
    insight_id: "ins-1",
    insight_key: "liquidity_gap:asset-family-llc:goal-james-business",
    action_type: "parent_review",
    status: "draft",
    draft_text: "Agenda — review with Robert",
    outcome_note: null,
    created_at: "2026-10-10T12:00:00Z",
    updated_at: "2026-10-10T12:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  patch.mockReset();
  patch.mockResolvedValue(envelope({}));
});

describe("ActionPanel", () => {
  it("offers both actions, but no heir invitation on a legal review flag", async () => {
    get.mockResolvedValue(envelope([]));
    const { rerender } = render(<ActionPanel familyId="fam-1" insight={makeInsight()} />);
    expect(await screen.findByRole("button", { name: "Draft: Invite consenting heir to a meeting" })).toBeInTheDocument();
    expect(screen.getByText("Nothing is sent. Drafts stay inside Heirloom Relay for your review.")).toBeInTheDocument();

    rerender(<ActionPanel familyId="fam-1" insight={makeInsight({ type: "legal_review" })} />);
    expect(screen.getByRole("button", { name: "Draft: Review plan with client" })).toBeInTheDocument();
    expect(screen.queryByText("Invite consenting heir to a meeting")).not.toBeInTheDocument();
  });

  it("approves a draft and requires an outcome note before completing", async () => {
    get.mockResolvedValueOnce(envelope([action({ status: "draft" })]));
    get.mockResolvedValue(envelope([action({ status: "approved" })]));
    render(<ActionPanel familyId="fam-1" insight={makeInsight()} />);

    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(patch).toHaveBeenCalledWith("/families/fam-1/actions/act-1", { status: "approved" });

    await userEvent.click(await screen.findByRole("button", { name: "Mark completed" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Add an outcome note");
    expect(patch).toHaveBeenCalledTimes(1);

    await userEvent.type(screen.getByLabelText("Outcome note"), "Met Robert and counsel");
    await userEvent.click(screen.getByRole("button", { name: "Mark completed" }));
    await waitFor(() =>
      expect(patch).toHaveBeenLastCalledWith("/families/fam-1/actions/act-1", {
        status: "completed",
        outcome_note: "Met Robert and counsel",
      }),
    );
  });

  it("keeps showing the flag's action after a recompute gives the same insight_key a new id", async () => {
    get.mockResolvedValue(envelope([action({ status: "approved" })]));
    const { rerender } = render(<ActionPanel familyId="fam-1" insight={makeInsight()} />);
    expect(await screen.findByRole("button", { name: "Mark completed" })).toBeInTheDocument();

    rerender(<ActionPanel familyId="fam-1" insight={makeInsight({ id: "ins-2" })} />);
    expect(screen.getByRole("button", { name: "Mark completed" })).toBeInTheDocument();
    expect(screen.getByText("Agenda — review with Robert")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Draft: Review plan with client" })).not.toBeInTheDocument();
  });

  it("offers a new draft when the flag recurs after an action completed on an earlier insight row", async () => {
    get.mockResolvedValue(envelope([action({ status: "completed", outcome_note: "Met Robert" })]));
    const { rerender } = render(<ActionPanel familyId="fam-1" insight={makeInsight()} />);
    expect(await screen.findByText("Outcome: Met Robert")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Draft: Review plan with client" })).not.toBeInTheDocument();

    rerender(<ActionPanel familyId="fam-1" insight={makeInsight({ id: "ins-2" })} />);
    post.mockResolvedValue(envelope({}));
    await userEvent.click(screen.getByRole("button", { name: "Draft: Review plan with client" }));
    expect(post).toHaveBeenCalledWith("/families/fam-1/insights/ins-2/actions", { action_type: "parent_review" });
  });
});

describe("AssetTermsEditor", () => {
  const asset = makeSnapshot().assets[0];

  it("rejects an out-of-range sale delay without sending", async () => {
    render(<AssetTermsEditor familyId="fam-1" asset={asset} onSaved={() => {}} />);
    const delay = screen.getByLabelText("Sale delay (years)");
    await userEvent.clear(delay);
    await userEvent.type(delay, "12");
    await userEvent.click(screen.getByRole("button", { name: "Save terms" }));
    expect(screen.getByRole("alert")).toHaveTextContent("between 0 and 10");
    expect(patch).not.toHaveBeenCalled();
  });

  it("saves a blank liquidatable fraction as unknown and reports back", async () => {
    const onSaved = vi.fn();
    render(<AssetTermsEditor familyId="fam-1" asset={asset} onSaved={onSaved} />);
    await userEvent.clear(screen.getByLabelText(/Liquidatable fraction/));
    await userEvent.click(screen.getByRole("button", { name: "Save terms" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(patch).toHaveBeenCalledWith("/families/fam-1/assets/a-llc/terms", {
      partner_consent_process_documented: true,
      sale_delay_years: 2,
      liquidatable_fraction: null,
    });
  });
});
