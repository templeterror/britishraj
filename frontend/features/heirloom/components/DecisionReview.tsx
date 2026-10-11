"use client";

import { useId, useState } from "react";
import relay from "@/features/heirloom/api/client";
import { formatConfidence } from "@/features/heirloom/format";
import { useRelayAction } from "@/features/heirloom/hooks/useRelayAction";
import type { AdvisorSnapshot, DecisionDTO, VerifyDecisionBody } from "@/features/heirloom/types/contracts";
import { describeLocator } from "./EvidenceDrawer";
import { EmptyState } from "./StateViews";
import StatusLabel, { formatLabelDate } from "./StatusLabel";
import styles from "./reviews.module.css";

const NOT_DOCUMENTED = "Rationale not documented";

function newestFirst(a: DecisionDTO, b: DecisionDTO): number {
  return b.decision_date.localeCompare(a.decision_date) || a.id.localeCompare(b.id);
}

function Source({ decision }: { decision: DecisionDTO }) {
  const where = describeLocator(decision.locator);
  const quote = decision.locator?.quoted_span;
  if (!decision.source_title && !quote) return null;
  return (
    <>
      {decision.source_title ? (
        <p className={styles.source}>
          {decision.source_title}
          {where ? ` · ${where}` : ""}
        </p>
      ) : null}
      {quote ? <blockquote className={styles.quote}>{quote}</blockquote> : null}
    </>
  );
}

function CandidateCard({
  familyId,
  decision,
  onChanged,
}: {
  familyId: string;
  decision: DecisionDTO;
  onChanged: () => void;
}) {
  const titleId = useId();
  const [rationale, setRationale] = useState(decision.rationale ?? "");
  const [note, setNote] = useState("");
  const action = useRelayAction(onChanged, "The decision could not be updated.");
  const base = `/families/${familyId}/decisions/${encodeURIComponent(decision.id)}`;

  const verify = (approved: boolean) => {
    const trimmedNote = note.trim();
    if (!approved && trimmedNote === "") {
      action.fail("Add a note explaining why this decision is rejected.");
      return;
    }
    const edited = rationale.trim();
    const body: VerifyDecisionBody = {
      approved,
      edited_rationale: approved && edited !== "" && edited !== (decision.rationale ?? "") ? edited : null,
      note: trimmedNote === "" ? null : trimmedNote,
    };
    void action.run(() => relay.post(`${base}/verify`, body));
  };

  const annotate = async () => {
    const trimmedNote = note.trim();
    if (trimmedNote === "") {
      action.fail("Add a note to annotate this decision.");
      return;
    }
    if (await action.run(() => relay.post(`${base}/annotate`, { note: trimmedNote }))) setNote("");
  };

  return (
    <article className={styles.card} aria-labelledby={titleId}>
      <StatusLabel tone="candidate" label="candidate" date={decision.decision_date} scope="Advisor review" />
      <h3 id={titleId} className={styles.title}>
        {decision.action}
      </h3>
      <div className={styles.columns}>
        <div className={styles.column}>
          <span className={styles.caption}>Transcript excerpt</span>
          <Source decision={decision} />
        </div>
        <dl className={styles.fields}>
          <div>
            <dt>Action</dt>
            <dd>{decision.action}</dd>
          </div>
          <div>
            <dt>Rationale</dt>
            <dd className={decision.rationale === null ? styles.missing : undefined}>
              {decision.rationale ?? NOT_DOCUMENTED}
            </dd>
          </div>
          <div>
            <dt>Alternatives considered</dt>
            <dd>
              {decision.alternatives.length > 0 ? (
                <ul className={styles.alternatives}>
                  {decision.alternatives.map((alt) => (
                    <li key={alt}>{alt}</li>
                  ))}
                </ul>
              ) : (
                "None recorded"
              )}
            </dd>
          </div>
          <div>
            <dt>Extraction confidence</dt>
            <dd className={styles.number}>{formatConfidence(decision.confidence)}</dd>
          </div>
        </dl>
      </div>
      {decision.advisor_note ? <p className={styles.note}>Advisor note: {decision.advisor_note}</p> : null}
      <label className={styles.field}>
        <span>Rationale (edit before verifying)</span>
        <textarea
          rows={2}
          value={rationale}
          placeholder="Only if the source states one"
          onChange={(e) => setRationale(e.target.value)}
        />
      </label>
      <div className={styles.field}>
        <label htmlFor={`${titleId}-note`}>Note</label>
        <textarea
          id={`${titleId}-note`}
          rows={2}
          value={note}
          aria-describedby={`${titleId}-note-hint`}
          onChange={(e) => setNote(e.target.value)}
        />
        <small id={`${titleId}-note-hint`}>Required to reject or annotate.</small>
      </div>
      <div className={styles.buttons}>
        <button type="button" className={styles.primary} disabled={action.busy} onClick={() => verify(true)}>
          Verify
        </button>
        <button type="button" className={styles.secondary} disabled={action.busy} onClick={() => verify(false)}>
          Reject
        </button>
        <button type="button" className={styles.secondary} disabled={action.busy} onClick={() => void annotate()}>
          Annotate
        </button>
      </div>
      {action.error ? (
        <p className={styles.error} role="alert">
          {action.error}
        </p>
      ) : null}
    </article>
  );
}

