"use client";

import { useId, useState, type FormEvent } from "react";
import relay, { RelayApiError } from "@/features/heirloom/api/client";
import type { MemoryAnswer } from "@/features/heirloom/types/contracts";
import { Citation } from "./ApprovedMemory";
import { formatLabelDate } from "./StatusLabel";
import styles from "./MemoryAsk.module.css";

const SUGGESTED_QUESTION = "Why was family control important?";
const NO_RECORD = "No approved record answers that.";

type Result = { kind: "answer"; answer: MemoryAnswer } | { kind: "error"; message: string };

function failure(err: unknown): string {
  if (err instanceof RelayApiError) {
    return err.code === "network_error" ? "Can't reach Heirloom Relay. Try again." : err.message;
  }
  return "The question could not be asked.";
}

/**
 * Ask a question of the explanations shared with this family member. The server answers from those
 * records only, or refuses with a reason, which is shown exactly as given.
 */
export default function MemoryAsk({ familyId }: { familyId: string }) {
  const headingId = useId();
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  async function ask(text: string) {
    const q = text.trim();
    if (q === "" || busy) return;
    setBusy(true);
    try {
      const { data } = await relay.post<MemoryAnswer>(`/families/${familyId}/memory/ask`, { question: q });
      setResult({ kind: "answer", answer: data });
    } catch (err) {
      setResult({ kind: "error", message: failure(err) });
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  function askSuggested() {
    setQuestion(SUGGESTED_QUESTION);
    void ask(SUGGESTED_QUESTION);
  }

  const answer = result?.kind === "answer" ? result.answer : null;
  const matches = answer?.status === "answered" ? answer.matches : [];

  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.heading}>
        Ask about a shared decision
      </h2>
      <p className={styles.hint}>Answers come only from the verified explanations that have been shared with you.</p>
      <form className={styles.form} onSubmit={onSubmit}>
        <label className={styles.field}>
          <span>Your question</span>
          <input
            type="text"
            value={question}
            maxLength={500}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </label>
        <button type="submit" className={styles.ask} disabled={busy || question.trim() === ""}>
          {busy ? "Asking…" : "Ask"}
        </button>
      </form>
      <button type="button" className={styles.suggestion} disabled={busy} onClick={askSuggested}>
        {SUGGESTED_QUESTION}
      </button>

      <div className={styles.result} aria-live="polite">
        {result?.kind === "error" ? (
          <p className={styles.error} role="alert">
            {result.message}
          </p>
        ) : answer && matches.length === 0 ? (
          <p className={styles.refusal}>{answer.reason ?? NO_RECORD}</p>
        ) : (
          matches.map((m) => (
            <article key={m.decision_id} className={styles.match} aria-label={m.title}>
              <time className={styles.date} dateTime={m.date}>
                {formatLabelDate(m.date)}
              </time>
              <h3 className={styles.title}>{m.title}</h3>
              <Citation
                quote={m.excerpt}
                sourceTitle={m.source_title}
                locator={m.locator}
                verifiedBy={m.verified_by_display}
              />
            </article>
          ))
        )}
      </div>
    </section>
  );
}
