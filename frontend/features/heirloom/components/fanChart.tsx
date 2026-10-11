"use client";

import { useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { formatMoneyCompact } from "@/features/heirloom/format";
import type { YearQuantiles } from "@/features/heirloom/types/contracts";
import styles from "./fanChart.module.css";

// Hand-built SVG P10–P90 fan shared by the value and accessible-cash charts.
// Geometry lives in viewBox units; the SVG scales to its container width.
export const FAN_WIDTH = 560;
export const FAN_HEIGHT = 240;
const M = { top: 20, right: 64, bottom: 28, left: 56 };

export interface FanScales {
  x: (year: number) => number;
  y: (value: number) => number;
  step: number;
  top: number;
  bottom: number;
  left: number;
  right: number;
}

function niceStep(max: number, count: number): number {
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
}

export function FanChart({
  title,
  series,
  tone,
  minYMax = 0,
  overlays,
  tableLabel,
  endLabel = true,
}: {
  title: string;
  series: YearQuantiles[];
  tone: "ink" | "accent";
  /** Lower bound for the y-domain, so reference lines (e.g. the goal) stay on the plot. */
  minYMax?: number;
  overlays?: (s: FanScales) => ReactNode;
  tableLabel: string;
  /** Direct P50 label at the series end; off where a reference label owns the right margin. */
  endLabel?: boolean;
}) {
  const [active, setActive] = useState<number | null>(null);
  if (series.length === 0) return null;

  const first = series[0].year;
  const last = series[series.length - 1].year;
  const span = Math.max(1, last - first);
  const plotW = FAN_WIDTH - M.left - M.right;
  const plotH = FAN_HEIGHT - M.top - M.bottom;
  const dataMax = Math.max(minYMax, ...series.map((q) => q.p90));
  const yStep = niceStep(dataMax > 0 ? dataMax : 1, 4);
  const yMax = Math.ceil((dataMax > 0 ? dataMax : 1) / yStep) * yStep;

  const s: FanScales = {
    x: (year) => M.left + ((year - first) / span) * plotW,
    y: (v) => M.top + plotH - (v / yMax) * plotH,
    step: plotW / span,
    top: M.top,
    bottom: M.top + plotH,
    left: M.left,
    right: M.left + plotW,
  };

  const upper = series.map((q) => `${s.x(q.year)},${s.y(q.p90)}`);
  const lower = [...series].reverse().map((q) => `${s.x(q.year)},${s.y(q.p10)}`);
  const band = `M${upper.join("L")}L${lower.join("L")}Z`;
  const median = `M${series.map((q) => `${s.x(q.year)},${s.y(q.p50)}`).join("L")}`;
  const yTicks = Array.from({ length: Math.round(yMax / yStep) + 1 }, (_, i) => i * yStep);
  const xTicks = series.filter((q) => (q.year - first) % 5 === 0).map((q) => q.year);
  const end = series[series.length - 1];
  const hovered = active === null ? null : series[active];

  function onPointerMove(e: PointerEvent<SVGRectElement>) {
    const box = e.currentTarget.ownerSVGElement?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    const vx = ((e.clientX - box.left) / box.width) * FAN_WIDTH;
    const i = Math.round(((vx - M.left) / plotW) * span);
    setActive(Math.min(series.length - 1, Math.max(0, i)));
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const delta = e.key === "ArrowRight" ? 1 : -1;
    setActive((i) => Math.min(series.length - 1, Math.max(0, (i ?? -delta) + delta)));
  }

  return (
    <figure className={styles.figure}>
      <figcaption className={styles.title}>{title}</figcaption>
      <div
        className={styles.plot}
        tabIndex={0}
        aria-label={`${title}. Use left and right arrow keys to read each year.`}
        onKeyDown={onKeyDown}
        onBlur={() => setActive(null)}
      >
        <svg viewBox={`0 0 ${FAN_WIDTH} ${FAN_HEIGHT}`} className={styles.svg} role="img" aria-label={title}>
          {yTicks.map((t) => (
            <g key={t}>
              <line className={styles.grid} x1={s.left} x2={s.right} y1={s.y(t)} y2={s.y(t)} />
              <text className={styles.axis} x={s.left - 8} y={s.y(t)} textAnchor="end" dominantBaseline="middle">
                {formatMoneyCompact(t)}
              </text>
            </g>
          ))}
          {xTicks.map((year) => (
            <text
              key={year}
              className={styles.axis}
              data-tick-year={year}
              x={s.x(year)}
              y={s.bottom + 18}
              textAnchor="middle"
            >
              {`Yr ${year}`}
            </text>
          ))}
          <path className={`${styles.band} ${styles[tone]}`} d={band} />
          <path className={`${styles.median} ${styles[tone]}`} d={median} />
          {endLabel ? (
            <text className={styles.endLabel} x={s.x(end.year) + 8} y={s.y(end.p50)} dominantBaseline="middle">
              {`P50 ${formatMoneyCompact(end.p50)}`}
            </text>
          ) : null}
          {overlays?.(s)}
          {hovered ? (
            <g>
              <line className={styles.crosshair} x1={s.x(hovered.year)} x2={s.x(hovered.year)} y1={s.top} y2={s.bottom} />
              <circle className={`${styles.dot} ${styles[tone]}`} cx={s.x(hovered.year)} cy={s.y(hovered.p50)} r={4} />
            </g>
          ) : null}
          <rect
            className={styles.hit}
            x={s.left}
            y={s.top}
            width={plotW}
            height={plotH}
            onPointerMove={onPointerMove}
            onPointerLeave={() => setActive(null)}
          />
        </svg>
        {hovered ? (
          <div
            className={styles.tooltip}
            style={{ left: `${(s.x(hovered.year) / FAN_WIDTH) * 100}%` }}
            role="status"
          >
            <span className={styles.tipYear}>Year {hovered.year}</span>
            <span><strong>{formatMoneyCompact(hovered.p90)}</strong> P90</span>
            <span><strong>{formatMoneyCompact(hovered.p50)}</strong> P50</span>
            <span><strong>{formatMoneyCompact(hovered.p10)}</strong> P10</span>
          </div>
        ) : null}
      </div>
      <details className={styles.table}>
        <summary>Show table</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Year</th>
              <th scope="col">{tableLabel} P10</th>
              <th scope="col">P50</th>
              <th scope="col">P90</th>
            </tr>
          </thead>
          <tbody>
            {series.map((q) => (
              <tr key={q.year}>
                <td>{q.year}</td>
                <td>{formatMoneyCompact(q.p10)}</td>
                <td>{formatMoneyCompact(q.p50)}</td>
                <td>{formatMoneyCompact(q.p90)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