function RecordedDecision({ decision }: { decision: DecisionDTO }) {
  const titleId = useId();
  const verified = decision.verification_status === "verified";
  const scope = verified && decision.verified_by_display ? `By ${decision.verified_by_display}` : undefined;
  return (
    <article className={styles.item} aria-labelledby={titleId}>
      <StatusLabel
        tone={verified ? "verified" : "superseded"}
        label={decision.verification_status}
        date={decision.decision_date}
        scope={scope}
      />
      <h3 id={titleId} className={styles.title}>
        {decision.action}
      </h3>
      <p className={decision.rationale === null ? styles.missing : styles.rationale}>
        {decision.rationale ?? NOT_DOCUMENTED}
        {decision.rationale_edited ? <span className={styles.edited}> · Rationale edited by advisor</span> : null}
      </p>
      {decision.valid_to ? (
        <p className={styles.meta}>No longer current from {formatLabelDate(decision.valid_to)}</p>
      ) : null}
      {decision.source_title ? (
        <p className={styles.meta}>
          {decision.source_title}
          {describeLocator(decision.locator) ? ` · ${describeLocator(decision.locator)}` : ""}
        </p>
      ) : null}
      {decision.advisor_note ? <p className={styles.note}>Advisor note: {decision.advisor_note}</p> : null}
    </article>
  );
}

/** Decision memory: extracted candidates to verify first, then the verified record with dates. */
export default function DecisionReview({ snapshot, onChanged }: { snapshot: AdvisorSnapshot; onChanged: () => void }) {
  const familyId = snapshot.family.id;
  const by = (status: DecisionDTO["verification_status"]) =>
    snapshot.decisions.filter((d) => d.verification_status === status).sort(newestFirst);
  const candidates = by("candidate");
  const verified = by("verified");
  const rejected = by("rejected");

  return (
    <section className={styles.review} aria-label="Decision memory">
      <h2 className={styles.heading}>Candidates to review</h2>
      {candidates.length === 0 ? (
        <EmptyState title="No candidates to review" body="Extracted decisions appear here before they join the record." />
      ) : (
        candidates.map((d) => <CandidateCard key={d.id} familyId={familyId} decision={d} onChanged={onChanged} />)
      )}
      <h2 className={styles.heading}>Verified decisions</h2>
      {verified.length === 0 ? (
        <EmptyState title="No verified decisions yet" />
      ) : (
        <div className={styles.list}>
          {verified.map((d) => (
            <RecordedDecision key={d.id} decision={d} />
          ))}
        </div>
      )}
      {rejected.length > 0 ? (
        <>
          <h2 className={styles.heading}>Rejected</h2>
          <div className={styles.list}>
            {rejected.map((d) => (
              <RecordedDecision key={d.id} decision={d} />
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
