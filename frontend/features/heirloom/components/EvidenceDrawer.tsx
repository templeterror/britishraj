"use client";

import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import type { AssetDTO, EvidenceDTO, SourceLocator } from "@/features/heirloom/types/contracts";
import AssetTermsEditor from "./AssetTermsEditor";
import { EVIDENCE_KIND_LABEL } from "./FlagCard";
import { EmptyState, ErrorState, LoadingState } from "./StateViews";
import StatusLabel, { type StatusTone } from "./StatusLabel";
import styles from "./EvidenceDrawer.module.css";

function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function describeLocator(locator: SourceLocator | null): string | null {
  if (!locator) return null;
  if (typeof locator.start_seconds === "number" && typeof locator.end_seconds === "number") {
    return `${clock(locator.start_seconds)}–${clock(locator.end_seconds)}`;
  }
  if (typeof locator.page === "number") return `Page ${locator.page}`;
  return null;
}

function tone(status: string): StatusTone {
  if (status === "verified") return "verified";
  if (status === "candidate" || status === "contested") return "candidate";
  if (status === "superseded") return "superseded";
  return "neutral";
}

/** Source record behind one evidence step; the asset record also carries the access-terms editor. */
export default function EvidenceDrawer({
  familyId,
  recordRef,
  assets,
  onClose,
  onChanged,
}: {
  familyId: string;
  recordRef: string;
  assets: AssetDTO[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const q = useRelayQuery<EvidenceDTO>(`/families/${familyId}/evidence/${encodeURIComponent(recordRef)}`);
  const ev = q.data;
  const asset = ev?.kind === "asset" ? assets.find((a) => a.ref === recordRef || a.id === recordRef) : undefined;
  const where = describeLocator(ev?.locator ?? null);
  const quote = ev?.excerpt ?? ev?.locator?.quoted_span ?? null;

  return (
    <section className={styles.drawer} aria-label="Evidence record">
      <div className={styles.bar}>
        <button type="button" className={styles.back} onClick={onClose}>
          ← Back to flag
        </button>
      </div>
      {q.error ? (
        q.error.status === 404 ? (
          <EmptyState title="Record not available" body="This record is not available to you." />
        ) : (
          <ErrorState error={q.error} onRetry={q.reload} />
        )
      ) : !ev ? (
        <LoadingState label="Loading source record" />
      ) : (
        <div className={styles.body}>
          <span className={styles.kind}>{EVIDENCE_KIND_LABEL[ev.kind] ?? ev.kind}</span>
          <h3 className={styles.title}>{ev.title}</h3>
          <StatusLabel tone={tone(ev.status)} label={ev.status} scope={ev.qualifier ?? undefined} />
          {ev.document_title ? (
            <p className={styles.source}>
              {ev.document_title}
              {ev.document_date ? ` · ${ev.document_date}` : ""}
              {where ? ` · ${where}` : ""}
            </p>
          ) : null}
          {quote ? <blockquote className={styles.quote}>{quote}</blockquote> : null}
          {asset ? <AssetTermsEditor familyId={familyId} asset={asset} onSaved={onChanged} /> : null}
        </div>
      )}
    </section>
  );
}
