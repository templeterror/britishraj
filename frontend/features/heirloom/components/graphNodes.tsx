import {
  Handle,
  MarkerType,
  Position,
  type Edge,
  type EdgeMarker,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
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
  focused?: boolean;
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

export const COLUMN_HEADERS = ["Person", "Document", "Asset", "Decision", "Outcome"] as const;
export const COLUMN_WIDTH = 300;
const ROW_HEIGHT = 136;
const ROW_ORIGIN = 36;

const LOCK_LABEL: Partial<Record<GraphClassification, string>> = {
  advisor_only: "Advisor-only",
  internal_parent_advisor: "Parent and advisor only",
};

const EDGE_LABEL: Record<string, string> = {
  INTENDED_FOR: "intended for (revocable)",
};

const ACCENT = "#00dd94";
const EDGE_INK = "rgba(255,255,255,0.42)";

/**
 * Records whose evidence is pending, disputed or no longer current are drawn dashed and labelled.
 * "unknown" is left out on purpose: the server gives it to generated records (forecasts, flags)
 * that have no verification state, so they draw solid with no status label.
 */
const DASHED_TONE: Partial<Record<EvidenceStatus, StatusTone>> = {
  candidate: "candidate",
  contested: "review",
  superseded: "superseded",
};

function marker(color: string): EdgeMarker {
  return { type: MarkerType.ArrowClosed, width: 16, height: 16, color };
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

function KindMark({ kind }: { kind: GraphNodeKind }) {
  const d =
    kind === "instrument" || kind === "intent"
      ? "M4 2.5h5.2L12 5.2V13.5H4z M9 2.8V5.4h2.5"
      : kind === "asset"
        ? "M3 8.5 8 4l5 4.5V13H3z"
        : kind === "decision"
          ? "M3.5 8.2 6.4 11 12.5 4.5"
          : kind === "person"
            ? "M8 8.2a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4zM4.2 13.2c.5-1.8 2-2.8 3.8-2.8s3.3 1 3.8 2.8"
            : "M8 3.2 9.4 6.4 13 6.8 10.3 9.2 11.1 12.8 8 11 4.9 12.8 5.7 9.2 3 6.8 6.6 6.4z";
  return (
    <span className={styles.kindIcon} aria-hidden="true">
      <svg viewBox="0 0 16 16" width="12" height="12">
        <path d={d} fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

function RelayGraphNode({ data }: NodeProps<RelayFlowNode>) {
  const { node, hasEvidence, focused } = data;
  const dashedTone = DASHED_TONE[node.evidence_status];
  const dashed = dashedTone !== undefined;
  const lock = LOCK_LABEL[node.classification];
  return (
    <div
      className={`${styles.node} ${dashed ? styles.dashed : ""} ${hasEvidence ? styles.clickable : ""} ${focused ? styles.focused : ""}`}
      data-dashed={dashed}
      data-tone={node.evidence_status}
    >
      <Handle id="in" type="target" position={Position.Left} isConnectable={false} className={styles.handle} />
      <Handle id="in-back" type="target" position={Position.Right} isConnectable={false} className={styles.handle} />
      <div className={styles.top}>
        <span className={styles.kind}>
          <span className={styles.dot} />
          {KIND_LABEL[node.kind]}
        </span>
        {lock ? <LockBadge label={lock} /> : <KindMark kind={node.kind} />}
      </div>
      <span className={styles.label}>{node.label}</span>
      {dashedTone ? (
        <StatusLabel
          tone={dashedTone}
          label={node.evidence_status}
          date={node.evidence_status === "superseded" ? (node.valid_to ?? undefined) : undefined}
        />
      ) : null}
      <Handle id="out" type="source" position={Position.Right} isConnectable={false} className={styles.handle} />
      <Handle id="out-back" type="source" position={Position.Left} isConnectable={false} className={styles.handle} />
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
  const columnOf = new Map<string, number>();
  const statusOf = new Map(graph.nodes.map((n) => [n.record_id, n.evidence_status]));
  const nodes: RelayFlowNode[] = [];
  COLUMNS.forEach((kinds, col) => {
    graph.nodes
      .filter((n) => kinds.includes(n.kind))
      .sort((a, b) => kinds.indexOf(a.kind) - kinds.indexOf(b.kind) || a.record_id.localeCompare(b.record_id))
      .forEach((n, row) => {
        const hasEvidence = evidence.has(n.record_id);
        columnOf.set(n.record_id, col);
        nodes.push({
          id: n.record_id,
          type: n.kind,
          position: { x: col * COLUMN_WIDTH, y: ROW_ORIGIN + row * ROW_HEIGHT },
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
    .map((e) => {
      const forward = (columnOf.get(e.source_id) ?? 0) <= (columnOf.get(e.target_id) ?? 0);
      const dashed =
        Boolean(e.valid_to) ||
        statusOf.get(e.source_id) === "candidate" ||
        statusOf.get(e.source_id) === "contested" ||
        statusOf.get(e.source_id) === "superseded" ||
        statusOf.get(e.target_id) === "candidate" ||
        statusOf.get(e.target_id) === "contested" ||
        statusOf.get(e.target_id) === "superseded";
      const accent = e.type === "INTENDED_FOR";
      return {
        id: edgeId(e),
        source: e.source_id,
        target: e.target_id,
        sourceHandle: forward ? "out" : "out-back",
        targetHandle: forward ? "in" : "in-back",
        type: "default" as const,
        label: EDGE_LABEL[e.type],
        markerEnd: marker(accent ? ACCENT : EDGE_INK),
        style: {
          stroke: accent ? ACCENT : EDGE_INK,
          strokeWidth: accent ? 2 : 1.5,
          strokeDasharray: dashed ? "6 5" : undefined,
        },
        className: [accent ? styles.intended : "", e.valid_to ? styles.ended : ""].filter(Boolean).join(" "),
        ariaLabel: `${e.type.toLowerCase().replace(/_/g, " ")} from ${e.source_id} to ${e.target_id}`,
      };
    });

  return { nodes, edges };
}
