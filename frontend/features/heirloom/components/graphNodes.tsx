import { Handle, Position, type Edge, type Node, type NodeProps, type NodeTypes } from "@xyflow/react";
import type {
  EvidenceStatus,
  GEdge,
  GNode,
  GraphClassification,
  GraphDTO,
  GraphNodeKind,
} from "@/features/heirloom/types/contracts";
import StatusLabel, { type StatusTone } from "./StatusLabel";
import styles from "./graphNodes.module.css";

export interface RelayNodeData extends Record<string, unknown> {
  node: GNode;
  hasEvidence: boolean;
}

export type RelayFlowNode = Node<RelayNodeData, GraphNodeKind>;

export const KIND_LABEL: Record<GraphNodeKind, string> = {
  person: "Person",
  asset: "Asset",
  instrument: "Document",
  intent: "Estate intent",
  decision: "Decision",
  goal: "Goal",
  forecast: "Forecast",
  insight: "Flag",
  restriction: "Restriction",
};

/** Layered columns, left to right: who → what the documents say → what is held → why → what it means. */
const COLUMNS: GraphNodeKind[][] = [
  ["person"],
  ["instrument", "intent"],
  ["asset", "restriction"],
  ["decision"],
  ["goal", "forecast", "insight"],
];

const COLUMN_WIDTH = 280;
const ROW_HEIGHT = 104;

const LOCK_LABEL: Partial<Record<GraphClassification, string>> = {
  advisor_only: "Advisor-only",
  internal_parent_advisor: "Parent and advisor only",
};

const EDGE_LABEL: Record<string, string> = {
  INTENDED_FOR: "intended for (revocable)",
};

function tone(status: EvidenceStatus): StatusTone {
  if (status === "candidate") return "candidate";
  if (status === "contested") return "review";
  if (status === "superseded") return "superseded";
  return "neutral";
}

function LockBadge({ label }: { label: string }) {
  return (
    <span className={styles.lock} data-testid="lock-badge" role="img" aria-label={label} title={label}>
      <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
        <rect x="3" y="7" width="10" height="7" rx="1.5" fill="currentColor" />
        <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </span>
  );
}

function RelayGraphNode({ data }: NodeProps<RelayFlowNode>) {
  const { node, hasEvidence } = data;
  // Anything not verified (a candidate, a superseded or contested record) is drawn dashed and says so.
  const dashed = node.evidence_status !== "verified";
  const lock = LOCK_LABEL[node.classification];
  return (
    <div
      className={`${styles.node} ${dashed ? styles.dashed : ""} ${hasEvidence ? styles.clickable : ""}`}
      data-dashed={dashed}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} className={styles.handle} />
      <div className={styles.top}>
        <span className={styles.kind}>{KIND_LABEL[node.kind]}</span>
        {lock ? <LockBadge label={lock} /> : null}
      </div>
      <span className={styles.label}>{node.label}</span>
      {dashed ? (
        <StatusLabel
          tone={tone(node.evidence_status)}
          label={node.evidence_status}
          date={node.evidence_status === "superseded" ? (node.valid_to ?? undefined) : undefined}
        />
      ) : null}
      <Handle type="source" position={Position.Right} isConnectable={false} className={styles.handle} />
    </div>
  );
}

export const nodeTypes: NodeTypes = {
  person: RelayGraphNode,
  asset: RelayGraphNode,
  instrument: RelayGraphNode,
  intent: RelayGraphNode,
  decision: RelayGraphNode,
  goal: RelayGraphNode,
  forecast: RelayGraphNode,
  insight: RelayGraphNode,
  restriction: RelayGraphNode,
};

function edgeId(e: GEdge): string {
  return `${e.type}:${e.source_id}->${e.target_id}`;
}

/**
 * Deterministic layered layout: a column per kind group, rows sorted by kind then record id, so the
 * same projection always draws the same picture. Edges whose endpoints are not in the projection are
 * dropped rather than drawn to an invented node.
 */
export function layoutGraph(graph: GraphDTO): { nodes: RelayFlowNode[]; edges: Edge[] } {
  const evidence = new Set(graph.evidence_refs);
  const nodes: RelayFlowNode[] = [];
  COLUMNS.forEach((kinds, col) => {
    graph.nodes
      .filter((n) => kinds.includes(n.kind))
      .sort((a, b) => kinds.indexOf(a.kind) - kinds.indexOf(b.kind) || a.record_id.localeCompare(b.record_id))
      .forEach((n, row) => {
        const hasEvidence = evidence.has(n.record_id);
        nodes.push({
          id: n.record_id,
          type: n.kind,
          position: { x: col * COLUMN_WIDTH, y: row * ROW_HEIGHT },
          data: { node: n, hasEvidence },
          ariaLabel: `${KIND_LABEL[n.kind]}: ${n.label}`,
          ariaRole: hasEvidence ? "button" : undefined,
        });
      });
  });

  const ids = new Set(nodes.map((n) => n.id));
  const edges: Edge[] = graph.edges
    .filter((e) => ids.has(e.source_id) && ids.has(e.target_id))
    .sort((a, b) => edgeId(a).localeCompare(edgeId(b)))
    .map((e) => ({
      id: edgeId(e),
      source: e.source_id,
      target: e.target_id,
      label: EDGE_LABEL[e.type],
      className: [e.type === "INTENDED_FOR" ? styles.intended : "", e.valid_to ? styles.ended : ""]
        .filter(Boolean)
        .join(" "),
      ariaLabel: `${e.type.toLowerCase().replace(/_/g, " ")} from ${e.source_id} to ${e.target_id}`,
    }));

  return { nodes, edges };
}
