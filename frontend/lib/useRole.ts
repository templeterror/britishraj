"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession, useUser } from "@clerk/nextjs";
import { getSupabaseClient } from "@/lib/supabase";

export type WealthBridgeRole = "parent" | "child" | "wealth_manager";

export const ROLE_PATH: Record<WealthBridgeRole, string> = {
  parent: "/dashboard/parent",
  child: "/dashboard/child",
  wealth_manager: "/dashboard/wealth-manager",
};

type RoleState = {
  role: WealthBridgeRole | null;
  loading: boolean;
  error: string | null;
};

// Looks up (and lets the caller set) the WealthBridge role for the signed-in
// Clerk user, stored in Supabase's `user_roles` table. One row per user,
// enforced by RLS comparing clerk_user_id to the Clerk JWT's `sub` claim.
export function useRole() {
  const { session } = useSession();
  const { user } = useUser();
  const [state, setState] = useState<RoleState>({ role: null, loading: true, error: null });

  useEffect(() => {
    if (!session || !user) return;
    let cancelled = false;
    const supabase = getSupabaseClient(session);
    supabase
      .from("user_roles")
      .select("role")
      .eq("clerk_user_id", user.id)
      .maybeSingle()
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error) setState({ role: null, loading: false, error: error.message });
        else setState({ role: (data?.role as WealthBridgeRole) ?? null, loading: false, error: null });
      });
    return () => {
      cancelled = true;
    };
  }, [session, user]);

  const setRole = useCallback(
    async (role: WealthBridgeRole) => {
      if (!session || !user) return { error: "Not signed in" };
      const supabase = getSupabaseClient(session);
      const { error } = await supabase
        .from("user_roles")
        .insert({ clerk_user_id: user.id, role });
      if (error) return { error: error.message };
      setState({ role, loading: false, error: null });
      return { error: null };
    },
    [session, user]
  );

  return { ...state, setRole };
}
