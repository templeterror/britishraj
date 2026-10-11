"use client";

import { useEffect, useId, useRef, useState } from "react";
import { firstName } from "@/features/heirloom/format";
import type {
  AdvisorDecisionDTO,
  AdvisorSnapshot,
  GoalSharingLevel,
  HeirSharingView,
} from "@/features/heirloom/types/contracts";
import HeirPreview from "./HeirPreview";
import RecordInstructionForm from "./RecordInstructionForm";
import StatusLabel, { formatLabelDate } from "./StatusLabel";
import styles from "./FamilyPermissions.module.css";

const GOAL_SHARING_LABEL: Record<GoalSharingLevel, string> = {
  not_shared: "Not shared",
  summary: "Summary shared",
  detail: "Details shared",
};

const LEGAL_NOTE =
  "Recorded instructions are an illustrative record, not a legally sufficient client authorization. Production use requires written client authorization and compliance review.";

function newestFirst(a: AdvisorDecisionDTO, b: AdvisorDecisionDTO): number {
  return b.decision_date.localeCompare(a.decision_date) || a.id.localeCompare(b.id);
}

/** Who changed the sharing last, and from which conversation. Empty when nothing was recorded. */
function provenance(sharing: HeirSharingView, parentName: string): string | null {
  if (sharing.recorded_via === "advisor_recorded") {
    const by = sharing.recorded_by_display ?? "the advisor";
    return sharing.basis_date
      ? `Recorded by ${by} from a conversation on ${formatLabelDate(sharing.basis_date)}`
      : `Recorded by ${by}`;
  }
  if (sharing.recorded_via === "self" && sharing.shared) return `Shared by ${parentName}`;
  return null;
}

function Basis({ sharing }: { sharing: HeirSharingView }) {
  if (sharing.recorded_via !== "advisor_recorded" || (!sharing.basis_note && !sharing.basis_source_title)) {
    return null;
  }
  return (
    <div className={styles.basis}>
      <span className={styles.caption}>Advisor-only record</span>
      {sharing.basis_note ? <blockquote className={styles.note}>{sharing.basis_note}</blockquote> : null}
      {sharing.basis_source_title ? <p className={styles.meta}>{`Source: ${sharing.basis_source_title}`}</p> : null}
    </div>
  );
}

function DecisionRow({
  familyId,
  decision,
  sources,
  parentName,
  heirName,
  onRecorded,
}: {
  familyId: string;
  decision: AdvisorDecisionDTO;
  sources: AdvisorSnapshot["sources"];
  parentName: string;
  heirName: string;
  onRecorded: () => void;
}) {
  const titleId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef(false);
  // What the advisor chose to record (true: share, false: stop), fixed when the form opens so a
  // refetch that changes the row underneath cannot turn "share" into "stop sharing" mid-entry.
  const [target, setTarget] = useState<boolean | null>(null);
  const sharing = decision.heir_sharing;
  const verified = decision.verification_status === "verified";
  const line = sharing ? provenance(sharing, parentName) : null;

  useEffect(() => {
    if (target === null && returnFocus.current) {
      returnFocus.current = false;
      triggerRef.current?.focus();
    }
  }, [target]);

  function close() {
    returnFocus.current = true;
    setTarget(null);
  }

  return (
    <article className={styles.row} aria-labelledby={titleId}>
      <StatusLabel
        tone={verified ? "verified" : decision.verification_status === "candidate" ? "candidate" : "superseded"}
        label={decision.verification_status}
        date={decision.decision_date}
      />
      <h4 id={titleId} className={styles.title}>
        {decision.action}
      </h4>
      {!verified ? (
        <p className={styles.muted}>Verify in Decision memory first</p>
      ) : !sharing ? (
        <p className={styles.muted}>There is no family member to share with yet.</p>
      ) : (
        <>
          <p className={sharing.shared ? styles.shared : styles.notShared}>
            {sharing.shared ? `Shared with ${heirName}` : "Not shared"}
          </p>
          {line ? <p className={styles.meta}>{line}</p> : null}
          <Basis sharing={sharing} />
          {target === null ? (
            <button
              ref={triggerRef}
              type="button"
              className={styles.action}
              onClick={() => setTarget(!sharing.shared)}
            >
              {sharing.shared ? "Record instruction to stop sharing" : `Record ${parentName}'s instruction to share`}
            </button>
          ) : (
            <div className={styles.formSlot}>
              <RecordInstructionForm
                familyId={familyId}
                decision={decision}
                recipientPersonId={sharing.recipient_person_id}
                sources={sources}
                activeTarget={target}
                parentName={parentName}
                onSubmitted={() => {
                  close();
                  onRecorded();
                }}
                onCancel={close}
              />
            </div>
          )}
        </>
      )}
    </article>
  );
}

