"use client";

import { useId, useState, type FormEvent } from "react";
import relay, { RelayApiError } from "@/features/heirloom/api/client";
import type { GoalInput, GoalKind, GoalPatch, HeirGoalView } from "@/features/heirloom/types/contracts";
import styles from "./GoalCheckIn.module.css";

const KIND_LABEL: Record<GoalKind, string> = {
  business: "Business",
  home: "Home",
  education: "Education",
  philanthropy: "Philanthropy",
  wealth_preservation: "Wealth preservation",
  other: "Other",
};
const KINDS = Object.keys(KIND_LABEL) as GoalKind[];

/** Example goals that fill the form (nothing is saved until the person saves). */
const EXAMPLES: Array<{ label: string; goal: GoalInput }> = [
  {
    label: "Start a company",
    goal: {
      goal_kind: "business",
      description_private: "Build a software company; I expect to need roughly $500,000 in startup liquidity.",
      amount_target: 500000,
      target_year: 2038,
      horizon_min_years: 8,
      horizon_max_years: 12,
      milestone: "Incorporate and raise a pre-seed round",
    },
  },
  {
    label: "Endow a foundation",
    goal: {
      goal_kind: "philanthropy",
      description_private: "Endow a small family foundation",
      amount_target: 250000,
      target_year: 2051,
      horizon_min_years: 20,
      horizon_max_years: 25,
      milestone: null,
    },
  },
];

interface FormState {
  kind: GoalKind;
  narrative: string;
  amount: string;
  year: string;
  milestone: string;
  /** The timeframe in years that goes with `horizonYear`; it is not a field the person edits. */
  horizon: [number | null, number | null];
  horizonYear: string;
}

const EMPTY: FormState = {
  kind: "business",
  narrative: "",
  amount: "",
  year: "",
  milestone: "",
  horizon: [null, null],
  horizonYear: "",
};

function fromGoal(g: Omit<GoalInput, "goal_funding_source"> | null): FormState {
  if (!g) return EMPTY;
  const year = g.target_year === null ? "" : String(g.target_year);
  return {
    kind: g.goal_kind,
    narrative: g.description_private,
    amount: g.amount_target === null ? "" : String(g.amount_target),
    year,
    milestone: g.milestone ?? "",
    horizon: [g.horizon_min_years, g.horizon_max_years],
    horizonYear: year,
  };
}

function wholeNumber(text: string): number | null | "invalid" {
  if (text.trim() === "") return null;
  const n = Number(text);
  return Number.isInteger(n) ? n : "invalid";
}

function toInput(f: FormState): { input: GoalInput } | { error: string } {
  const narrative = f.narrative.trim();
  if (narrative === "") return { error: "Describe what you're working toward." };
  const amount = wholeNumber(f.amount);
  if (amount === "invalid" || (amount !== null && (amount <= 0 || amount > 1_000_000_000))) {
    return { error: "Amount must be a whole number above 0, or leave it blank." };
  }
  const year = wholeNumber(f.year);
  if (year === "invalid" || (year !== null && (year < 1000 || year > 9999))) {
    return { error: "Target year must be a four-digit year, or leave it blank." };
  }
  // The saved timeframe belongs to the year it was set with; a different year makes it stale.
  const keepHorizon = f.year === f.horizonYear;
  return {
    input: {
      goal_kind: f.kind,
      description_private: narrative,
      amount_target: amount,
      target_year: year,
      horizon_min_years: keepHorizon ? f.horizon[0] : null,
      horizon_max_years: keepHorizon ? f.horizon[1] : null,
      milestone: f.milestone.trim() === "" ? null : f.milestone.trim(),
    },
  };
}

type Status =
  | { kind: "idle" | "saving" | "saved" | "conflict" }
  | { kind: "error"; message: string };

/**
 * The family member's goal. It is saved against the version it was loaded from, so a save made after
 * the goal changed in another window comes back as a conflict instead of overwriting that change.
 * `onSaved` refetches the goal; it also runs when the person chooses Reload after a conflict.
 */
