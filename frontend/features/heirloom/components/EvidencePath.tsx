import type { EvidenceItem, EvidenceKind } from "@/features/heirloom/types/contracts";
import styles from "./EvidencePath.module.css";

export type EvidenceStepKey =
  | "instrument"
  | "interest"
  | "asset"
  | "rationale"
  | "goal"
  | "transfer"
  | "flag"
  | "action";

export interface EvidenceStep {
  key: EvidenceStepKey;
  label: string;
  /** Record to open in the evidence drawer; null for in-sheet steps or missing evidence. */
  ref: string | null;
}

const STEP_KIND: Partial<Record<EvidenceStepKey, EvidenceKind>> = {
  instrument: "estate_instrument",
  interest: "estate_intent",
  asset: "asset",
  rationale: "decision",
  goal: "goal",
  transfer: "forecast",
};

function buildEvidenceSteps(
  evidence: EvidenceItem[],
  names: { parent: string; heir: string },
  forecastRef?: string,
): EvidenceStep[] {
  const refFor = (key: EvidenceStepKey): string | null => {
    const kind = STEP_KIND[key];
    if (!kind) return null;
    const items = evidence.filter((e) => e.kind === kind);
    const preferred = kind === "forecast" ? items.find((e) => e.ref === forecastRef) : undefined;
    return (preferred ?? items[0])?.ref ?? null;
  };
  const steps: Array<[EvidenceStepKey, string]> = [
    ["instrument", "Estate instrument"],
    ["interest", "Named interest"],
    ["asset", "Asset & liquidity"],
    ["rationale", `${names.parent}'s rationale`],
    ["goal", `${names.heir}'s goal`],
    ["transfer", "Modeled transfer"],
    ["flag", "Flag"],
    ["action", "Action"],
  ];
  return steps.map(([key, label]) => ({ key, label, ref: refFor(key) }));
}

/** Breadcrumbs from the estate instrument to the advisor action; each record step opens its source. */
export default function EvidencePath({
  evidence,
  names,
  forecastRef,
  onStep,
}: {
  evidence: EvidenceItem[];
  names: { parent: string; heir: string };
  /** The forecast evidence to open for "Modeled transfer" (the scenario on screen). */
  forecastRef?: string;
  onStep: (step: EvidenceStep) => void;
}) {
  const steps = buildEvidenceSteps(evidence, names, forecastRef);
  return (
    <nav aria-label="Evidence path">
      <ol className={styles.path}>
        {steps.map((step) => {
          const inSheet = step.key === "flag" || step.key === "action";
          const missing = !inSheet && step.ref === null;
          return (
            <li key={step.key} className={styles.step}>
              <button
                type="button"
                className={styles.crumb}
                disabled={missing}
                title={missing ? "Not yet verified evidence for this flag" : undefined}
                onClick={() => onStep(step)}
              >
                {step.label}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
