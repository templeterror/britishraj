import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RelayApiError } from "@/features/heirloom/api/client";
import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import { useRevisionPoll } from "@/features/heirloom/hooks/useRevisionPoll";

const get = vi.hoisted(() => vi.fn());
vi.mock("@/features/heirloom/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/heirloom/api/client")>();
  return { ...actual, default: { get } };
});

const META = { revision: 1, consent_revision: 0, mode: "demo" as const, degraded: [] };

afterEach(() => {
  get.mockReset();
});

describe("useRelayQuery", () => {
  it("loads data, then surfaces a recoverable error and reloads on demand", async () => {
    get.mockRejectedValueOnce(new RelayApiError(0, "network_error", "Failed to fetch"));
    get.mockResolvedValueOnce({ data: { hello: "world" }, meta: META, errors: [] });

    const { result } = renderHook(() => useRelayQuery<{ hello: string }>("/families/f1/snapshot"));
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.error?.code).toBe("network_error"));
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeUndefined();

    act(() => result.current.reload());
    await waitFor(() => expect(result.current.data).toEqual({ hello: "world" }));
    expect(result.current.error).toBeUndefined();
    expect(result.current.meta?.mode).toBe("demo");
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("does not fetch when path is null", () => {
    const { result } = renderHook(() => useRelayQuery(null));
    expect(result.current.loading).toBe(false);
    expect(get).not.toHaveBeenCalled();
  });

  it("refetches when deps change", async () => {
    get.mockResolvedValue({ data: 1, meta: META, errors: [] });
    const { rerender } = renderHook(({ dep }) => useRelayQuery<number>("/x", [dep]), {
      initialProps: { dep: "a" },
    });
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
    rerender({ dep: "b" });
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });
});

describe("useRevisionPoll", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
  });

  function Probe({ onChange }: { onChange: () => void }) {
    useRevisionPoll("fam-1", onChange, 1000);
    return <div>probe</div>;
  }

  const rev = (revision: number, consent_revision: number) => ({
    data: { revision, consent_revision },
    meta: META,
    errors: [],
  });

  it("calls onChange only when revision or consent_revision changes", async () => {
    const onChange = vi.fn();
    get.mockResolvedValue(rev(1, 0));
    render(<Probe onChange={onChange} />);
    expect(screen.getByText("probe")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(get).toHaveBeenCalledWith("/families/fam-1/revision");
    expect(onChange).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(onChange).not.toHaveBeenCalled();

    get.mockResolvedValue(rev(2, 0));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(onChange).toHaveBeenCalledTimes(1);

    get.mockResolvedValue(rev(2, 1));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it("pauses while the document is hidden", async () => {
    const onChange = vi.fn();
    get.mockResolvedValue(rev(1, 0));
    render(<Probe onChange={onChange} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const callsAfterBaseline = get.mock.calls.length;

    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    get.mockResolvedValue(rev(5, 5));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(get.mock.calls.length).toBe(callsAfterBaseline);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("keeps polling after a failed request", async () => {
    const onChange = vi.fn();
    get.mockResolvedValueOnce(rev(1, 0));
    render(<Probe onChange={onChange} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    get.mockRejectedValueOnce(new RelayApiError(0, "network_error", "down"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    get.mockResolvedValue(rev(2, 0));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});
