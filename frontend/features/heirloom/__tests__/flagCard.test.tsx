import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import FlagCard from "@/features/heirloom/components/FlagCard";
import { makeInsight } from "./advisorFixtures";

describe("FlagCard", () => {
  it("renders the headline probability as a percent with its condition as the caption", async () => {
    const onOpen = vi.fn();
    render(<FlagCard insight={makeInsight()} onOpen={onOpen} />);

    expect(screen.getByText("6%")).toBeInTheDocument();
    expect(
      screen.getByText("if transfer occurred in year 10 and exit took 24 months longer"),
    ).toBeInTheDocument();
    expect(screen.getByText("James shared a business goal in year 12.")).toBeInTheDocument();
    expect(screen.getByText("Review required · Illustrative")).toBeInTheDocument();
    expect(screen.getAllByTestId("evidence-chip")).toHaveLength(3);

    await userEvent.click(screen.getByRole("button", { name: /Liquidity for James's goal/ }));
    expect(onOpen).toHaveBeenCalledWith("ins-1");
  });

  it('renders "Unknown" when headline_probability is null', () => {
    render(
      <FlagCard
        insight={makeInsight({
          headline_probability: null,
          headline_condition: "Access terms unknown — attorney review",
        })}
        onOpen={() => {}}
      />,
    );
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
    expect(screen.getByText("Access terms unknown — attorney review")).toBeInTheDocument();
  });
});
