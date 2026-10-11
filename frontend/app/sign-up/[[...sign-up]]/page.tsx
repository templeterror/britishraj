import { Suspense } from "react";
import { SignUp } from "@clerk/nextjs";
import { HeirloomLogo } from "@/components/HeirloomLogo";

export default function Page() {
  return (
    <main className="kb-page">
      <div className="kb-logo">
        <HeirloomLogo size={30} />
      </div>
      {/* See the same comment on the sign-in page. */}
      <Suspense fallback={<p style={{ color: "var(--text-secondary)" }}>Loading sign-up...</p>}>
        <SignUp />
      </Suspense>
    </main>
  );
}
