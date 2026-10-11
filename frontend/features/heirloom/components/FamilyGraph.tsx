"use client";

import "@xyflow/react/dist/style.css";
import { Controls, ReactFlow, type NodeMouseHandler } from "@xyflow/react";
import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import type { AssetDTO, GraphDTO } from "@/features/heirloom/types/contracts";
import EvidenceDrawer from "./EvidenceDrawer";
import { layoutGraph, nodeTypes, type RelayFlowNode } from "./graphNodes";
import { EmptyState, ErrorState, LoadingState } from "./StateViews";
import styles from "./FamilyGraph.module.css";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * The family knowledge graph as the server projects it for this viewer. The browser draws only
 * the nodes and edges it receives; "As of" asks the server for the graph on that date.
 */
export default function FamilyGraph({
  familyId,
  assets = [],
  refreshKey = 0,
  onChanged = () => {},
}: {
  familyId: string;
  /** Lets the evidence drawer offer the asset terms editor on asset nodes. */
  assets?: AssetDTO[];
  /** Bump to refetch, e.g. after a revision poll saw a change. */
  refreshKey?: number;
  onChanged?: () => void;
}) {
  const [asOf, setAsOf] = useState("");
  const [drawerRef, setDrawerRef] = useState<string | null>(null);
  const query = ISO_DATE.test(asOf) ? `?as_of=${asOf}` : "";
  const graph = useRelayQuery<GraphDTO>(`/families/${familyId}/graph${query}`, [refreshKey]);

  // Keep drawing the last graph while another date loads, instead of flashing a spinner.
  const [shown, setShown] = useState<GraphDTO | null>(null);
  if (graph.data && graph.data !== shown) setShown(graph.data);
  const data = graph.data ?? shown;
  const layout = useMemo(() => (data ? layoutGraph(data) : null), [data]);
  const evidence = useMemo(() => new Set(data?.evidence_refs ?? []), [data]);

  useEffect(() => {
    if (!drawerRef) return;
    function onKey(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") setDrawerRef(null);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerRef]);

  const open = (id: string | undefined) => {
    if (id && evidence.has(id)) setDrawerRef(id);
  };
  const onNodeClick: NodeMouseHandler<RelayFlowNode> = (_, node) => open(node.id);
  // Nodes are focusable; Enter on one opens its record like a click.
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Enter") return;
    const target = e.target as HTMLElement;
    if (target.classList.contains("react-flow__node")) open(target.dataset.id);
  };

  return (
    <section className={styles.graph} aria-label="Knowledge graph">
      <div className={styles.toolbar}>
        <label className={styles.asOf}>
          <span>As of</span>
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </label>
        {asOf ? (
          <button type="button" className={styles.clear} onClick={() => setAsOf("")}>
            Today
          </button>
        ) : null}
        <p className={styles.legend}>
          Solid: verified, or a generated forecast or flag · Dashed: candidate, contested or superseded ·
          Lock: not visible to heirs
        </p>
      </div>
      <div className={`${styles.stage} ${drawerRef ? styles.withDrawer : ""}`}>
        <div className={`${styles.canvas} ${graph.loading && data ? styles.stale : ""}`}>
          {graph.error ? (
            <ErrorState error={graph.error} onRetry={graph.reload} />
          ) : !layout ? (
            <LoadingState label="Loading graph" />
          ) : layout.nodes.length === 0 ? (
            <EmptyState
              title="Nothing on record"
              body={query ? "No records existed on this date." : "No records are on file for this family yet."}
            />
          ) : (
            <ReactFlow
              nodes={layout.nodes}
              edges={layout.edges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              onKeyDown={onKeyDown}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              fitView
              minZoom={0.3}
            >
              <Controls showInteractive={false} />
            </ReactFlow>
          )}
        </div>
        {drawerRef ? (
          <div className={styles.side}>
            <EvidenceDrawer
              key={drawerRef}
              familyId={familyId}
              recordRef={drawerRef}
              assets={assets}
              onClose={() => setDrawerRef(null)}
              onChanged={onChanged}
              backLabel="← Back to graph"
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
