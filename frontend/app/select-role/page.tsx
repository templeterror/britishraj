"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Image from "next/image";
import { SignedIn, SignedOut, RedirectToSignIn } from "@clerk/nextjs";
import { useRole, ROLE_PATH, type WealthBridgeRole } from "@/lib/useRole";

const ROLES: { id: WealthBridgeRole; title: string; desc: string }[] = [
  {
    id: "parent",
    title: "Parent",
    desc: "View your portfolio, record your financial goals and estate intentions, and see how your decisions support your family.",
  },
  {
    id: "child",
    title: "Child / Heir",
    desc: "Share your financial goals, understand what's being planned for you, and ask questions about your family's financial history.",
  },
  {
    id: "wealth_manager",
    title: "Wealth Manager",
    desc: "Oversee family relationships, explore the knowledge graph, and get alerted when a family's plans and goals fall out of alignment.",
  },
];

function RoleSelector() {
  const router = useRouter();
  const { role, loading, error, setRole } = useRole();
  const [submitting, setSubmitting] = useState<WealthBridgeRole | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  if (!loading && role) {
    router.replace(ROLE_PATH[role]);
    return null;
  }

  async function choose(id: WealthBridgeRole) {
    setSubmitting(id);
    setSubmitError(null);
    const { error } = await setRole(id);
    if (error) {
      setSubmitError(error);
      setSubmitting(null);
      return;
    }
    router.replace(ROLE_PATH[id]);
  }

  return (
    <main className="kb-page">
      <Image
        src="/kalshi-logo-tagline.svg"
        alt="WealthBridge"
        width={220}
        height={26}
        className="kb-logo"
        priority
      />
      <h1 style={{ marginBottom: "0.25rem" }}>Who's signing in?</h1>
      <p style={{ color: "#9a9a9a", marginBottom: "2rem" }}>
        Pick your role. This is a one-time setup step for your account.
      </p>

      {loading && <p>Loading...</p>}
      {error && <p className="kb-error">Couldn&apos;t check your account: {error}</p>}

      {!loading && (
        <div className="kb-role-grid">
          {ROLES.map((r) => (
            <button
              key={r.id}
              className="kb-role-card"
              disabled={submitting !== null}
              onClick={() => choose(r.id)}
            >
              <p className="kb-role-title">
                {submitting === r.id ? "Saving..." : r.title}
              </p>
              <p className="kb-role-desc">{r.desc}</p>
            </button>
          ))}
        </div>
      )}

      {submitError && (
        <p className="kb-error" style={{ marginTop: "1.5rem" }}>
          Couldn&apos;t save your role: {submitError}
        </p>
      )}
    </main>
  );
}

export default function SelectRolePage() {
  return (
    <>
      <SignedIn>
        <RoleSelector />
      </SignedIn>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
}
