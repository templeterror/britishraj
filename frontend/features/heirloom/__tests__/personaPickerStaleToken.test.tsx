import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PersonaPicker from "@/features/heirloom/components/PersonaPicker";
import { getSession, setSession } from "@/features/heirloom/session";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const META = { revision: 0, consent_revision: 0, mode: "demo", degraded: [] };
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const STALE = {
  token: "stale-token",
  familyId: "fam-1",
  person: { id: "p-robert", displayName: "Robert Morgan", role: "parent" as const },
};

describe("PersonaPicker Reset demo with a stale stored token", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  const authHeader = (call: number) => new Headers(fetchMock.mock.calls[call][1]?.headers).get("Authorization");

  it("clears the rejected session and retries once with a freshly minted Sarah token", async () => {
    setSession(STALE);
    fetchMock
      .mockResolvedValueOnce(json(401, { data: null, meta: META, errors: [{ code: "unauthenticated", message: "Token rejected" }] }))
      .mockResolvedValueOnce(
        json(200, {
          data: { token: "fresh-token", family_id: "fam-1", person: { id: "p-sarah", display_name: "Sarah Lin", role: "advisor" } },
          meta: META,
          errors: [],
        }),
      )
      .mockResolvedValueOnce(json(200, { data: { status: "reset" }, meta: META, errors: [] }));
    render(<PersonaPicker />);

    await userEvent.click(screen.getByRole("button", { name: "Reset demo" }));

    expect(await screen.findByText("Demo data reset.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(getSession()).toBeNull();
    expect(fetchMock.mock.calls.map((c) => String(c[0]).split("/api/v1")[1])).toEqual([
      "/demo/reset",
      "/demo/sessions",
      "/demo/reset",
    ]);
    expect(authHeader(0)).toBe("Bearer stale-token");
    expect(authHeader(2)).toBe("Bearer fresh-token");
  });

  it("clears the session and shows an error when the retry is rejected too", async () => {
    setSession(STALE);
    const unauth = { data: null, meta: META, errors: [{ code: "unauthenticated", message: "Token rejected" }] };
    fetchMock
      .mockResolvedValueOnce(json(401, unauth))
      .mockResolvedValueOnce(
        json(200, {
          data: { token: "fresh-token", family_id: "fam-1", person: { id: "p-sarah", display_name: "Sarah Lin", role: "advisor" } },
          meta: META,
          errors: [],
        }),
      )
      .mockResolvedValueOnce(json(401, unauth));
    render(<PersonaPicker />);

    await userEvent.click(screen.getByRole("button", { name: "Reset demo" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(getSession()).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
