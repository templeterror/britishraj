// ============================================================================
// WEALTH MANAGER DASHBOARD — this is the file to build out.
//
// Routing, auth, and the role check already happen in
// app/dashboard/wealth-manager/page.tsx and components/RoleGuard.tsx — you
// don't need to touch either of those. Just build the UI below.
//
// Per the PRD, the Wealth Manager dashboard needs:
//   - Family Portfolio Overview: managed family relationships and portfolios
//   - Knowledge Graph: connections between decisions, assets, family, goals
//   - Alignment Intelligence: AI alerts for parent/heir conflicts
//   - Meeting Management: schedule meetings, track relationship-building
//   - Relationship Health: heir engagement, unresolved conflicts, retention risk
//
// `DashboardCard` below is just a simple placeholder wrapper (see
// components/DashboardShell.tsx) — swap it for real layout/charts/tables
// whenever you're ready. The page already renders inside the shared
// <DashboardShell> (logo + role badge + sign-out in the header), so this
// component only needs to return the page's main content.
//
// Two org roles exist for wealth-manager-side firm members, set up in Clerk
// (Dashboard -> Organizations -> Roles & Permissions):
//   - org:admin   — full firm admin, can edit firm settings/billing/members
//                   (built-in org:sys_profile:manage permission) and manage
//                   client families (custom org:families:manage permission)
//   - org:advisor — firm staff, can manage client families
//                   (org:families:manage) but not firm settings
// Use <PermissionGate permission="..."> (components/PermissionGate.tsx) to
// show/hide UI based on these, rather than hardcoding role name checks.
// ============================================================================

import { DashboardCard } from "@/components/DashboardShell";
import { PermissionGate } from "@/components/PermissionGate";
import Link from "next/link";

export function WealthManagerDashboard() {
  return (
    <>
      <DashboardCard title="Family Portfolio Overview">
        The family relationships and portfolios you manage.{" "}
        <PermissionGate
          permission="org:families:manage"
          fallback={<span style={{ color: "var(--text-tertiary)" }}>(read-only access)</span>}
        >
          <span style={{ color: "var(--text-tertiary)" }}>(you can manage client families)</span>
        </PermissionGate>
        <br />
        <PermissionGate permission="org:sys_profile:manage">
          <Link href="/dashboard/wealth-manager/firm" style={{ color: "var(--accent)" }}>
            Manage your firm & invite families &rarr;
          </Link>
        </PermissionGate>
      </DashboardCard>
      <DashboardCard title="Knowledge Graph">
        Explore connections between decisions, assets, family members, and goals.
      </DashboardCard>
      <DashboardCard title="Alignment Intelligence">
        AI-generated alerts for conflicts between parent decisions and heir goals.
      </DashboardCard>
      <DashboardCard title="Meeting Management">
        Schedule meetings and track relationship-building activities.
      </DashboardCard>
      <DashboardCard title="Relationship Health">
        Heir engagement, unresolved conflicts, and retention risk indicators.
      </DashboardCard>
    </>
  );
}
