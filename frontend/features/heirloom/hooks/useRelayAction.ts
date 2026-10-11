"use client";

import { useState } from "react";
import { RelayApiError } from "@/features/heirloom/api/client";

export interface RelayAction {
  busy: boolean;
  error: string | null;
  /** Show a validation message without making a request. */
  fail: (message: string) => void;
  /** Run one write; resolves true on success. */
  run: (call: () => Promise<unknown>) => Promise<boolean>;
}

/**
 * State for one form's writes. On success `onChanged` refetches. A 409 means the record moved on
 * elsewhere (stale source, already verified), so it refetches too and shows the server's message.
 */
export function useRelayAction(onChanged: () => void, fallback = "The change could not be saved."): RelayAction {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(call: () => Promise<unknown>): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      await call();
      onChanged();
      return true;
    } catch (err) {
      setError(err instanceof RelayApiError ? err.message : fallback);
      if (err instanceof RelayApiError && err.status === 409) onChanged();
      return false;
    } finally {
      setBusy(false);
    }
  }

  return { busy, error, fail: setError, run };
}
