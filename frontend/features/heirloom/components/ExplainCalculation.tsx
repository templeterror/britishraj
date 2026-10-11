import type { ScenarioResultDTO } from "@/features/heirloom/types/contracts";
import styles from "./ExplainCalculation.module.css";

function humanize(key: string): string {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function show(value: unknown): string {
  if (value === null || value === undefined) return "Unknown";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString("en-US") : String(value);
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

/** Reproducibility record for one modeled scenario: run settings, assumptions and limitations. */
export default function ExplainCalculation({ result }: { result: ScenarioResultDTO }) {
  return (
    <details className={styles.explain}>
      <summary>Explain the calculation</summary>
      <dl className={styles.run}>
        <div>
          <dt>Paths</dt>
          <dd>{show(result.settings.paths)}</dd>
        </div>
        <div>
          <dt>Seed</dt>
          <dd>{result.seed}</dd>
        </div>
        <div>
          <dt>Model version</dt>
          <dd>{result.model_version}</dd>
        </div>
        <div>
          <dt>Input hash</dt>
          <dd className={styles.hash}>{result.input_hash}</dd>
        </div>
      </dl>
      <table className={styles.assumptions}>
        <caption>Assumptions</caption>
        <tbody>
          {Object.entries(result.settings).map(([key, value]) => (
            <tr key={key}>
              <th scope="row">{humanize(key)}</th>
              <td>{show(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4 className={styles.heading}>Limitations</h4>
      <ul className={styles.limits}>
        {result.limitations.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
      <p className={styles.disclaimer}>Illustrative assumptions — not a prediction, not advice</p>
    </details>
  );
}
