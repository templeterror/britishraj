import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";
import "./globals.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});

// Display serif, used only for the wordmark and page-level headings — see
// design-system/HEIRLOOM-DESIGN-SYSTEM.md. Never for body copy or UI chrome.
const heirloomSerif = Source_Serif_4({
  subsets: ["latin"],
  weight: ["500", "600"],
  variable: "--font-heirloom-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Heirloom",
  description: "Heirloom — keep your family aligned across generations of wealth",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <ClerkProvider
      signInUrl={process.env.NEXT_PUBLIC_CLERK_SIGN_IN_URL}
      signUpUrl={process.env.NEXT_PUBLIC_CLERK_SIGN_UP_URL}
      signInFallbackRedirectUrl={process.env.NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL}
      signUpFallbackRedirectUrl={process.env.NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL}
      appearance={{
        variables: {
          colorPrimary: "#1f5a45",
          colorPrimaryForeground: "#f3f4f0",
          colorBackground: "#ffffff",
          colorForeground: "#1c1d1a",
          colorMutedForeground: "#686a5f",
          colorNeutral: "#1c1d1a",
          colorInput: "#fafaf7",
          colorInputForeground: "#1c1d1a",
          colorBorder: "#dcded5",
          colorDanger: "#9e3f2e",
          colorSuccess: "#3c7a5a",
          colorWarning: "#b8863a",
          borderRadius: "4px",
          fontFamily: "var(--font-plex-sans)",
        },
      }}
    >
      <html lang="en" className={`${plexSans.variable} ${heirloomSerif.variable}`}>
        <body>{children}</body>
      </html>
    </ClerkProvider>
  );
}
