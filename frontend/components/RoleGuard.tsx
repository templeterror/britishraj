"use client";

import { Show, RedirectToSignIn } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useRole, ROLE_PATH, type HeirloomRole } from "@/lib/useRole";

function Guarded({ expected, children }: { expected: HeirloomRole; children: ReactNode }) {
  const router = useRouter();
  const { role, loading, error } = useRole();
  const mismatched = !loading && !error && role !== expected;

  useEffect(() => {
    if (mismatched) {
      router.replace(role ? ROLE_PATH[role] : "/select-role");
    }
  }, [mismatched, role, router]);

  if (loading) {
    return (
      <main className="kb-page">
        <p style={{ color: "#9a9a9a" }}>Loading...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="kb-page">
        <p className="kb-error">Couldn&apos;t load your account: {error}</p>
      </main>
    );
  }

  if (mismatched) {
    // Redirecting via the effect above; render nothing in the meantime
    // instead of this page's content, so the wrong dashboard never flashes.
    return (
      <main className="kb-page">
        <p style={{ color: "#9a9a9a" }}>Redirecting...</p>
      </main>
    );
  }

  return <>{children}</>;
}

// Wraps a dashboard page: redirects signed-out users to sign-in, and
// redirects a signed-in user whose stored role doesn't match `expected`
// to their actual dashboard (or to /select-role if they have none yet).
export function RoleGuard({ expected, children }: { expected: HeirloomRole; children: ReactNode }) {
  return (
    <Show when="signed-in" fallback={<RedirectToSignIn />}>
      <Guarded expected={expected}>{children}</Guarded>
    </Show>
  );
}
