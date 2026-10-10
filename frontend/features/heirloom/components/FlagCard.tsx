import { formatProbability } from "@/features/heirloom/format";
import type { EvidenceItem, EvidenceKind, InsightDTO } from "@/features/heirloom/types/contracts";
import StatusLabel from "./StatusLabel";
import styles from "./FlagCard.module.css";

// The chips tell the story in this order: what was intended, why, and what the heir wants.
const CHIP_PRIORITY: EvidenceKind[] = ["estate_intent", "decision", "goal", "asset", "estate_instrument", "forecast"];

export const EVIDENCE_KIND_LABEL: Record<EvidenceKind, string> = {
  estate_instrument: "Instrument",
  estate_intent: "Intent",
  asset: "Asset",
  decision: "Decision",
  goal: "Goal",
  forecast: "Forecast",
};

export function topEvidence(evidence: EvidenceItem[], count = 3): EvidenceItem[] {
  return [...evidence]
    .sort((a, b) => CHIP_PRIORITY.indexOf(a.kind) - CHIP_PRIORITY.indexOf(b.kind))
    .slice(0, count);
}

export default function FlagCard({ insight, onOpen }: { insight: InsightDTO; onOpen: (id: string) => void }) {
  const unknown = insight.headline_probability === null;
  return (
    <article className={styles.card}>
      <div className={styles.headline}>
        <span className={`${styles.probability} ${unknown ? styles.unknown : ""}`}>
          {formatProbability(insight.headline_probability)}
        </span>
        <span className={styles.condition}>{insight.headline_condition}</span>
      </div>
      <h3 className={styles.title}>
        <button type="button" className={styles.open} onClick={() => onOpen(insight.id)}>
          {insight.title}
        </button>
      </h3>
      <p className={styles.why}>{insight.why_now}</p>
      <ul className={styles.chips} aria-label="Evidence">
        {topEvidence(insight.evidence).map((e) => (
          <li key={`${e.kind}:${e.ref}`} className={styles.chip} data-testid="evidence-chip">
            <span className={styles.chipKind}>{EVIDENCE_KIND_LABEL[e.kind]}</span>
            {e.label}
          </li>
        ))}
      </ul>
      <StatusLabel tone="review" label="Review required" scope="Illustrative" />
    </article>
  );
}
