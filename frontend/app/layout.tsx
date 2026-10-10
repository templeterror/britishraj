import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { dark } from "@clerk/themes";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
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
        baseTheme: dark,
        variables: {
          colorPrimary: "#00dd94",
          colorPrimaryForeground: "#042016",
          colorBackground: "#13171f",
          colorForeground: "#f2f5f7",
          colorMutedForeground: "#9aa4b2",
          colorNeutral: "#f2f5f7",
          colorInput: "#1b2029",
          colorInputForeground: "#f2f5f7",
          colorBorder: "#242a35",
          colorDanger: "#ef4444",
          colorSuccess: "#22c55e",
          colorWarning: "#f5a623",
          borderRadius: "8px",
          fontFamily: "var(--font-plex-sans)",
        },
      }}
    >
      <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
        <body>{children}</body>
      </html>
    </ClerkProvider>
  );
}
