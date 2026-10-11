import type { HeirDecisionView, SourceLocator } from "@/features/heirloom/types/contracts";
import { describeLocator } from "./EvidenceDrawer";
import { EmptyState } from "./StateViews";
import StatusLabel, { formatLabelDate } from "./StatusLabel";
import styles from "./ApprovedMemory.module.css";

/** The words quoted from the source, where they came from, and who verified them. */
export function Citation({
  quote,
  sourceTitle,
  locator,
  verifiedBy,
}: {
  quote: string | null;
  sourceTitle: string | null;
  locator: SourceLocator | null;
  verifiedBy: string | null;
}) {
  const where = describeLocator(locator);
  const source = sourceTitle ? [`Source: ${sourceTitle}`, where].filter((p) => p !== null).join(" · ") : null;
  return (
    <div className={styles.citation}>
      {quote ? <blockquote className={styles.quote}>{quote}</blockquote> : null}
      {source ? <p className={styles.source}>{source}</p> : null}
      <StatusLabel tone="verified" label={verifiedBy ? `Verified by ${verifiedBy}` : "Verified"} />
    </div>
  );
}

/**
 * Decision explanations a parent chose to share, each with its citation. Used for the family
 * member's own view and for the parent's preview of it, so both see the same thing.
 */
export default function ApprovedMemory({
  decisions,
  emptyText = "Robert hasn't shared any decision explanations yet.",
}: {
  decisions: HeirDecisionView[];
  emptyText?: string;
}) {
  if (decisions.length === 0) return <EmptyState title={emptyText} />;
  return (
    <ul className={styles.list}>
      {decisions.map((d) => {
        // A meeting note often quotes the rationale word for word; show the words once.
        const span = typeof d.locator?.quoted_span === "string" ? d.locator.quoted_span : null;
        const quote = span !== null && span.trim() !== d.rationale?.trim() ? span : null;
        return (
          <li key={d.decision_id}>
            <article className={styles.item} aria-label={d.title}>
              <time className={styles.date} dateTime={d.date}>
                {formatLabelDate(d.date)}
              </time>
              <h3 className={styles.title}>{d.title}</h3>
              <p className={styles.rationale}>{d.rationale ?? "Rationale not documented"}</p>
              <Citation
                quote={quote}
                sourceTitle={d.source_title}
                locator={d.locator}
                verifiedBy={d.verified_by_display}
              />
            </article>
          </li>
        );
      })}
    </ul>
  );
}
