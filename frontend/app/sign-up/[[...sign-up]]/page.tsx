import { SignUp } from "@clerk/nextjs";
import Image from "next/image";

export default function Page() {
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
      <SignUp />
    </main>
  );
}
