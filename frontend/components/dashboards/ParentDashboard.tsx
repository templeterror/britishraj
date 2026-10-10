// ============================================================================
// PARENT DASHBOARD — this is the file to build out.
//
// Routing, auth, and the role check already happen in
// app/dashboard/parent/page.tsx and components/RoleGuard.tsx — you don't
// need to touch either of those. Just build the UI below.
//
// Per the PRD, the Parent dashboard needs:
//   - Portfolio Overview: assets, investments, transactions, performance
//   - Financial Goals: estate planning intentions, long-term family objectives
//   - Decision History: past investment decisions + advisor meeting summaries
//   - Goal Alignment: how current decisions support heirs' stated goals
//
// `DashboardCard` below is just a simple placeholder wrapper (see
// components/DashboardShell.tsx) — swap it for real layout/charts/tables
// whenever you're ready. The page already renders inside the shared
// <DashboardShell> (logo + role badge + sign-out in the header), so this
// component only needs to return the page's main content.
// ============================================================================

import { DashboardCard } from "@/components/DashboardShell";

export function ParentDashboard() {
  return (
    <>
      <DashboardCard title="Portfolio Overview">
        Assets, investments, transactions, and performance go here.
      </DashboardCard>
      <DashboardCard title="Financial Goals">
        Define your estate planning intentions and long-term family objectives.
      </DashboardCard>
      <DashboardCard title="Decision History">
        Your past investment decisions and advisor meeting summaries.
      </DashboardCard>
      <DashboardCard title="Goal Alignment">
        How your current financial decisions support your heirs&apos; stated goals.
      </DashboardCard>
    </>
  );
}
