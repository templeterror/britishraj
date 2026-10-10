"use client";

import { Show, RedirectToSignIn } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useRole, ROLE_PATH } from "@/lib/useRole";

function RoleGate() {
  const router = useRouter();
  const { role, loading, error } = useRole();

  if (!loading && !error) {
    router.replace(role ? ROLE_PATH[role] : "/select-role");
  }

  return (
    <main className="kb-page">
      {error ? (
        <p className="kb-error">Couldn&apos;t load your account: {error}</p>
      ) : (
        <p style={{ color: "#9a9a9a" }}>Loading...</p>
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
