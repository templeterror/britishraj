"use client";

import { useId } from "react";
import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import type { HeirPreviewDTO } from "@/features/heirloom/types/contracts";
import ApprovedMemory from "./ApprovedMemory";
import { ErrorState, LoadingState } from "./StateViews";
import styles from "./HeirPreview.module.css";

/**
 * Exactly what the family member sees: the server's own computation of their approved decisions,
 * drawn by the same component their screen uses. `refreshKey` refetches it after a change, and a
 * failed refetch shows the error rather than the previous, possibly out-of-date, list.
 */
export default function HeirPreview({
  familyId,
  heirName = "James",
  refreshKey = 0,
}: {
  familyId: string;
  heirName?: string;
  refreshKey?: number;
}) {
  const headingId = useId();
  const q = useRelayQuery<HeirPreviewDTO>(`/families/${familyId}/heir-preview`, [refreshKey]);

  return (
    <section className={styles.section} aria-labelledby={headingId} aria-busy={q.loading}>
      <h2 id={headingId} className={styles.heading}>
        {`Exactly what ${heirName} sees`}
      </h2>
      {q.error ? (
        <ErrorState error={q.error} onRetry={q.reload} />
      ) : !q.data ? (
        <LoadingState label="Loading preview" />
      ) : (
        <ApprovedMemory decisions={q.data.approved_decisions} />
      )}
    </section>
  );
}
