"use client";

import { useId, useState } from "react";
import relay from "@/features/heirloom/api/client";
import { formatConfidence } from "@/features/heirloom/format";
import { useRelayAction } from "@/features/heirloom/hooks/useRelayAction";
import type {
  AdvisorSnapshot,
  ImportIntentBody,
  InstrumentDTO,
  InstrumentStatusBody,
  IntentDTO,
  VerifyIntentBody,
} from "@/features/heirloom/types/contracts";
import { EmptyState } from "./StateViews";
import StatusLabel, { formatLabelDate, type StatusTone } from "./StatusLabel";
import styles from "./reviews.module.css";

/** The document's standing, from the instrument and what its intents say. */
export function instrumentStanding(instrument: InstrumentDTO, intents: IntentDTO[]): { label: string; tone: StatusTone } {
  if (instrument.status === "superseded") return { label: "superseded", tone: "superseded" };
  if (instrument.status === "contested" || intents.some((i) => i.status === "contested")) {
    return { label: "unknown conflict", tone: "review" };
  }
  if (instrument.status === "verified") return { label: "verified document", tone: "verified" };
  return { label: "draft", tone: "candidate" };
}

const INTENT_TONE: Record<IntentDTO["status"], StatusTone> = {
  proposed: "candidate",
  verified: "verified",
  contested: "review",
  superseded: "superseded",
};

