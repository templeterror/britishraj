"use client";

import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import type { ActivityRow } from "@/features/heirloom/types/contracts";
import { EmptyState, ErrorState, LoadingState } from "./StateViews";
import { formatLabelDate } from "./StatusLabel";
import styles from "./ActivityLog.module.css";

const KIND_LABEL: Record<ActivityRow["kind"], string> = {
  action: "Action",
  audit: "Access",
  event: "Change",
};

/** "2026-10-10T12:05:00Z" -> "10 Oct 2026 · 12:05 UTC" (shown in UTC so every viewer sees the same time). */
function when(at: string): string {
  const time = /T(\d{2}:\d{2})/.exec(at)?.[1];
  return time ? `${formatLabelDate(at)} · ${time} UTC` : formatLabelDate(at);
}

/** The family's recent actions, access checks and domain events, newest first as the server returns them. */
export default function ActivityLog({ familyId, refreshKey = 0 }: { familyId: string; refreshKey?: number }) {
  const q = useRelayQuery<ActivityRow[]>(`/families/${familyId}/activity`, [refreshKey]);

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <LoadingState label="Loading activity" />;
  if (q.data.length === 0) return <EmptyState title="No activity yet" />;

  return (
    <section aria-label="Activity">
      <ol className={styles.list}>
        {q.data.map((row, i) => (
          <li key={`${row.at}-${i}`} className={styles.row}>
            <span className={styles.when}>{when(row.at)}</span>
            <span className={styles.kind}>{KIND_LABEL[row.kind] ?? row.kind}</span>
            <span className={styles.summary}>{row.summary}</span>
            <span className={styles.actor}>
              {row.actor_display ?? "System"}
              {row.allowed === false ? <strong className={styles.denied}>Denied</strong> : null}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
