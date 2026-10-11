import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import FamilyGraph from "@/features/heirloom/components/FamilyGraph";
import { layoutGraph } from "@/features/heirloom/components/graphNodes";
import type { EvidenceDTO } from "@/features/heirloom/types/contracts";
import { envelope, makeGraph } from "./advisorFixtures";
import { installReactFlowJsdom } from "./reactFlowJsdom";

const get = vi.hoisted(() => vi.fn());
vi.mock("@/features/heirloom/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/heirloom/api/client")>();
  return { ...actual, default: { get, post: vi.fn(), patch: vi.fn() } };
});

const LETTER_EVIDENCE: EvidenceDTO = {
  record_ref: "intent-james-llc",
  title: "Robert's 40% membership interest",
  kind: "estate_intent",
  status: "verified",
  qualifier: "Revocable",
  document_title: "Estate planning letter, 2026",
  document_date: "2026-03-02",
  excerpt: "I intend my 40% membership interest in Morgan Family Holdings LLC to pass to my son James.",
  locator: null,
};

beforeAll(() => installReactFlowJsdom());

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(async (path: string) => {
    if (path.includes("/graph")) return envelope(makeGraph());
    if (path.endsWith("/evidence/intent-james-llc")) return envelope(LETTER_EVIDENCE);
    throw new Error(`unexpected GET ${path}`);
  });
});

describe("FamilyGraph", () => {
  it("renders a node per DTO node and a lock badge for advisor-only nodes", async () => {
    render(<FamilyGraph familyId="fam-1" />);
    const graph = makeGraph();

    for (const node of graph.nodes) {
      expect(await screen.findByTestId(`rf__node-${node.record_id}`)).toBeInTheDocument();
    }
    const restricted = graph.nodes.filter(
      (n) => n.classification === "advisor_only" || n.classification === "internal_parent_advisor",
    );
    expect(screen.getAllByTestId("lock-badge")).toHaveLength(restricted.length);
    expect(within(screen.getByTestId("rf__node-insight-liquidity")).getByTestId("lock-badge")).toHaveAttribute(
      "aria-label",
      "Advisor-only",
    );
    expect(within(screen.getByTestId("rf__node-person-james")).queryByTestId("lock-badge")).toBeNull();
    // A candidate is drawn dashed and says so in words.
    const candidate = screen.getByTestId("rf__node-decision-retain-llc");
    expect(within(candidate).getByText("candidate")).toBeInTheDocument();
    expect(candidate.querySelector("[data-dashed='true']")).not.toBeNull();
  });

  it("renders no node for ids absent from the DTO", async () => {
    const { container } = render(<FamilyGraph familyId="fam-1" />);
    await screen.findByTestId("rf__node-person-robert");

    expect(screen.queryByTestId("rf__node-goal-james-business")).toBeNull();
    expect(container.querySelectorAll(".react-flow__node")).toHaveLength(makeGraph().nodes.length);
  });

  it("refetches the projection for the chosen as-of date", async () => {
    render(<FamilyGraph familyId="fam-1" />);
    await screen.findByTestId("rf__node-person-robert");
    expect(get).toHaveBeenCalledWith("/families/fam-1/graph");

    fireEvent.change(screen.getByLabelText("As of"), { target: { value: "2025-01-01" } });
    await waitFor(() => expect(get).toHaveBeenCalledWith("/families/fam-1/graph?as_of=2025-01-01"));
  });

  it("opens the evidence drawer for a clicked node", async () => {
    render(<FamilyGraph familyId="fam-1" />);
    // fireEvent: user-event's pointer sequence trips d3-zoom's drag guard in jsdom.
    fireEvent.click(await screen.findByTestId("rf__node-intent-james-llc"));

    await waitFor(() => expect(get).toHaveBeenCalledWith("/families/fam-1/evidence/intent-james-llc"));
    const drawer = await screen.findByRole("region", { name: "Evidence record" });
    expect(await within(drawer).findByText(/pass to my son James/)).toBeInTheDocument();
    expect(within(drawer).getByText(/2026-03-02/)).toBeInTheDocument();

    await userEvent.click(within(drawer).getByRole("button", { name: "← Back to graph" }));
    expect(screen.queryByRole("region", { name: "Evidence record" })).toBeNull();
  });

  it("does not open a drawer for a node without evidence", async () => {
    render(<FamilyGraph familyId="fam-1" />);
    fireEvent.click(await screen.findByTestId("rf__node-person-robert"));
    expect(screen.queryByRole("region", { name: "Evidence record" })).toBeNull();
    expect(get).not.toHaveBeenCalledWith(expect.stringContaining("/evidence/"));
  });
});

describe("layoutGraph", () => {
  it("places kinds in fixed columns, labels the intent edge and drops dangling edges", () => {
    const { nodes, edges } = layoutGraph(makeGraph());
    const x = (id: string) => nodes.find((n) => n.id === id)?.position.x ?? NaN;

    expect(x("person-robert")).toBe(x("person-james"));
    expect(x("person-robert")).toBeLessThan(x("intent-james-llc"));
    expect(x("intent-james-llc")).toBe(x("instr-estate-letter-2026"));
    expect(x("intent-james-llc")).toBeLessThan(x("asset-family-llc"));
    expect(x("asset-family-llc")).toBeLessThan(x("decision-retain-llc"));
    expect(x("decision-retain-llc")).toBeLessThan(x("insight-liquidity"));

    const intended = edges.find((e) => e.source === "intent-james-llc" && e.target === "person-james");
    expect(intended?.label).toBe("intended for (revocable)");
    expect(edges.some((e) => e.target === "goal-james-business")).toBe(false);
    expect(edges).toHaveLength(4);
  });

  it("is deterministic regardless of DTO order", () => {
    const graph = makeGraph();
    const shuffled = { ...graph, nodes: [...graph.nodes].reverse(), edges: [...graph.edges].reverse() };
    const a = layoutGraph(graph);
    const b = layoutGraph(shuffled);
    const positions = (l: typeof a) => l.nodes.map((n) => [n.id, n.position.x, n.position.y]);
    expect(positions(b)).toEqual(positions(a));
    expect(b.edges.map((e) => e.id)).toEqual(a.edges.map((e) => e.id));
  });
});
