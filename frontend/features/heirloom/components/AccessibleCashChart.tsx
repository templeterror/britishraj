"use client";

import { formatMoneyCompact } from "@/features/heirloom/format";
import type { ScenarioResultDTO } from "@/features/heirloom/types/contracts";
import { FanChart } from "./fanChart";
import styles from "./fanChart.module.css";

/** True when median accessible cash at the goal year falls short of the goal (a timing gap is not a shortfall). */
export function hasShortfall(result: ScenarioResultDTO, goalNominal: number): boolean {
  return !result.transfer_after_goal && result.cash_at_goal.p50 < goalNominal;
}

/** Cash an heir could actually reach each year, P10–P90, if the transfer occurred in the scenario's year. */
export default function AccessibleCashChart({
  result,
  goalYear,
  goalNominal,
}: {
  result: ScenarioResultDTO;
  goalYear: number;
  goalNominal: number;
}) {
  const transferYear = result.settings.transfer_year;
  const shortfall = hasShortfall(result, goalNominal);
  return (
    <div>
      <FanChart
        title={`Accessible cash by year, if transfer occurred in year ${transferYear}`}
        series={result.cash_by_year}
        tone="accent"
        minYMax={goalNominal * 1.15}
        tableLabel="Cash"
        endLabel={false}
        overlays={(s) => (
          <>
            {shortfall ? (
              <rect
                data-testid="shortfall-zone"
                className={styles.shortfall}
                x={Math.max(s.left, s.x(goalYear) - s.step / 2)}
                width={s.step}
                y={s.y(goalNominal)}
                height={Math.max(0, s.y(result.cash_at_goal.p50) - s.y(goalNominal))}
              />
            ) : null}
            <line className={styles.goalLine} x1={s.left} x2={s.right} y1={s.y(goalNominal)} y2={s.y(goalNominal)} />
            <text className={styles.goalLabel} x={s.right + 4} y={s.y(goalNominal)} dominantBaseline="middle">
              {`Goal ${formatMoneyCompact(goalNominal)}`}
            </text>
            <line
              className={styles.transferMarker}
              x1={s.x(transferYear)}
              x2={s.x(transferYear)}
              y1={s.top}
              y2={s.bottom}
            />
            <text className={styles.markerLabel} x={s.x(transferYear) + 4} y={s.top - 6}>
              {`If transfer in yr ${transferYear}`}
            </text>
          </>
        )}
      />
      {result.transfer_after_goal ? (
        <p className={styles.note}>
          The transfer year falls after the goal year: a timing gap, not a shortfall.
        </p>
      ) : null}
    </div>
  );
}
