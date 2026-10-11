"use client";

import { useMemo, useSyncExternalStore } from "react";
import { getSessionRaw, parseSession, subscribeSession } from "@/features/heirloom/session";
import type { RelaySession } from "@/features/heirloom/types/contracts";

/** Current persona session; null on the server, before hydration, or when signed out. */
export function useSession(): RelaySession | null {
  const raw = useSyncExternalStore(subscribeSession, getSessionRaw, () => null);
  return useMemo(() => parseSession(raw), [raw]);
}
