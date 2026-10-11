import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import AdvisorScreen from "@/features/heirloom/screens/AdvisorScreen";
import { setSession } from "@/features/heirloom/session";
import { envelope, makeGraph, makeInsight, makeResult, makeSnapshot } from "./advisorFixtures";
import { installReactFlowJsdom } from "./reactFlowJsdom";

const get = vi.hoisted(() => vi.fn());
vi.mock("@/features/heirloom/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/heirloom/api/client")>();
  return { ...actual, default: { get, post: vi.fn(), patch: vi.fn() } };
});

/** What the server currently holds; a test changes it, then lets the revision poll notice. */
let server: { revision: number; consentRevision: number; goalsShared: boolean };

beforeAll(() => installReactFlowJsdom());

beforeEach(() => {
  // Only the poll interval is faked, so React Testing Library's waitFor still runs on real time.
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  server = { revision: 3, consentRevision: 1, goalsShared: true };
  setSession({
    token: "demo-token",
    familyId: "fam-1",
    person: { id: "p-sarah", displayName: "Sarah Lin", role: "advisor" },
  });
  get.mockReset();
  get.mockImplementation(async (path: string) => {
    if (path.endsWith("/revision")) {
      return envelope({ revision: server.revision, consent_revision: server.consentRevision });
    }
    if (path.endsWith("/snapshot")) {
      return envelope(makeSnapshot({ goal_sharing: server.goalsShared ? "summary" : "not_shared" }));
    }
    if (path.endsWith("/insights")) return envelope(server.goalsShared ? [makeInsight()] : []);
    if (path.includes("/forecasts/")) return envelope(makeResult());
    if (path.endsWith("/actions")) return envelope([]);
    if (path.includes("/graph")) return envelope(makeGraph());
    throw new Error(`unexpected GET ${path}`);
  });
});

afterEach(() => {
  vi.useRealTimers();
});

const calls = (fragment: string) => get.mock.calls.filter(([path]) => String(path).includes(fragment)).length;

/** Wait for the poll's baseline, then let one interval pass so it sees the server's new revision. */
async function nextPoll() {
  await waitFor(() => expect(calls("/revision")).toBeGreaterThan(0));
  const before = calls("/revision");
  await act(async () => {
    vi.advanceTimersByTime(2500);
  });
  await waitFor(() => expect(calls("/revision")).toBe(before + 1));
}

describe("AdvisorScreen revision poll", () => {
  it("closes an open flag sheet when the heir revokes sharing", async () => {
    render(<AdvisorScreen />);
    await userEvent.click(await screen.findByRole("button", { name: /Liquidity for James's goal/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // James revokes sharing in his own tab: consent revision moves and the insight is withdrawn.
    server = { ...server, consentRevision: 2, goalsShared: false };
    await nextPoll();

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByText("James has not shared any current goals.")).toBeInTheDocument();
  });

  it("refetches the knowledge graph when the revision changes", async () => {
    render(<AdvisorScreen />);
    await userEvent.click(await screen.findByRole("tab", { name: "Knowledge graph" }));
    await screen.findByTestId("rf__node-decision-retain-llc");
    expect(calls("/graph")).toBe(1);

    server = { ...server, revision: 4 };
    await nextPoll();

    await waitFor(() => expect(calls("/graph")).toBe(2));
    expect(calls("/snapshot")).toBe(2);
    expect(calls("/insights")).toBe(2);
  });
});
