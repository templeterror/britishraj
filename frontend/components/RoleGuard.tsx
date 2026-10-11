"use client";

import { Show, RedirectToSignIn, useOrganization } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useRole, ROLE_PATH, type HeirloomRole } from "@/lib/useRole";

function Guarded({ expected, children }: { expected: HeirloomRole; children: ReactNode }) {
  const router = useRouter();
  const { role, loading, error } = useRole();
  const { organization, isLoaded: orgLoaded } = useOrganization();
  const mismatched = !loading && !error && role !== expected;
  // Wealth managers need an active firm (Clerk Organization) to see their
  // dashboard — without one there's no tenant to scope the data to.
  const needsFirm = expected === "wealth_manager" && !mismatched && orgLoaded && !organization;

  useEffect(() => {
    if (mismatched) {
      router.replace(role ? ROLE_PATH[role] : "/select-role");
    } else if (needsFirm) {
      router.replace("/create-firm");
    }
  }, [mismatched, needsFirm, role, router]);

  if (loading || !orgLoaded) {
    return (
      <main className="kb-page">
        <p style={{ color: "var(--text-secondary)" }}>Loading...</p>
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

  if (mismatched || needsFirm) {
    // Redirecting via the effect above; render nothing in the meantime
    // instead of this page's content, so the wrong screen never flashes.
    return (
      <main className="kb-page">
        <p style={{ color: "var(--text-secondary)" }}>Redirecting...</p>
      </main>
    );
  }

  return <>{children}</>;
}

// Wraps a dashboard page: redirects signed-out users to sign-in, redirects
// a signed-in user whose stored role doesn't match `expected` to their
// actual dashboard (or to /select-role if they have none yet), and sends a
// Wealth Manager with no active firm to /create-firm first.
export function RoleGuard({ expected, children }: { expected: HeirloomRole; children: ReactNode }) {
  return (
    <Show when="signed-in" fallback={<RedirectToSignIn />}>
      <Guarded expected={expected}>{children}</Guarded>
    </Show>
  );
}
