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
          // Translucent card against the colored ambient background. 72%
          // keeps it clearly a lifted surface instead of blending into the
          // page while still letting the ambient color bleed through.
          colorBackground: "rgba(255, 255, 255, 0.72)",
          colorForeground: "#1c1d1a",
          colorMutedForeground: "#686a5f",
          colorNeutral: "#1c1d1a",
          // Inputs get real contrast against the card: soft neutral fill,
          // visible border, so they stop reading as autofill-only chrome.
          colorInput: "#fafaf6",
          colorInputForeground: "#1c1d1a",
          colorBorder: "rgba(28, 29, 26, 0.14)",
          colorDanger: "#9e3f2e",
          colorSuccess: "#3c7a5a",
          colorWarning: "#b8863a",
          borderRadius: "14px",
          fontFamily: "var(--font-plex-sans)",
        },
        elements: {
          // The Clerk card gets our full liquid-glass chrome: strong
          // backdrop blur + specular top highlight + deeper outer shadow
          // so it clearly floats above the ambient color field.
          card: {
            backdropFilter: "blur(32px) saturate(180%)",
            WebkitBackdropFilter: "blur(32px) saturate(180%)",
            boxShadow:
              "inset 0 1px 0 rgba(255, 255, 255, 0.7), inset 0 0 0 1px rgba(28, 29, 26, 0.08), 0 24px 60px rgba(28, 29, 26, 0.18), 0 4px 12px rgba(28, 29, 26, 0.08)",
            border: 0,
          },
          // Social sign-in buttons ("Continue with Google" etc.) get an
          // explicit outlined pill so they stop being invisible-on-white.
          socialButtonsBlockButton: {
            background: "#ffffff",
            border: "1px solid rgba(28, 29, 26, 0.14)",
            boxShadow: "0 1px 2px rgba(28, 29, 26, 0.05)",
            borderRadius: "999px",
            fontWeight: 500,
          },
          socialButtonsBlockButton__google: {
            background: "#ffffff",
          },
          // Form inputs: real border + a hint of ground so they lift
          // from the glass background.
          formFieldInput: {
            border: "1px solid rgba(28, 29, 26, 0.14)",
            boxShadow: "inset 0 1px 2px rgba(28, 29, 26, 0.04)",
          },
          // The Continue button carries its own soft brand shadow.
          formButtonPrimary: {
            boxShadow:
              "0 1px 0 rgba(255, 255, 255, 0.2) inset, 0 4px 12px rgba(31, 90, 69, 0.3)",
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
