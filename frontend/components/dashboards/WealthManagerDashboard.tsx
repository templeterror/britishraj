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
// ============================================================================

import { DashboardCard } from "@/components/DashboardShell";

export function WealthManagerDashboard() {
  return (
    <>
      <DashboardCard title="Family Portfolio Overview">
        The family relationships and portfolios you manage.
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