export default function GoalCheckIn({
  familyId,
  goal,
  onSaved,
}: {
  familyId: string;
  /** The saved goal, or null before the first one. */
  goal: HeirGoalView | null;
  onSaved: () => void;
}) {
  const headingId = useId();
  const [base, setBase] = useState(() => ({ version: goal?.version ?? null, form: fromGoal(goal) }));
  const [form, setForm] = useState<FormState>(base.form);
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  // A newer goal arriving (a refetch after a change elsewhere) replaces the form only if the person
  // has not started editing; otherwise their edits stay and the save reports the conflict.
  const dirty = JSON.stringify(form) !== JSON.stringify(base.form);
  if (goal && (base.version === null || goal.version > base.version) && !dirty) {
    const next = { version: goal.version, form: fromGoal(goal) };
    setBase(next);
    setForm(next.form);
  }

  function change(patch: Partial<FormState>) {
    setForm({ ...form, ...patch });
    if (status.kind === "saved" || status.kind === "error") setStatus({ kind: "idle" });
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const checked = toInput(form);
    if ("error" in checked) {
      setStatus({ kind: "error", message: checked.error });
      return;
    }
    setStatus({ kind: "saving" });
    try {
      const saved =
        goal && base.version !== null
          ? await relay.patch<HeirGoalView>(`/families/${familyId}/heir-goals/${goal.goal_id}`, {
              ...checked.input,
              version: base.version,
            } satisfies GoalPatch)
          : await relay.post<HeirGoalView>(`/families/${familyId}/heir-goals`, checked.input);
      const next = { version: saved.data.version, form: fromGoal(saved.data) };
      setBase(next);
      setForm(next.form);
      setStatus({ kind: "saved" });
      onSaved();
    } catch (err) {
      if (err instanceof RelayApiError && err.status === 409 && err.code === "version_conflict") {
        setStatus({ kind: "conflict" });
      } else {
        const message = err instanceof RelayApiError ? err.message : "Your goal could not be saved.";
        setStatus({ kind: "error", message });
      }
    }
  }

  function reload() {
    setForm(base.form);
    setStatus({ kind: "idle" });
    onSaved();
  }

  return (
    <form className={styles.form} onSubmit={onSubmit} noValidate aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.heading}>
        Your goal
      </h2>
      <p className={styles.private}>Your information is private unless you choose to share it.</p>

      <div className={styles.examples} role="group" aria-label="Start from an example">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            type="button"
            className={styles.example}
            onClick={() => change(fromGoal(ex.goal))}
          >
            {ex.label}
          </button>
        ))}
      </div>

      <label className={styles.field}>
        <span>Kind of goal</span>
        <select
          className={styles.control}
          value={form.kind}
          onChange={(e) => change({ kind: e.target.value as GoalKind })}
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {KIND_LABEL[k]}
            </option>
          ))}
        </select>
      </label>

      <label className={styles.field}>
        <span>What are you working toward?</span>
        <textarea
          className={styles.control}
          rows={3}
          maxLength={2000}
          value={form.narrative}
          onChange={(e) => change({ narrative: e.target.value })}
        />
      </label>

      <div className={styles.row}>
        <label className={styles.field}>
          <span>Rough amount you expect to need (optional)</span>
          <input
            type="number"
            className={styles.control}
            min={1}
            step={1}
            value={form.amount}
            onChange={(e) => change({ amount: e.target.value })}
          />
        </label>
        <label className={styles.field}>
          <span>Target year (optional)</span>
          <input
            type="number"
            className={styles.control}
            step={1}
            value={form.year}
            onChange={(e) => change({ year: e.target.value })}
          />
        </label>
      </div>

      <label className={styles.field}>
        <span>Next milestone (optional)</span>
        <input
          type="text"
          className={styles.control}
          maxLength={500}
          value={form.milestone}
          onChange={(e) => change({ milestone: e.target.value })}
        />
      </label>

      {status.kind === "conflict" ? (
        <div className={styles.conflict} role="alert">
          <span>This goal was updated in another window.</span>
          <button type="button" className={styles.reload} onClick={reload}>
            Reload
          </button>
        </div>
      ) : null}
      {status.kind === "error" ? (
        <p className={styles.error} role="alert">
          {status.message}
        </p>
      ) : null}
      {status.kind === "saved" ? <p className={styles.saved}>Saved.</p> : null}

      <button type="submit" className={styles.save} disabled={status.kind === "saving"}>
        {status.kind === "saving" ? "Saving…" : "Save goal"}
      </button>
    </form>
  );
}
