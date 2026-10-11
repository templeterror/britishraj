import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdvisorFlags } from "@/features/heirloom/screens/AdvisorScreen";
import { envelope, makeInsight, makeResult, makeSnapshot } from "./advisorFixtures";

const get = vi.hoisted(() => vi.fn());
const post = vi.hoisted(() => vi.fn());
const patch = vi.hoisted(() => vi.fn());
vi.mock("@/features/heirloom/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/heirloom/api/client")>();
  return { ...actual, default: { get, post, patch } };
});

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  patch.mockReset();
  get.mockImplementation(async (path: string) => {
    if (path.includes("/forecasts/sc-10-exit_delay_24m")) {
      return envelope(makeResult({ preset: "exit_delay_24m", cashAtGoalP50: 300_000 }));
    }
    if (path.includes("/forecasts/")) return envelope(makeResult());
    if (path.endsWith("/actions")) return envelope([]);
    throw new Error(`unexpected GET ${path}`);
  });
});

function renderFlags(insights = [makeInsight()], goalSharing: "summary" | "not_shared" = "summary") {
  const props = { familyId: "fam-1", onChanged: () => {} };
  const view = render(
    <AdvisorFlags {...props} snapshot={makeSnapshot({ goal_sharing: goalSharing })} insights={insights} />,
  );
  return {
    ...view,
    rerenderWith: (next: typeof insights, sharing: "summary" | "not_shared") =>
      view.rerender(
        <AdvisorFlags {...props} snapshot={makeSnapshot({ goal_sharing: sharing })} insights={next} />,
      ),
  };
}

describe("Advisor flag sheet", () => {
  it("opens on the headline scenario and fetches its forecast", async () => {
    renderFlags();
    await userEvent.click(screen.getByRole("button", { name: /Liquidity for James's goal/ }));

    const sheet = screen.getByRole("dialog");
    await waitFor(() => expect(get).toHaveBeenCalledWith("/families/fam-1/forecasts/sc-10-exit_delay_24m"));
    expect(within(sheet).getByRole("button", { name: "Exit +24 mo" })).toHaveAttribute("aria-pressed", "true");
    expect(within(sheet).getByRole("button", { name: "Year 10" })).toHaveAttribute("aria-pressed", "true");
    expect(await within(sheet).findByTestId("shortfall-zone")).toBeInTheDocument();

    await userEvent.click(within(sheet).getByRole("button", { name: "Base" }));
    await waitFor(() => expect(get).toHaveBeenCalledWith("/families/fam-1/forecasts/sc-10-base"));
    await waitFor(() => expect(within(sheet).queryByTestId("shortfall-zone")).not.toBeInTheDocument());
  });

  it("closes when insight no longer in list", async () => {
    const { rerenderWith } = renderFlags();
    await userEvent.click(screen.getByRole("button", { name: /Liquidity for James's goal/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // James revokes sharing: the next revision poll returns no insights.
    rerenderWith([], "not_shared");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("James has not shared any current goals.")).toBeInTheDocument();

    // The same insight id reappearing later does not reopen a sheet the advisor never reopened.
    rerenderWith([makeInsight()], "summary");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("stays open on the recomputed insight when only its id changes", async () => {
    const { rerenderWith } = renderFlags();
    await userEvent.click(screen.getByRole("button", { name: /Liquidity for James's goal/ }));

    rerenderWith([makeInsight({ id: "ins-2", headline_probability: 0.12 })], "summary");

    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByText("12%")).toBeInTheDocument();
  });

  it("shows the no-mismatch empty state when goals are shared but nothing is flagged", () => {
    renderFlags([], "summary");
    expect(screen.getByText("No open flags under current assumptions.")).toBeInTheDocument();
  });
});
