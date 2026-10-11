"use client";

import { Show, RedirectToSignIn } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useRole, ROLE_PATH } from "@/lib/useRole";
import { ensureRelaySession } from "@/lib/relaySession";

function RoleGate() {
  const router = useRouter();
  const { role, loading, error } = useRole();

  useEffect(() => {
    if (loading || error) return;
    if (!role) {
      router.replace("/select-role");
      return;
    }
    // Returning user with a stored role — mint their Relay demo session if
    // it's not already in sessionStorage (fresh tab, etc.), then push into
    // the matching Relay screen. We never block navigation on the mint; if
    // the backend is unreachable the Relay screens will surface their own
    // error states, which is still better than looping on a loading spinner.
    let cancelled = false;
    ensureRelaySession(role)
      .catch((e) => {
        console.warn("Could not mint relay demo session:", e);
      })
      .finally(() => {
        if (!cancelled) router.replace(ROLE_PATH[role]);
      });
    return () => {
      cancelled = true;
    };
  }, [loading, error, role, router]);

  return (
    <main className="kb-page">
      {error ? (
        <p className="kb-error">Couldn&apos;t load your account: {error}</p>
      ) : (
        <p style={{ color: "var(--text-secondary)" }}>Loading...</p>
      )}
    </main>
  );
}

export default function Home() {
  return (
    <Show when="signed-in" fallback={<RedirectToSignIn />}>
      <RoleGate />
    </Show>
  );
}
