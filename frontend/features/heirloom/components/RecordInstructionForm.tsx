"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import relay from "@/features/heirloom/api/client";
import { useRelayAction } from "@/features/heirloom/hooks/useRelayAction";
import type { AdvisorDecisionDTO, RecordInstructionBody, SourceRef } from "@/features/heirloom/types/contracts";
import { formatLabelDate } from "./StatusLabel";
import styles from "./RecordInstructionForm.module.css";

const NOTE_MAX = 500;

/** Today in the advisor's own calendar, as YYYY-MM-DD. */
function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

interface FieldErrors {
  date?: string;
  note?: string;
}

function noop() {}

/**
 * Where the advisor writes down what the parent said about sharing one decision. The server needs
 * the conversation's date and a note for every recorded change, and optionally which meeting it was.
 * Nothing is sent until both are valid. `activeTarget` is the state being recorded: true to share,
 * false to stop sharing.
 */
export default function RecordInstructionForm({
  familyId,
  decision,
  recipientPersonId,
  sources,
  activeTarget,
  parentName = "Robert",
  onSubmitted,
  onCancel,
}: {
  familyId: string;
  decision: AdvisorDecisionDTO;
  recipientPersonId: string;
  sources: SourceRef[];
  activeTarget: boolean;
  /** Whose instruction this is. The demo family's parent unless the caller says otherwise. */
  parentName?: string;
  onSubmitted: () => void;
  onCancel: () => void;
}) {
  const id = useId();
  const dateRef = useRef<HTMLInputElement>(null);
  const [date, setDate] = useState("");
  const [note, setNote] = useState("");
  const [sourceRef, setSourceRef] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  // The caller's `onSubmitted` runs only on success, so the hook's own refetch callback is not used.
  const action = useRelayAction(noop, "The instruction could not be recorded.");

  useEffect(() => {
    dateRef.current?.focus();
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const trimmed = note.trim();
    const found: FieldErrors = {};
    if (date === "") found.date = "Enter the date of the conversation.";
    else if (date > today()) found.date = "The conversation date can't be in the future.";
    if (trimmed === "") found.note = `Write what ${parentName} said.`;
    else if (trimmed.length > NOTE_MAX) found.note = `Keep it to ${NOTE_MAX} characters or fewer.`;
    setErrors(found);
    if (found.date || found.note) return;

    const body: RecordInstructionBody = {
      scope: "decision_excerpt",
      recipient_person_id: recipientPersonId,
      active: activeTarget,
      basis: {
        conversation_date: date,
        note: trimmed,
        ...(sourceRef === "" ? {} : { source_ref: sourceRef }),
      },
    };
    const ok = await action.run(() =>
      relay.put(`/families/${familyId}/consents/${encodeURIComponent(decision.id)}`, body),
    );
    if (ok) onSubmitted();
  }

  return (
    <form
      className={styles.form}
      aria-label={activeTarget ? "Record instruction to share" : "Record instruction to stop sharing"}
      noValidate
      onSubmit={(e) => void submit(e)}
    >
      <div className={styles.field}>
        <label htmlFor={`${id}-date`}>Conversation date</label>
        <input
          ref={dateRef}
          id={`${id}-date`}
          type="date"
          required
          max={today()}
          value={date}
          aria-invalid={errors.date ? true : undefined}
          aria-describedby={errors.date ? `${id}-date-error` : undefined}
          onChange={(e) => {
            setDate(e.target.value);
            setErrors((prev) => ({ ...prev, date: undefined }));
          }}
        />
        {errors.date ? (
          <p id={`${id}-date-error`} className={styles.error} role="alert">
            {errors.date}
          </p>
        ) : null}
      </div>
      <div className={styles.field}>
        <label htmlFor={`${id}-note`}>{`What ${parentName} said`}</label>
        <textarea
          id={`${id}-note`}
          rows={3}
          required
          maxLength={NOTE_MAX}
          value={note}
          aria-invalid={errors.note ? true : undefined}
          aria-describedby={errors.note ? `${id}-note-error ${id}-note-count` : `${id}-note-count`}
          onChange={(e) => {
            setNote(e.target.value);
            setErrors((prev) => ({ ...prev, note: undefined }));
          }}
        />
        <small id={`${id}-note-count`} className={styles.count}>
          {`${note.length}/${NOTE_MAX}`}
        </small>
        {errors.note ? (
          <p id={`${id}-note-error`} className={styles.error} role="alert">
            {errors.note}
          </p>
        ) : null}
      </div>
      <div className={styles.field}>
        <label htmlFor={`${id}-source`}>Source (optional)</label>
        <select id={`${id}-source`} value={sourceRef} onChange={(e) => setSourceRef(e.target.value)}>
          <option value="">No source</option>
          {sources.map((s) => (
            <option key={s.ref} value={s.ref}>
              {`${s.title} · ${formatLabelDate(s.document_date)}`}
            </option>
          ))}
        </select>
      </div>
      {action.error ? (
        <p className={styles.error} role="alert">
          {action.error}
        </p>
      ) : null}
      <div className={styles.buttons}>
        <button type="submit" className={styles.primary} disabled={action.busy}>
          Save recorded instruction
        </button>
        <button type="button" className={styles.secondary} disabled={action.busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
