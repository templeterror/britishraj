"use client";

import { Show, RedirectToSignIn, CreateOrganization, useOrganization } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { HeirloomLogo } from "@/components/HeirloomLogo";
import { ROLE_PATH } from "@/lib/useRole";

function CreateFirm() {
  const router = useRouter();
  const { organization, isLoaded } = useOrganization();

  // Once an organization becomes active (just created, or already existed),
  // move on to the wealth manager dashboard.
  useEffect(() => {
    if (isLoaded && organization) {
      router.replace(ROLE_PATH.wealth_manager);
    }
  }, [isLoaded, organization, router]);

  return (
    <main className="kb-page">
      <div className="kb-logo">
        <HeirloomLogo size={30} />
      </div>
      <h1 style={{ marginBottom: "0.25rem" }}>Set up your firm</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: "2rem", textAlign: "center", maxWidth: 440 }}>
        As a Wealth Manager, you work inside a firm (a Clerk Organization).
        Create one now, or switch to an existing firm you&apos;re already a
        member of from the organization switcher.
      </p>
      <CreateOrganization />
    </main>
  );
}

export default function CreateFirmPage() {
  return (
    <Show when="signed-in" fallback={<RedirectToSignIn />}>
      <CreateFirm />
    </Show>
  );
}