function humanize(kind: string): string {
  const text = kind.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function IntentFields({
  intent,
  assetLabel,
  sourceVersion,
  familyId,
  onChanged,
}: {
  intent: IntentDTO;
  assetLabel: string;
  sourceVersion: number;
  familyId: string;
  onChanged: () => void;
}) {
  const [notes, setNotes] = useState("");
  const action = useRelayAction(onChanged, "The intent could not be updated.");
  const verify = (verified: boolean) => {
    const trimmed = notes.trim();
    const body: VerifyIntentBody = { verified, notes: trimmed === "" ? null : trimmed, source_version: sourceVersion };
    void action.run(() =>
      relay.post(`/families/${familyId}/estate-intents/${encodeURIComponent(intent.id)}/verify`, body),
    );
  };
  const rejected = intent.status === "proposed" && !intent.advisor_verified && intent.verification_notes !== null;

  return (
    <div className={styles.intent}>
      <StatusLabel
        tone={INTENT_TONE[intent.status] ?? "neutral"}
        label={rejected ? "rejected" : intent.status}
        scope={intent.status === "verified" && intent.verified_by_display ? `By ${intent.verified_by_display}` : undefined}
      />
      <dl className={styles.fields}>
        <div>
          <dt>Asset</dt>
          <dd>{assetLabel}</dd>
        </div>
        <div>
          <dt>Beneficiary</dt>
          <dd>{intent.beneficiary_display_name}</dd>
        </div>
        <div>
          <dt>Allocation</dt>
          <dd>{intent.allocation}</dd>
        </div>
        <div>
          <dt>Conditions</dt>
          <dd>
            {intent.conditions.length > 0 ? (
              <ul className={styles.alternatives}>
                {intent.conditions.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            ) : (
              "None stated"
            )}
          </dd>
        </div>
        <div>
          <dt>Extraction confidence</dt>
          <dd className={styles.number}>{formatConfidence(intent.confidence)}</dd>
        </div>
      </dl>
      {intent.valid_to ? <p className={styles.meta}>Ended {formatLabelDate(intent.valid_to)}</p> : null}
      {intent.verification_notes ? <p className={styles.note}>Notes: {intent.verification_notes}</p> : null}
      {intent.status === "proposed" ? (
        <>
          <label className={styles.field}>
            <span>Verification notes</span>
            <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <div className={styles.buttons}>
            <button type="button" className={styles.primary} disabled={action.busy} onClick={() => verify(true)}>
              Verify
            </button>
            <button type="button" className={styles.secondary} disabled={action.busy} onClick={() => verify(false)}>
              Reject
            </button>
          </div>
        </>
      ) : null}
      {action.error ? (
        <p className={styles.error} role="alert">
          {action.error}
        </p>
      ) : null}
    </div>
  );
}

function InstrumentCard({
  instrument,
  snapshot,
  onChanged,
}: {
  instrument: InstrumentDTO;
  snapshot: AdvisorSnapshot;
  onChanged: () => void;
}) {
  const titleId = useId();
  const familyId = snapshot.family.id;
  const intents = snapshot.intents.filter((i) => i.instrument_ref === instrument.ref);
  const standing = instrumentStanding(instrument, intents);
  const action = useRelayAction(onChanged, "The document could not be updated.");
  const supersede = () => {
    const body: InstrumentStatusBody = { status: "superseded" };
    void action.run(() =>
      relay.post(`/families/${familyId}/instruments/${encodeURIComponent(instrument.id)}/status`, body),
    );
  };
  const assetLabel = (ref: string) => snapshot.assets.find((a) => a.ref === ref)?.label ?? ref;
  const meta = [
    humanize(instrument.kind),
    instrument.effective_date ? `Effective ${formatLabelDate(instrument.effective_date)}` : null,
    instrument.revocable ? "Revocable" : null,
    instrument.counsel_reviewed_at ? `Counsel reviewed ${formatLabelDate(instrument.counsel_reviewed_at)}` : null,
  ].filter((m): m is string => m !== null);

  return (
    <article className={`${styles.item} ${standing.label === "draft" ? styles.card : ""}`} aria-labelledby={titleId}>
      <div className={styles.header}>
        <StatusLabel tone={standing.tone} label={standing.label} />
        {instrument.status !== "superseded" ? (
          <button type="button" className={styles.secondary} disabled={action.busy} onClick={supersede}>
            Mark superseded
          </button>
        ) : null}
      </div>
      <h3 id={titleId} className={styles.title}>
        {instrument.title}
      </h3>
      <p className={styles.meta}>{meta.join(" · ")}</p>
      {action.error ? (
        <p className={styles.error} role="alert">
          {action.error}
        </p>
      ) : null}
      <div className={styles.columns}>
        <div className={styles.column}>
          <span className={styles.caption}>Document excerpt{instrument.source_title ? ` · ${instrument.source_title}` : ""}</span>
          {instrument.source_excerpt ? (
            <blockquote className={styles.quote}>{instrument.source_excerpt}</blockquote>
          ) : (
            <p className={styles.missing}>No excerpt on file</p>
          )}
        </div>
        <div className={styles.intents}>
          <span className={styles.caption}>Extracted intent</span>
          {intents.length === 0 ? (
            <p className={styles.missing}>No intents extracted</p>
          ) : (
            intents.map((intent) => (
              <IntentFields
                key={intent.id}
                intent={intent}
                assetLabel={assetLabel(intent.asset_ref)}
                sourceVersion={instrument.source_version ?? 0}
                familyId={familyId}
                onChanged={onChanged}
              />
            ))
          )}
        </div>
      </div>
    </article>
  );
}

/** Estate intents per document: the source text beside what was extracted from it, for the advisor to verify. */
export default function IntentReview({ snapshot, onChanged }: { snapshot: AdvisorSnapshot; onChanged: () => void }) {
  const familyId = snapshot.family.id;
  const importer = useRelayAction(onChanged, "The amendment could not be imported.");
  const importAmendment = () => {
    const body: ImportIntentBody = { fixture_ref: "conflicting_amendment" };
    void importer.run(() => relay.post(`/families/${familyId}/estate-intents/import`, body));
  };
  const instruments = [...snapshot.instruments].sort(
    (a, b) => (b.effective_date ?? "").localeCompare(a.effective_date ?? "") || a.id.localeCompare(b.id),
  );

  return (
    <section className={styles.review} aria-label="Estate intents">
      <div className={styles.toolbar}>
        <button type="button" className={styles.secondary} disabled={importer.busy} onClick={importAmendment}>
          Import synthetic amendment
        </button>
        <p className={styles.hint}>Adds a synthetic later amendment as a draft. Nothing changes until you verify it.</p>
      </div>
      {importer.error ? (
        <p className={styles.error} role="alert">
          {importer.error}
        </p>
      ) : null}
      {instruments.length === 0 ? (
        <EmptyState title="No estate documents on file" />
      ) : (
        <div className={styles.list}>
          {instruments.map((instrument) => (
            <InstrumentCard key={instrument.id} instrument={instrument} snapshot={snapshot} onChanged={onChanged} />
          ))}
        </div>
      )}
    </section>
  );
}
