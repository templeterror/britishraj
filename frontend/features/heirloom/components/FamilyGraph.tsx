"use client";

import "@xyflow/react/dist/style.css";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  ViewportPortal,
  type NodeMouseHandler,
} from "@xyflow/react";
import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import type { AssetDTO, GraphDTO } from "@/features/heirloom/types/contracts";
import EvidenceDrawer from "./EvidenceDrawer";
import { COLUMN_HEADERS, COLUMN_WIDTH, layoutGraph, nodeTypes, type RelayFlowNode } from "./graphNodes";
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
  const [focusId, setFocusId] = useState<string | null>(null);
  const query = ISO_DATE.test(asOf) ? `?as_of=${asOf}` : "";
  const graph = useRelayQuery<GraphDTO>(`/families/${familyId}/graph${query}`, [refreshKey]);

  // Keep drawing the last graph while another date loads, instead of flashing a spinner.
  const [shown, setShown] = useState<GraphDTO | null>(null);
  if (graph.data && graph.data !== shown) setShown(graph.data);
  const data = graph.data ?? shown;
  const layout = useMemo(() => (data ? layoutGraph(data) : null), [data]);
  const evidence = useMemo(() => new Set(data?.evidence_refs ?? []), [data]);
  const pictured = useMemo(() => {
    if (!layout) return null;
    if (!focusId) return layout;
    const linked = new Set<string>([focusId]);
    for (const edge of layout.edges) {
      if (edge.source === focusId || edge.target === focusId) {
        linked.add(edge.source);
        linked.add(edge.target);
      }
    }
    return {
      nodes: layout.nodes.map((node) => ({
        ...node,
        className: node.id === focusId ? styles.nodeFocus : linked.has(node.id) ? undefined : styles.nodeDim,
        data: { ...node.data, focused: node.id === focusId },
      })),
      edges: layout.edges.map((edge) => {
        const onPath = edge.source === focusId || edge.target === focusId;
        return {
          ...edge,
          className: [edge.className, onPath ? styles.edgeTrace : styles.edgeDim].filter(Boolean).join(" "),
        };
      }),
    };
  }, [layout, focusId]);

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
  const onNodeClick: NodeMouseHandler<RelayFlowNode> = (_, node) => {
    setFocusId(node.id);
    open(node.id);
  };
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
      </div>
      <div className={`${styles.stage} ${drawerRef ? styles.withDrawer : ""}`}>
        <div className={`${styles.canvas} ${graph.loading && data ? styles.stale : ""}`}>
          {graph.error ? (
            <ErrorState error={graph.error} onRetry={graph.reload} />
          ) : !pictured ? (
            <LoadingState label="Loading graph" />
          ) : pictured.nodes.length === 0 ? (
            <EmptyState
              title="Nothing on record"
              body={query ? "No records existed on this date." : "No records are on file for this family yet."}
            />
          ) : (
            <ReactFlow
              nodes={pictured.nodes}
              edges={pictured.edges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              onPaneClick={() => setFocusId(null)}
              onKeyDown={onKeyDown}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
              fitView
              fitViewOptions={{ padding: 0.12, minZoom: 0.72, maxZoom: 1 }}
              minZoom={0.45}
              maxZoom={1.4}
              colorMode="dark"
              panOnScroll
              proOptions={{ hideAttribution: true }}
            >
              <Background variant={BackgroundVariant.Dots} gap={18} size={1.15} color="rgba(255,255,255,0.14)" />
              <ViewportPortal>
                <div className={styles.guides}>
                  {COLUMN_HEADERS.map((label, index) => (
                    <div key={label} className={styles.guide} style={{ transform: `translate(${index * COLUMN_WIDTH}px, 0)` }}>
                      {label}
                    </div>
                  ))}
                </div>
              </ViewportPortal>
              <Controls showInteractive={false} position="bottom-right" className={styles.controls} />
              <MiniMap
                pannable
                zoomable={false}
                bgColor="#111114"
                maskColor="rgba(0, 0, 0, 0.55)"
                nodeColor="#1a1a1e"
                nodeStrokeColor="rgba(255,255,255,0.28)"
                className={styles.minimap}
              />
              <Panel position="bottom-left" className={styles.legend}>
                Solid: verified, or a generated forecast or flag · Dashed: candidate, contested or superseded ·
                Lock: not visible to heirs
              </Panel>
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
