"use client";

import { useEffect, useId, useRef, useState } from "react";
import { PRESET_LABEL, PRESET_ORDER, firstName, formatProbability } from "@/features/heirloom/format";
import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import type {
  AdvisorSnapshot,
  InsightDTO,
  ScenarioResultDTO,
  ScenarioRow,
  StressPreset,
} from "@/features/heirloom/types/contracts";
import AccessibleCashChart from "./AccessibleCashChart";
import ActionPanel from "./ActionPanel";
import EvidenceDrawer from "./EvidenceDrawer";
import EvidencePath, { type EvidenceStep } from "./EvidencePath";
import ExplainCalculation from "./ExplainCalculation";
import { EmptyState, ErrorState, LoadingState } from "./StateViews";
import StatusLabel from "./StatusLabel";
import ValueFanChart from "./ValueFanChart";
import styles from "./FlagSheet.module.css";

interface Selection {
  year: number;
  preset: StressPreset;
}

/** Start on the scenario the headline quotes; otherwise the earliest base case. */
function initialSelection(insight: InsightDTO): Selection | null {
  const rows = insight.scenario_rows;
  const headline =
    insight.headline_probability === null ? undefined : rows.find((r) => r.p === insight.headline_probability);
  const pick =
    headline ??
    [...rows].sort((a, b) => a.transfer_year - b.transfer_year).find((r) => r.preset === "base") ??
    rows[0];
  return pick ? { year: pick.transfer_year, preset: pick.preset } : null;
}

export default function FlagSheet({
  familyId,
  snapshot,
  insight,
  onClose,
  onChanged,
}: {
  familyId: string;
  snapshot: AdvisorSnapshot;
  insight: InsightDTO;
  onClose: () => void;
  /** Something the advisor changed may alter flags (e.g. asset terms): refetch. */
  onChanged: () => void;
}) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const actionRef = useRef<HTMLDivElement>(null);
  const flagRef = useRef<HTMLDivElement>(null);
  const [selection, setSelection] = useState<Selection | null>(() => initialSelection(insight));
  const [drawerRef, setDrawerRef] = useState<string | null>(null);

  const rows = insight.scenario_rows;
  const years = [...new Set(rows.map((r) => r.transfer_year))].sort((a, b) => a - b);
  const presets = PRESET_ORDER.filter((p) => rows.some((r) => r.preset === p));
  const rowFor = (year: number, preset: StressPreset): ScenarioRow | undefined =>
    rows.find((r) => r.transfer_year === year && r.preset === preset);
  const row = selection ? rowFor(selection.year, selection.preset) : undefined;

  const forecast = useRelayQuery<ScenarioResultDTO>(
    row ? `/families/${familyId}/forecasts/${encodeURIComponent(row.scenario_id)}` : null,
  );
  // Hold the last chart while the next scenario loads, instead of flashing a skeleton.
  const [shown, setShown] = useState<ScenarioResultDTO | null>(null);
  if (forecast.data && forecast.data !== shown) setShown(forecast.data);
  const result = forecast.data ?? shown;

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      if (drawerRef) setDrawerRef(null);
      else onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerRef, onClose]);

  function onStep(step: EvidenceStep) {
    if (step.key === "flag") flagRef.current?.scrollIntoView?.({ behavior: "smooth" });
    else if (step.key === "action") actionRef.current?.scrollIntoView?.({ behavior: "smooth" });
    else if (step.ref) setDrawerRef(step.ref);
  }

  const parent = snapshot.people.find((p) => p.role === "parent");
  const heir = snapshot.people.find((p) => p.role === "adult_heir");
  const names = { parent: firstName(parent?.display_name, "Parent"), heir: firstName(heir?.display_name, "Heir") };

  return (
    <div className={styles.layer}>
      <div className={styles.backdrop} onClick={onClose} aria-hidden="true" />
      <aside className={styles.sheet} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className={styles.header}>
          <StatusLabel tone="review" label="Review required" scope="Illustrative" />
          <button ref={closeRef} type="button" className={styles.close} onClick={onClose}>
            Close
          </button>
        </header>
        <div className={styles.scroll}>
          <div ref={flagRef} className={styles.flag}>
            <h2 id={titleId} className={styles.title}>
              {insight.title}
            </h2>
            <div className={styles.headline}>
              <span className={styles.probability}>{formatProbability(insight.headline_probability)}</span>
              <span className={styles.condition}>{insight.headline_condition}</span>
            </div>
            <p className={styles.summary}>{insight.summary}</p>
            {insight.known.length > 0 ? (
              <ul className={styles.facts} aria-label="What is known">
                {insight.known.map((k) => (
                  <li key={k}>{k}</li>
                ))}
              </ul>
            ) : null}
          </div>

          <EvidencePath evidence={insight.evidence} names={names} forecastRef={row?.scenario_id} onStep={onStep} />

          {rows.length > 0 && selection ? (
            <section className={styles.model} aria-label="Modeled transfer">
              <div className={styles.toggles}>
                <div role="group" aria-label="Hypothetical transfer year" className={styles.group}>
                  {years.map((y) => (
                    <button
                      key={y}
                      type="button"
                      className={styles.toggle}
                      aria-pressed={selection.year === y}
                      onClick={() => setSelection({ ...selection, year: y })}
                    >
                      {`Year ${y}`}
                    </button>
                  ))}
                </div>
                <div role="group" aria-label="Stress preset" className={styles.group}>
                  {presets.map((p) => (
                    <button
                      key={p}
                      type="button"
                      className={styles.toggle}
                      aria-pressed={selection.preset === p}
                      disabled={!rowFor(selection.year, p)}
                      onClick={() => setSelection({ ...selection, preset: p })}
                    >
                      {PRESET_LABEL[p]}
                    </button>
                  ))}
                </div>
              </div>
              <p className={styles.scenario}>
                Accessible cash covers the goal in <strong>{formatProbability(row?.p ?? null)}</strong>{" "}
                of paths if transfer were to occur in year {selection.year} · {PRESET_LABEL[selection.preset]} ·
                illustrative
              </p>
              {!row ? (
                <EmptyState title="Not modeled" body="This transfer year and preset are not modeled for this flag." />
              ) : forecast.error ? (
                <ErrorState error={forecast.error} onRetry={forecast.reload} />
              ) : !result ? (
                <LoadingState label="Loading scenario" />
              ) : (
                <div className={`${styles.charts} ${forecast.loading ? styles.stale : ""}`}>
                  <ValueFanChart
                    result={result}
                    transferYear={result.settings.transfer_year}
                    goalYear={result.settings.goal_year}
                  />
                  <AccessibleCashChart
                    result={result}
                    goalYear={result.settings.goal_year}
                    goalNominal={result.goal_nominal}
                  />
                  <ExplainCalculation result={result} />
                </div>
              )}
            </section>
          ) : null}

          <div ref={actionRef}>
            <ActionPanel familyId={familyId} insight={insight} />
          </div>
        </div>
        {drawerRef ? (
          <EvidenceDrawer
            key={drawerRef}
            familyId={familyId}
            recordRef={drawerRef}
            assets={snapshot.assets}
            onClose={() => setDrawerRef(null)}
            onChanged={onChanged}
          />
        ) : null}
      </aside>
    </div>
  );
}
