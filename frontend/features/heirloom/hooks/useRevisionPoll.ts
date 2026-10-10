"use client";

import { useEffect, useRef } from "react";
import relay from "@/features/heirloom/api/client";
import type { RevisionDTO } from "@/features/heirloom/types/contracts";

/**
 * Polls /families/{id}/revision and calls `onChange` when `revision` or
 * `consent_revision` differs from the last value seen. The first response only
 * sets the baseline. Paused while the tab is hidden; request failures are
 * ignored (the next tick retries, and a 401 is handled by the client).
 */
export function useRevisionPoll(familyId: string | null, onChange: () => void, intervalMs = 2500): void {
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    if (!familyId) return;
    let stopped = false;
    let inFlight = false;
    let seen: RevisionDTO | null = null;

    async function tick() {
      if (stopped || inFlight || document.hidden) return;
      inFlight = true;
      try {
        const { data } = await relay.get<RevisionDTO>(`/families/${familyId}/revision`);
        if (stopped) return;
        const changed =
          seen !== null &&
          (seen.revision !== data.revision || seen.consent_revision !== data.consent_revision);
        seen = { revision: data.revision, consent_revision: data.consent_revision };
        if (changed) onChangeRef.current();
      } catch {
        // transient failure: try again on the next tick
      } finally {
        inFlight = false;
      }
    }

    void tick();
    const timer = setInterval(() => void tick(), intervalMs);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [familyId, intervalMs]);
}
