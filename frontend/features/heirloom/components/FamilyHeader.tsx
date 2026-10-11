import { formatMoneyCompact } from "@/features/heirloom/format";
import type { AdvisorSnapshot } from "@/features/heirloom/types/contracts";
import styles from "./FamilyHeader.module.css";

/** Family context for the advisor. Deliberately shows coverage, never a "$ at risk" figure. */
export default function FamilyHeader({ snapshot }: { snapshot: AdvisorSnapshot }) {
  const { coverage: c } = snapshot;
  const total = snapshot.assets.reduce((sum, a) => sum + a.value, 0);
  const chips = [
    `${c.decisions_verified} of ${c.decisions_total} decisions verified`,
    `${c.assets_with_verified_intent} of ${c.assets_total} assets with verified intent`,
    `Heirs connected ${c.heirs_connected} of ${c.heirs_total}`,
  ];
  return (
    <header className={styles.header}>
      <div className={styles.identity}>
        <h1 className={styles.family}>{snapshot.family.display_name}</h1>
        <p className={styles.advisor}>Advisor: {snapshot.advisor.display_name}</p>
      </div>
      <dl className={styles.stats}>
        <div>
          <dt>Assets under advisement (synthetic)</dt>
          <dd>{formatMoneyCompact(total)}</dd>
        </div>
        <div data-alert={snapshot.open_flags > 0 ? "true" : undefined}>
          <dt>Open flags</dt>
          <dd>{snapshot.open_flags}</dd>
        </div>
      </dl>
      <ul className={styles.chips} aria-label="Coverage">
        {chips.map((chip) => (
          <li key={chip} className={styles.chip}>
            {chip}
          </li>
        ))}
      </ul>
    </header>
  );
}
