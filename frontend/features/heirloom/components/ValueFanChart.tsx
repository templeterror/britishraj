"use client";

import type { ScenarioResultDTO } from "@/features/heirloom/types/contracts";
import { FanChart } from "./fanChart";
import styles from "./fanChart.module.css";

/** Paper (nominal) value of the named interest, P10–P90, with the hypothetical transfer year marked. */
export default function ValueFanChart({
  result,
  transferYear,
  goalYear,
}: {
  result: ScenarioResultDTO;
  transferYear: number;
  goalYear: number;
}) {
  return (
    <FanChart
      title="Paper value of the interest (P10–P90)"
      series={result.value_nominal}
      tone="ink"
      tableLabel="Value"
      overlays={(s) => (
        <>
          <line
            data-testid="transfer-marker"
            className={styles.transferMarker}
            x1={s.x(transferYear)}
            x2={s.x(transferYear)}
            y1={s.top}
            y2={s.bottom}
          />
          <text className={styles.markerLabel} x={s.x(transferYear) + 4} y={s.top - 6}>
            {`If transfer in yr ${transferYear}`}
          </text>
          <line className={styles.goalTick} x1={s.x(goalYear)} x2={s.x(goalYear)} y1={s.bottom - 6} y2={s.bottom} />
          <text className={styles.goalLabel} x={s.x(goalYear)} y={s.bottom - 10} textAnchor="middle">
            Goal
          </text>
        </>
      )}
    />
  );
}
