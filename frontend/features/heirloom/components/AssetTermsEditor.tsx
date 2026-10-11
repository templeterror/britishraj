"use client";

import { useState, type FormEvent } from "react";
import relay, { RelayApiError } from "@/features/heirloom/api/client";
import type { AssetDTO, AssetTermsPatch } from "@/features/heirloom/types/contracts";
import styles from "./AssetTermsEditor.module.css";

type Validated = { patch: AssetTermsPatch } | { error: string };

function validate(delay: string, fraction: string, documented: boolean): Validated {
  const patch: AssetTermsPatch = { partner_consent_process_documented: documented };
  if (delay.trim() !== "") {
    const d = Number(delay);
    if (!Number.isFinite(d) || d < 0 || d > 10) return { error: "Sale delay must be between 0 and 10 years." };
    patch.sale_delay_years = d;
  }
  if (fraction.trim() === "") {
    patch.liquidatable_fraction = null;
  } else {
    const f = Number(fraction);
    if (!Number.isFinite(f) || f < 0 || f > 1) {
      return { error: "Liquidatable fraction must be between 0 and 1, or blank if unknown." };
    }
    patch.liquidatable_fraction = f;
  }
  return { patch };
}

/** Advisor edits to the access terms the forecast depends on; saving triggers a server-side recompute. */
export default function AssetTermsEditor({
  familyId,
  asset,
  onSaved,
}: {
  familyId: string;
  asset: AssetDTO;
  onSaved: () => void;
}) {
  const { terms } = asset;
  const [delay, setDelay] = useState(terms.sale_delay_years === null ? "" : String(terms.sale_delay_years));
  const [fraction, setFraction] = useState(
    terms.liquidatable_fraction === null ? "" : String(terms.liquidatable_fraction),
  );
  const [documented, setDocumented] = useState(terms.partner_consent_process_documented);
  const [status, setStatus] = useState<{ kind: "idle" | "saving" | "saved" } | { kind: "error"; message: string }>({
    kind: "idle",
  });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const checked = validate(delay, fraction, documented);
    if ("error" in checked) {
      setStatus({ kind: "error", message: checked.error });
      return;
    }
    setStatus({ kind: "saving" });
    try {
      await relay.patch(`/families/${familyId}/assets/${asset.id}/terms`, checked.patch);
      setStatus({ kind: "saved" });
      onSaved();
    } catch (err) {
      setStatus({ kind: "error", message: err instanceof RelayApiError ? err.message : "Could not save terms." });
    }
  }

  return (
    <form className={styles.form} onSubmit={onSubmit} noValidate>
      <h4 className={styles.heading}>Access terms</h4>
      <label className={styles.field}>
        <span>Sale delay (years)</span>
        <input type="number" min={0} max={10} step={0.5} value={delay} onChange={(e) => setDelay(e.target.value)} />
      </label>
      <label className={styles.field}>
        <span>Liquidatable fraction (0–1, blank if unknown)</span>
        <input
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={fraction}
          onChange={(e) => setFraction(e.target.value)}
        />
      </label>
      <label className={styles.check}>
        <input type="checkbox" checked={documented} onChange={(e) => setDocumented(e.target.checked)} />
        <span>Partner-consent process documented</span>
      </label>
      {status.kind === "error" ? (
        <p className={styles.error} role="alert">
          {status.message}
        </p>
      ) : null}
      {status.kind === "saved" ? <p className={styles.saved}>Saved. Flags recompute from the new terms.</p> : null}
      <button type="submit" className={styles.save} disabled={status.kind === "saving"}>
        {status.kind === "saving" ? "Saving…" : "Save terms"}
      </button>
    </form>
  );
}
