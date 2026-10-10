"use client";

import { SignedIn, SignedOut, RedirectToSignIn } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useRole, ROLE_PATH, type WealthBridgeRole } from "@/lib/useRole";

function Guarded({ expected, children }: { expected: WealthBridgeRole; children: ReactNode }) {
  const router = useRouter();
  const { role, loading, error } = useRole();

  if (!loading && !error && role !== expected) {
    router.replace(role ? ROLE_PATH[role] : "/select-role");
    return null;
  }

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

  return <>{children}</>;
}

// Wraps a dashboard page: redirects signed-out users to sign-in, and
// redirects a signed-in user whose stored role doesn't match `expected`
// to their actual dashboard (or to /select-role if they have none yet).
export function RoleGuard({ expected, children }: { expected: WealthBridgeRole; children: ReactNode }) {
  return (
    <>
      <SignedIn>
        <Guarded expected={expected}>{children}</Guarded>
      </SignedIn>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
}
