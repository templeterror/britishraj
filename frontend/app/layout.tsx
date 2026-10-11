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
        options: {
          // Social sign-in buttons ("Continue with Google" etc.) render below
          // the email/password form instead of above it.
          socialButtonsPlacement: "bottom",
        },
        variables: {
          colorPrimary: "#1f5a45",
          colorPrimaryForeground: "#f3f4f0",
          // Translucent so the ambient background shows through the Clerk
          // card the same way our own .kb-card does. --glass-bg = 55% white.
          colorBackground: "rgba(255, 255, 255, 0.55)",
          colorForeground: "#1c1d1a",
          colorMutedForeground: "#686a5f",
          colorNeutral: "#1c1d1a",
          colorInput: "rgba(255, 255, 255, 0.6)",
          colorInputForeground: "#1c1d1a",
          colorBorder: "rgba(28, 29, 26, 0.06)",
          colorDanger: "#9e3f2e",
          colorSuccess: "#3c7a5a",
          colorWarning: "#b8863a",
          borderRadius: "14px",
          fontFamily: "var(--font-plex-sans)",
        },
        elements: {
          // Make the Clerk card itself behave like .kb-card: blur the
          // ambient background behind it and carry the same specular edge
          // + soft outer shadow.
          card: {
            backdropFilter: "blur(28px) saturate(180%)",
            WebkitBackdropFilter: "blur(28px) saturate(180%)",
            boxShadow:
              "inset 0 1px 0 rgba(255, 255, 255, 0.6), inset 0 0 0 1px rgba(28, 29, 26, 0.06), 0 10px 40px rgba(28, 29, 26, 0.08), 0 2px 6px rgba(28, 29, 26, 0.04)",
            border: 0,
          },
        },
      }}
    >
      <html lang="en" className={`${plexSans.variable} ${heirloomSerif.variable}`}>
        <body>{children}</body>
      </html>
    </ClerkProvider>
  );
}
