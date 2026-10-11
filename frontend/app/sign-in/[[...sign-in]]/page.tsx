import { Suspense } from "react";
import { SignIn } from "@clerk/nextjs";
import { HeirloomLogo } from "@/components/HeirloomLogo";

export default function Page() {
  return (
    <main className="kb-page">
      <div className="kb-auth-mark-row">
        <HeirloomLogo size={34} withWordmark={false} />
        <div>
          <p className="kb-auth-wordmark">Heirloom</p>
          <p className="kb-auth-tagline">Wealth, kept in the family.</p>
        </div>
      </div>
      {/* Clerk's <SignIn /> reads routing info via usePathname()/useSearchParams(),
          which Next.js 16 flags as a prerender blocker if not in a Suspense
          boundary. Wrapping it here lets the page shell prerender while the
          Clerk widget streams in. */}
      <Suspense fallback={<p style={{ color: "var(--text-secondary)" }}>Loading sign-in...</p>}>
        <SignIn />
      </Suspense>
    </main>
  );
}
