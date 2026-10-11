import type { RelaySession } from "@/features/heirloom/types/contracts";

const KEY = "heirloom.relay.session";
const CHANGE_EVENT = "heirloom.relay.session-change";

function isSession(value: unknown): value is RelaySession {
  if (typeof value !== "object" || value === null) return false;
  const s = value as Record<string, unknown>;
  const p = s.person as Record<string, unknown> | null | undefined;
  return (
    typeof s.token === "string" &&
    typeof s.familyId === "string" &&
    typeof p === "object" &&
    p !== null &&
    typeof p.id === "string" &&
    typeof p.displayName === "string" &&
    typeof p.role === "string"
  );
}

function notify(): void {
  try {
    window.dispatchEvent(new Event(CHANGE_EVENT));
  } catch {
    // no window (SSR) — nothing to notify
  }
}

/** Raw stored string; a stable snapshot for useSyncExternalStore. */
export function getSessionRaw(): string | null {
  try {
    return window.sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function parseSession(raw: string | null): RelaySession | null {
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    return isSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function getSession(): RelaySession | null {
  return parseSession(getSessionRaw());
}

export function setSession(session: RelaySession): void {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    // storage unavailable: the session simply will not persist
  }
  notify();
}

export function clearSession(): void {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    // storage unavailable
  }
  notify();
}

export function subscribeSession(listener: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(CHANGE_EVENT, listener);
    window.removeEventListener("storage", listener);
  };
}
