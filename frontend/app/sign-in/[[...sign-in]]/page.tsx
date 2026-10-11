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
      <SignIn />
    </main>
  );
}
