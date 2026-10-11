"use client";

import { useCallback, useEffect, useState } from "react";
import relay, { RelayApiError } from "@/features/heirloom/api/client";
import type { Meta } from "@/features/heirloom/types/contracts";

interface QueryState<T> {
  key: string;
  path: string;
  data?: T;
  meta?: Meta;
  error?: RelayApiError;
}

export interface RelayQuery<T> {
  data: T | undefined;
  meta: Meta | undefined;
  error: RelayApiError | undefined;
  loading: boolean;
  reload: () => void;
}

function toApiError(e: unknown): RelayApiError {
  return e instanceof RelayApiError
    ? e
    : new RelayApiError(0, "network_error", e instanceof Error ? e.message : "Request failed");
}

/**
 * GET `path` through the relay client. Pass null to skip. `deps` re-run the request.
 * While a reload is in flight the previous data for the same path stays available.
 */
export function useRelayQuery<T>(path: string | null, deps: unknown[] = []): RelayQuery<T> {
  const [tick, setTick] = useState(0);
  const [state, setState] = useState<QueryState<T> | null>(null);
  const depsKey = JSON.stringify(deps);
  const key = path === null ? "" : `${path}|${tick}|${depsKey}`;

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    relay
      .get<T>(path)
      .then((env) => {
        if (!cancelled) setState({ key, path, data: env.data, meta: env.meta });
      })
      .catch((e: unknown) => {
        if (!cancelled) setState({ key, path, error: toApiError(e) });
      });
    return () => {
      cancelled = true;
    };
  }, [key, path]);

  const reload = useCallback(() => setTick((n) => n + 1), []);

  const current = state !== null && path !== null && state.path === path ? state : null;
  return {
    data: current?.data,
    meta: current?.meta,
    error: current && current.key === key ? current.error : undefined,
    loading: path !== null && state?.key !== key,
    reload,
  };
}
