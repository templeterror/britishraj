import styles from "./StatusLabel.module.css";

export type StatusTone = "verified" | "candidate" | "review" | "superseded" | "neutral";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-04-15" (or a full ISO timestamp) -> "15 Apr 2026"; anything else is shown as given. */
export function formatLabelDate(date: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(date);
  if (!m) return date;
  const month = MONTHS[Number(m[2]) - 1];
  return month ? `${Number(m[3])} ${month} ${m[1]}` : date;
}

/** Small-caps status line, e.g. "VERIFIED · 15 APR 2026 · ADVISOR-ONLY" (uppercased by CSS). */
export default function StatusLabel({
  tone,
  label,
  date,
  scope,
}: {
  tone: StatusTone;
  label: string;
  date?: string;
  scope?: string;
}) {
  const parts = [label, date ? formatLabelDate(date) : null, scope ?? null].filter(
    (p): p is string => p !== null,
  );
  return <span className={`${styles.label} ${styles[tone]}`}>{parts.join(" · ")}</span>;
}
