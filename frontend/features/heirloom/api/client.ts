import { clearSession, getSession } from "@/features/heirloom/session";
import type { Envelope } from "@/features/heirloom/types/contracts";

export class RelayApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "RelayApiError";
    this.status = status;
    this.code = code;
  }
}

export interface RelayClientOptions {
  /** API root including the version prefix, e.g. http://localhost:8000/api/v1 */
  baseUrl: string;
  getToken: () => string | null;
  onUnauthenticated?: () => void;
  fetchImpl?: typeof fetch;
}

export interface RelayClient {
  get<T>(path: string): Promise<Envelope<T>>;
  post<T>(path: string, body?: unknown): Promise<Envelope<T>>;
  put<T>(path: string, body: unknown): Promise<Envelope<T>>;
  patch<T>(path: string, body: unknown): Promise<Envelope<T>>;
}

type Method = "GET" | "POST" | "PUT" | "PATCH";

async function readEnvelope(res: Response): Promise<Partial<Envelope<unknown>> | null> {
  try {
    const parsed: unknown = await res.json();
    return typeof parsed === "object" && parsed !== null ? (parsed as Partial<Envelope<unknown>>) : null;
  } catch {
    return null;
  }
}

export function createRelayClient(opts: RelayClientOptions): RelayClient {
  async function request<T>(method: Method, path: string, body?: unknown): Promise<Envelope<T>> {
    const headers = new Headers({ Accept: "application/json" });
    const token = opts.getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const init: RequestInit = { method, headers, cache: "no-store" };
    if (body !== undefined) {
      headers.set("Content-Type", "application/json");
      init.body = JSON.stringify(body);
    }

    let res: Response;
    try {
      res = await (opts.fetchImpl ?? fetch)(`${opts.baseUrl}${path}`, init);
    } catch (cause) {
      throw new RelayApiError(0, "network_error", cause instanceof Error ? cause.message : "Network error");
    }

    const envelope = await readEnvelope(res);
    if (!res.ok) {
      const item = envelope?.errors?.[0];
      if (res.status === 401) opts.onUnauthenticated?.();
      throw new RelayApiError(
        res.status,
        item?.code ?? "http_error",
        item?.message ?? `Request failed with status ${res.status}`,
      );
    }
    if (!envelope || !("data" in envelope)) {
      throw new RelayApiError(res.status, "bad_response", "The server returned an unexpected response.");
    }
    return envelope as Envelope<T>;
  }

  return {
    get: (path) => request("GET", path),
    post: (path, body) => request("POST", path, body),
    put: (path, body) => request("PUT", path, body),
    patch: (path, body) => request("PATCH", path, body),
  };
}

const PICKER_PATH = "/relay";

/** Expired or rejected token: drop the session and return to the persona picker. */
export function handleUnauthenticated(navigate: (path: string) => void = (p) => window.location.assign(p)): void {
  clearSession();
  if (typeof window !== "undefined" && window.location.pathname.replace(/\/$/, "") !== PICKER_PATH) {
    navigate(PICKER_PATH);
  }
}

export const RELAY_BASE_URL = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1`;

const relay = createRelayClient({
  baseUrl: RELAY_BASE_URL,
  getToken: () => getSession()?.token ?? null,
  onUnauthenticated: () => handleUnauthenticated(),
});

export default relay;
