import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RelayApiError } from "@/features/heirloom/api/client";
import ModeBadge from "@/features/heirloom/components/ModeBadge";
import StatusLabel from "@/features/heirloom/components/StatusLabel";
import { EmptyState, ErrorState, LoadingState } from "@/features/heirloom/components/StateViews";

describe("ErrorState", () => {
  it("renders message and calls onRetry on click", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new RelayApiError(403, "forbidden_for_role", "Not allowed for your role.")} onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Not allowed for your role.");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("explains an unreachable backend and still offers Retry", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new RelayApiError(0, "network_error", "Failed to fetch")} onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Can't reach Heirloom Relay");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe("other state views", () => {
  it("LoadingState announces its label", () => {
    render(<LoadingState label="Loading flags" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading flags");
  });

  it("EmptyState shows title and body", () => {
    render(<EmptyState title="No open flags." body="James has not shared any current goals." />);
    expect(screen.getByText("No open flags.")).toBeInTheDocument();
    expect(screen.getByText("James has not shared any current goals.")).toBeInTheDocument();
  });

  it("ModeBadge shows Mock data mode only in demo mode", () => {
    const { rerender } = render(<ModeBadge mode="demo" />);
    expect(screen.getByText("Mock data mode")).toBeInTheDocument();
    rerender(<ModeBadge mode="clerk" />);
    expect(screen.queryByText("Mock data mode")).not.toBeInTheDocument();
  });

  it("StatusLabel composes tone, date and scope", () => {
    render(<StatusLabel tone="verified" label="Verified" date="2026-04-15" scope="Advisor-only" />);
    expect(screen.getByText("Verified · 15 Apr 2026 · Advisor-only")).toBeInTheDocument();
  });
});
