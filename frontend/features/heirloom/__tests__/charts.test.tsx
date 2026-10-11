import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AccessibleCashChart from "@/features/heirloom/components/AccessibleCashChart";
import ValueFanChart from "@/features/heirloom/components/ValueFanChart";
import { makeResult } from "./advisorFixtures";

function tickX(container: HTMLElement, year: number): number {
  const tick = container.querySelector(`[data-tick-year="${year}"]`);
  if (!tick) throw new Error(`no x-axis tick for year ${year}`);
  return Number(tick.getAttribute("x"));
}

describe("ValueFanChart", () => {
  it.each([10, 20])("renders one transfer marker at the x-position of year %i", (transferYear) => {
    const { container } = render(
      <ValueFanChart result={makeResult({ transferYear })} transferYear={transferYear} goalYear={12} />,
    );
    expect(screen.getByText("Paper value of the interest (P10–P90)")).toBeInTheDocument();

    const markers = screen.getAllByTestId("transfer-marker");
    expect(markers).toHaveLength(1);
    const marker = markers[0];
    expect(marker.tagName.toLowerCase()).toBe("line");
    const x = Number(marker.getAttribute("x1"));
    expect(Number(marker.getAttribute("x2"))).toBe(x);
    expect(x).toBeCloseTo(tickX(container, transferYear));
    expect(x).not.toBeCloseTo(tickX(container, transferYear === 10 ? 20 : 10));
  });
});

describe("AccessibleCashChart", () => {
  it("titles the chart with the hypothetical transfer year", () => {
    render(<AccessibleCashChart result={makeResult({ transferYear: 20 })} goalYear={25} goalNominal={900_000} />);
    expect(
      screen.getByText("Accessible cash by year, if transfer occurred in year 20"),
    ).toBeInTheDocument();
  });

  it("renders the shortfall zone when cash p50 at the goal year is below the goal", () => {
    const result = makeResult({ cashAtGoalP50: 300_000, goalNominal: 672_444 });
    render(<AccessibleCashChart result={result} goalYear={12} goalNominal={672_444} />);
    expect(screen.getByTestId("shortfall-zone")).toBeInTheDocument();
  });

  it("renders no shortfall zone when cash p50 at the goal year covers the goal", () => {
    const result = makeResult({ cashAtGoalP50: 900_000, goalNominal: 672_444 });
    render(<AccessibleCashChart result={result} goalYear={12} goalNominal={672_444} />);
    expect(screen.queryByTestId("shortfall-zone")).not.toBeInTheDocument();
  });
});
