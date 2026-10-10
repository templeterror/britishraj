"use client";

import { UserButton } from "@clerk/nextjs";
import { HeirloomLogo } from "@/components/HeirloomLogo";
import type { ReactNode } from "react";

export function DashboardShell({
  roleLabel,
  children,
}: {
  roleLabel: string;
  children: ReactNode;
}) {
  return (
    <div style={{ minHeight: "100vh", padding: "1.5rem 2rem", maxWidth: 1100, margin: "0 auto" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "2rem",
        }}
      >
        <HeirloomLogo size={24} />
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span
            style={{
              fontSize: "0.8rem",
              color: "#00dd94",
              border: "1px solid #262626",
              borderRadius: "999px",
              padding: "0.25rem 0.75rem",
            }}
          >
            {roleLabel}
          </span>
          <UserButton />
        </div>
      </header>
      {children}
    </div>
  );
}

export function DashboardCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="kb-card" style={{ marginBottom: "1rem" }}>
      <h2 style={{ marginTop: 0, fontSize: "1.1rem", color: "#00dd94" }}>{title}</h2>
      <div style={{ color: "#d4d4d4", fontSize: "0.92rem", lineHeight: 1.5 }}>{children}</div>
    </div>
  );
}