/**
 * The advisor's record of what the parent asked to share with the family member, one verified
 * decision at a time, each change citing the conversation it came from. The family member's own
 * goal sharing is shown but cannot be changed here.
 */
export default function FamilyPermissions({
  familyId,
  snapshot,
  onChanged,
  refreshKey = 0,
}: {
  familyId: string;
  snapshot: AdvisorSnapshot;
  onChanged: () => void;
  /** Changes whenever the screen refetched, so the preview does too. */
  refreshKey?: number;
}) {
  const base = useId();
  const [previewKey, setPreviewKey] = useState(0);
  const parentName = firstName(snapshot.people.find((p) => p.role === "parent")?.display_name, "Parent");
  const heirName = firstName(snapshot.people.find((p) => p.role === "adult_heir")?.display_name, "Family member");
  const decisions = [...snapshot.decisions].sort(newestFirst);

  function recorded() {
    setPreviewKey((n) => n + 1);
    onChanged();
  }

  return (
    <div className={styles.root}>
      <section className={styles.block} aria-labelledby={`${base}-intro`}>
        <h2 id={`${base}-intro`} className={styles.heading}>
          {`${parentName}'s sharing instructions`}
        </h2>
        <p className={styles.hint}>
          {`Record what ${parentName} asked you to share with ${heirName}. Each change must cite the conversation it came from.`}
        </p>

        <section className={styles.group} aria-labelledby={`${base}-preserve`}>
          <h3 id={`${base}-preserve`} className={styles.subheading}>
            {`What ${parentName} wants to preserve`}
          </h3>
          {snapshot.preserve_values.length === 0 ? (
            <p className={styles.muted}>Nothing recorded yet.</p>
          ) : (
            <ul className={styles.values}>
              {snapshot.preserve_values.map((v) => (
                <li key={v}>{v}</li>
              ))}
            </ul>
          )}
        </section>

        <section className={styles.group} aria-labelledby={`${base}-decisions`}>
          <h3 id={`${base}-decisions`} className={styles.subheading}>
            Decision explanations
          </h3>
          {decisions.length === 0 ? (
            <p className={styles.muted}>No decisions are on record yet.</p>
          ) : (
            decisions.map((d) => (
              <DecisionRow
                key={d.id}
                familyId={familyId}
                decision={d}
                sources={snapshot.sources}
                parentName={parentName}
                heirName={heirName}
                onRecorded={recorded}
              />
            ))
          )}
        </section>

        <section className={styles.group} aria-labelledby={`${base}-other`}>
          <h3 id={`${base}-other`} className={styles.subheading}>
            Other information
          </h3>
          <ul className={styles.fixed}>
            <li>Estate-plan details — Off (not shareable in this pilot)</li>
            <li>Account balances — Not available in this pilot</li>
          </ul>
        </section>
      </section>

      <section className={styles.block} aria-labelledby={`${base}-own`}>
        <h2 id={`${base}-own`} className={styles.heading}>
          {`${heirName}'s own sharing`}
        </h2>
        <p className={styles.hint}>{`${heirName} controls whether you see his goals.`}</p>
        <p className={styles.state}>{GOAL_SHARING_LABEL[snapshot.goal_sharing]}</p>
      </section>

      <HeirPreview familyId={familyId} heirName={heirName} refreshKey={refreshKey + previewKey} />

      <p className={styles.legal}>{LEGAL_NOTE}</p>
    </div>
  );
}
