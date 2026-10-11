"use client";

import { useState } from "react";
import relay, { RelayApiError } from "@/features/heirloom/api/client";
import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import type { ActionType, AdvisorActionDTO, InsightDTO, UpdateActionBody } from "@/features/heirloom/types/contracts";
import { ErrorState } from "./StateViews";
import StatusLabel from "./StatusLabel";
import styles from "./ActionPanel.module.css";

const ACTION_LABEL: Record<ActionType, string> = {
  parent_review: "Review plan with client",
  heir_intro: "Invite consenting heir to a meeting",
};

function message(err: unknown): string {
  return err instanceof RelayApiError ? err.message : "The action could not be saved.";
}

function ActionItem({
  familyId,
  insightId,
  insightCreatedAt,
  type,
  action,
  onChanged,
}: {
  familyId: string;
  insightId: string;
  /** When the current insight row was created; separates a recurrence from the row's own history. */
  insightCreatedAt: string;
  type: ActionType;
  /** Latest action of this type for the insight, if any. */
  action: AdvisorActionDTO | undefined;
  onChanged: () => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(call: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await call();
      onChanged();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  const create = () =>
    run(() => relay.post(`/families/${familyId}/insights/${insightId}/actions`, { action_type: type }));
  const update = (body: UpdateActionBody) =>
    run(() => relay.patch(`/families/${familyId}/actions/${action?.id}`, body));
  const complete = () => {
    if (note.trim() === "") {
      setError("Add an outcome note before marking this completed.");
      return;
    }
    void update({ status: "completed", outcome_note: note.trim() });
  };

  // A completed action keeps the flag closed if it was completed on or after the current row was
  // created; it may have been carried over from an earlier row (actions keep their original
  // insight_id). Only a completion older than the current row means the flag recurred, and then
  // the advisor can start a fresh action for it.
  const completedBeforeRow =
    action?.status === "completed" && Date.parse(action.updated_at) < Date.parse(insightCreatedAt);
  const open = action && action.status !== "cancelled" && !completedBeforeRow;
  return (
    <li className={styles.item}>
      <h4 className={styles.heading}>{ACTION_LABEL[type]}</h4>
      {!open ? (
        <button type="button" className={styles.primary} disabled={busy} onClick={() => void create()}>
          Draft: {ACTION_LABEL[type]}
        </button>
      ) : (
        <>
          <StatusLabel
            tone={action.status === "completed" ? "verified" : "review"}
            label={action.status}
            date={action.updated_at}
          />
          <p className={styles.draft}>{action.draft_text}</p>
          {action.status === "completed" && action.outcome_note ? (
            <p className={styles.outcome}>Outcome: {action.outcome_note}</p>
          ) : null}
          {action.status === "approved" ? (
            <label className={styles.note}>
              <span>Outcome note</span>
              <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
            </label>
          ) : null}
          <div className={styles.buttons}>
            {action.status === "draft" ? (
              <button type="button" className={styles.primary} disabled={busy} onClick={() => void update({ status: "approved" })}>
                Approve
              </button>
            ) : null}
            {action.status === "approved" ? (
              <button type="button" className={styles.primary} disabled={busy} onClick={complete}>
                Mark completed
              </button>
            ) : null}
            {action.status === "draft" || action.status === "approved" ? (
              <button type="button" className={styles.secondary} disabled={busy} onClick={() => void update({ status: "cancelled" })}>
                Cancel
              </button>
            ) : null}
          </div>
        </>
      )}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </li>
  );
}

/** Advisor follow-ups for one flag. Drafts are reviewed here and never sent anywhere. */
export default function ActionPanel({ familyId, insight }: { familyId: string; insight: InsightDTO }) {
  const actions = useRelayQuery<AdvisorActionDTO[]>(`/families/${familyId}/actions`);
  const types: ActionType[] = insight.type === "legal_review" ? ["parent_review"] : ["parent_review", "heir_intro"];
  // Match on insight_key, not just the row id: saving asset terms recomputes the flag into a new
  // insight row, and the actions drafted against the old row still belong to this flag.
  const latest = (type: ActionType) =>
    (actions.data ?? [])
      .filter((a) => (a.insight_key === insight.insight_key || a.insight_id === insight.id) && a.action_type === type)
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0];

  return (
    <section className={styles.panel} aria-label="Actions">
      <h3 className={styles.title}>Actions</h3>
      {actions.error && !actions.data ? (
        <ErrorState error={actions.error} onRetry={actions.reload} />
      ) : (
        <ul className={styles.list}>
          {types.map((type) => (
            <ActionItem
              key={type}
              familyId={familyId}
              insightId={insight.id}
              insightCreatedAt={insight.created_at}
              type={type}
              action={latest(type)}
              onChanged={actions.reload}
            />
          ))}
        </ul>
      )}
      <p className={styles.footer}>Nothing is sent. Drafts stay inside Heirloom Relay for your review.</p>
    </section>
  );
}
