import { describe, expect, it, vi } from "vitest";
import {
  RelayApiError,
  createRelayClient,
  handleUnauthenticated,
} from "@/features/heirloom/api/client";
import { getSession, setSession } from "@/features/heirloom/session";

const META = { revision: 3, consent_revision: 1, mode: "demo", degraded: [] };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch, extra: { onUnauthenticated?: () => void } = {}) {
  return createRelayClient({
    baseUrl: "http://api.test/api/v1",
    getToken: () => "tok-123",
    fetchImpl,
    ...extra,
  });
}

describe("relay client", () => {
  it("sends bearer and no-store", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ data: { ok: true }, meta: META, errors: [] }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const env = await client.get<{ ok: boolean }>("/families/f1/revision");

    expect(env.data).toEqual({ ok: true });
    expect(env.meta.revision).toBe(3);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://api.test/api/v1/families/f1/revision");
    expect(init.cache).toBe("no-store");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok-123");
    expect(init.method).toBe("GET");
  });

  it("sends JSON bodies for post, put and patch", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ data: {}, meta: META, errors: [] }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await client.post("/demo/sessions", { persona: "sarah" });
    await client.put("/families/f1/consents/r1", { active: true });
    await client.patch("/families/f1/heir-goals/g1", { version: 2 });

    const calls = fetchImpl.mock.calls as unknown as [string, RequestInit][];
    expect(calls.map(([, init]) => init.method)).toEqual(["POST", "PUT", "PATCH"]);
    expect(calls[0][1].body).toBe(JSON.stringify({ persona: "sarah" }));
    expect(new Headers(calls[0][1].headers).get("Content-Type")).toBe("application/json");
  });

  it("omits the Authorization header when there is no token", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ data: {}, meta: META, errors: [] }));
    const client = createRelayClient({
      baseUrl: "http://api.test/api/v1",
      getToken: () => null,
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    await client.get("/health");
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(init.headers).has("Authorization")).toBe(false);
  });

  it("throws RelayApiError with server code", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(
        {
          data: null,
          meta: META,
          errors: [{ code: "forbidden_for_role", message: "Not allowed for your role." }],
        },
        403,
      ),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const err = await client.get("/families/f1/insights").catch((e: unknown) => e);

    expect(err).toBeInstanceOf(RelayApiError);
    expect((err as RelayApiError).status).toBe(403);
    expect((err as RelayApiError).code).toBe("forbidden_for_role");
    expect((err as RelayApiError).message).toBe("Not allowed for your role.");
  });

  it("falls back to http_error when the error body is not an envelope", async () => {
    const fetchImpl = vi.fn(async () => new Response("<html>bad gateway</html>", { status: 502 }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const err = (await client.get("/health").catch((e: unknown) => e)) as RelayApiError;

    expect(err).toBeInstanceOf(RelayApiError);
    expect(err.status).toBe(502);
    expect(err.code).toBe("http_error");
  });

  it("401 triggers onUnauthenticated", async () => {
    const onUnauthenticated = vi.fn();
    const fetchImpl = vi.fn(async () =>
      jsonResponse(
        { data: null, meta: META, errors: [{ code: "unauthenticated", message: "Sign in again." }] },
        401,
      ),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch, { onUnauthenticated });

    const err = (await client.get("/families/f1/snapshot").catch((e: unknown) => e)) as RelayApiError;

    expect(onUnauthenticated).toHaveBeenCalledTimes(1);
    expect(err).toBeInstanceOf(RelayApiError);
    expect(err.status).toBe(401);
    expect(err.code).toBe("unauthenticated");
  });

  it("network failure becomes network_error", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    const onUnauthenticated = vi.fn();
    const client = makeClient(fetchImpl as unknown as typeof fetch, { onUnauthenticated });

    const err = (await client.get("/families/f1/snapshot").catch((e: unknown) => e)) as RelayApiError;

    expect(err).toBeInstanceOf(RelayApiError);
    expect(err.status).toBe(0);
    expect(err.code).toBe("network_error");
    expect(onUnauthenticated).not.toHaveBeenCalled();
  });
});

describe("default unauthenticated handler", () => {
  const demoSession = {
    token: "demo.stale.token",
    familyId: "fam-1",
    person: { id: "p-1", displayName: "Sarah Lin", role: "advisor" as const },
  };

  it("clears the stored session and navigates to the picker", () => {
    setSession(demoSession);
    const navigate = vi.fn();

    handleUnauthenticated(navigate);

    expect(getSession()).toBeNull();
    expect(navigate).toHaveBeenCalledWith("/relay");
  });

  it("does not navigate when already on the picker", () => {
    setSession(demoSession);
    window.history.pushState({}, "", "/relay");
    const navigate = vi.fn();

    handleUnauthenticated(navigate);

    expect(getSession()).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
    window.history.pushState({}, "", "/");
  });
});
