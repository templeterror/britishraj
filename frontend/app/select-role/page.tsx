"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { HeirloomLogo } from "@/components/HeirloomLogo";
import { Show, RedirectToSignIn } from "@clerk/nextjs";
import { useRole, ROLE_PATH, type HeirloomRole } from "@/lib/useRole";

const ROLES: { id: HeirloomRole; title: string; desc: string }[] = [
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
  const [submitting, setSubmitting] = useState<HeirloomRole | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && role) {
      router.replace(ROLE_PATH[role]);
    }
  }, [loading, role, router]);

  if (!loading && role) {
    return null;
  }

  async function choose(id: HeirloomRole) {
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
      <div className="kb-logo">
        <HeirloomLogo size={30} />
      </div>
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
    <Show when="signed-in" fallback={<RedirectToSignIn />}>
      <RoleSelector />
    </Show>
  );
}
