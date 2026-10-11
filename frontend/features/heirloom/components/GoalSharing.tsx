"use client";

import { useId } from "react";
import relay from "@/features/heirloom/api/client";
import { firstName } from "@/features/heirloom/format";
import { useRelayAction } from "@/features/heirloom/hooks/useRelayAction";
import type { ConsentPutBody, HeirSnapshot } from "@/features/heirloom/types/contracts";
import styles from "./GoalSharing.module.css";

type GoalScope = Extract<ConsentPutBody["scope"], "goal_summary" | "goal_detail">;

/**
 * The two ways the family member can share their goal with the advisor. Both start off, and each is
 * its own choice; the server keeps them consistent (details on also turns the summary on, summary
 * off also turns the details off) and the switches show what it says after the refresh.
 */
export default function GoalSharing({
  familyId,
  goalId,
  advisor,
  sharing,
  onChanged,
}: {
  familyId: string;
  /** The goal being shared; none until the first goal is saved. */
  goalId: string | undefined;
  advisor: HeirSnapshot["advisor"];
  sharing: HeirSnapshot["sharing"];
  onChanged: () => void;
}) {
  const headingId = useId();
  const action = useRelayAction(onChanged, "Your sharing choice could not be saved.");
  const name = firstName(advisor.display_name, "your advisor");
  const disabled = !goalId || action.busy;

  function change(scope: GoalScope, active: boolean) {
    if (!goalId) return;
    const body: Omit<ConsentPutBody, "recipient_person_id"> & Partial<ConsentPutBody> = {
      scope,
      recipient_person_id: advisor.person_id,
      active,
    };
    void action.run(() => relay.put(`/families/${familyId}/consents/${goalId}`, body));
  }

  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.heading}>
        What {name} can see
      </h2>
      <p className={styles.hint}>
        {name} sees nothing about your goal unless you turn a switch on. You can turn either one off at any time.
        Turning the summary off also turns the details off.
      </p>
      <ul className={styles.list}>
        <li>
          <label className={styles.row}>
            <input
              type="checkbox"
              role="switch"
              className={styles.switch}
              checked={sharing.advisor_summary}
              disabled={disabled}
              onChange={(e) => change("goal_summary", e.target.checked)}
            />
            <span>{`Share a goal summary with ${name} (type, rough amount, timeframe)`}</span>
          </label>
        </li>
        <li>
          <label className={styles.row}>
            <input
              type="checkbox"
              role="switch"
              className={styles.switch}
              checked={sharing.advisor_detail}
              disabled={disabled}
              onChange={(e) => change("goal_detail", e.target.checked)}
            />
            <span>Also share full details (exact amount, year, milestone, your notes)</span>
          </label>
        </li>
      </ul>
      {!goalId ? <p className={styles.hint}>Save a goal first, then choose what to share.</p> : null}
      {action.error ? (
        <p className={styles.error} role="alert">
          {action.error}
        </p>
      ) : null}
    </section>
  );
}
