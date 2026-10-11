import type { Metadata } from "next";
import { Inter } from "next/font/google";
import RelayTopBar from "@/features/heirloom/components/RelayTopBar";
import tokens from "@/features/heirloom/styles/tokens.module.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = { title: "Heirloom Relay" };

// TEMPORARY chrome for the /relay namespace; teammate A's shells will host the screens.
export default function RelayLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`${inter.variable} ${tokens.scope}`}>
      <RelayTopBar />
      {children}
    </div>
  );
}
