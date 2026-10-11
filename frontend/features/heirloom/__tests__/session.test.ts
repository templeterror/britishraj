import { afterEach, describe, expect, it, vi } from "vitest";
import { clearSession, getSession, setSession } from "@/features/heirloom/session";
import type { RelaySession } from "@/features/heirloom/types/contracts";

const SESSION: RelaySession = {
  token: "demo.abc.def",
  familyId: "11111111-2222-3333-4444-555555555555",
  person: { id: "p-sarah", displayName: "Sarah Lin", role: "advisor" },
};

describe("relay session", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("round-trips through sessionStorage", () => {
    expect(getSession()).toBeNull();
    setSession(SESSION);
    expect(getSession()).toEqual(SESSION);
    expect(window.sessionStorage.getItem("heirloom.relay.session")).toContain("demo.abc.def");
    clearSession();
    expect(getSession()).toBeNull();
  });

  it("getSession returns null when sessionStorage.getItem throws", () => {
    setSession(SESSION);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage blocked");
    });
    expect(getSession()).toBeNull();
  });

  it("setSession and clearSession swallow storage errors", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => setSession(SESSION)).not.toThrow();
    expect(() => clearSession()).not.toThrow();
  });

  it("returns null for corrupt or malformed stored values", () => {
    window.sessionStorage.setItem("heirloom.relay.session", "{not json");
    expect(getSession()).toBeNull();
    window.sessionStorage.setItem("heirloom.relay.session", JSON.stringify({ token: 5 }));
    expect(getSession()).toBeNull();
  });
});
