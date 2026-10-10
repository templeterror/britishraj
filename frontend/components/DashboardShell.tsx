"use client";

import { UserButton, OrganizationSwitcher } from "@clerk/nextjs";
import { HeirloomLogo } from "@/components/HeirloomLogo";
import type { ReactNode } from "react";

type RoleTint = "parent" | "child" | "wealth_manager";

const ROLE_ACCENT: Record<RoleTint, string> = {
  parent: "var(--role-parent)",
  child: "var(--role-child)",
  wealth_manager: "var(--role-wealth-manager)",
};

export function DashboardShell({
  roleLabel,
  roleTint = "parent",
  children,
}: {
  roleLabel: string;
  roleTint?: RoleTint;
  children: ReactNode;
}) {
  const accent = ROLE_ACCENT[roleTint];
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
          <span className="kb-badge" style={{ color: accent, borderColor: accent }}>
            {roleLabel}
          </span>
          {roleTint === "wealth_manager" && (
            <OrganizationSwitcher
              hidePersonal
              appearance={{
                elements: {
                  organizationSwitcherTrigger: {
                    color: "var(--text-primary)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-control)",
                    padding: "6px 10px",
                  },
                },
              }}
            />
          )}
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
      <h2 style={{ marginTop: 0, fontSize: "16px", fontWeight: 600, color: "var(--text-primary)" }}>{title}</h2>
      <div style={{ color: "var(--text-secondary)", fontSize: "14px", lineHeight: 1.5 }}>{children}</div>
    </div>
  );
}
