import { SignIn } from "@clerk/nextjs";
import { HeirloomLogo } from "@/components/HeirloomLogo";

export default function Page() {
  return (
    <main className="kb-page">
      <div className="kb-logo">
        <HeirloomLogo size={30} />
      </div>
      <SignIn />
    </main>
  );
}
