// ============================================================================
// CHILD / HEIR DASHBOARD — this is the file to build out.
//
// Routing, auth, and the role check already happen in
// app/dashboard/child/page.tsx and components/RoleGuard.tsx — you don't
// need to touch either of those. Just build the UI below.
//
// Per the PRD, the Child dashboard needs:
//   - Financial Goals: submit/update personal financial goals quarterly
//   - Inheritance Readiness: plans/assets explicitly shared by the parent
//   - AI Financial Assistant: query authorized financial history in plain English
//   - Educational Insights: investment strategies and long-term wealth planning
//
// `DashboardCard` below is just a simple placeholder wrapper (see
// components/DashboardShell.tsx) — swap it for real layout/charts/tables
// whenever you're ready. The page already renders inside the shared
// <DashboardShell> (logo + role badge + sign-out in the header), so this
// component only needs to return the page's main content.
// ============================================================================

import { DashboardCard } from "@/components/DashboardShell";

export function ChildDashboard() {
  return (
    <>
      <DashboardCard title="Financial Goals">
        Submit and update your personal financial goals each quarter.
      </DashboardCard>
      <DashboardCard title="Inheritance Readiness">
        Financial plans and assets explicitly shared with you by your parent.
      </DashboardCard>
      <DashboardCard title="AI Financial Assistant">
        Ask about your family&apos;s financial history in plain English.
      </DashboardCard>
      <DashboardCard title="Educational Insights">
        Investment strategies and long-term wealth planning, explained.
      </DashboardCard>
    </>
  );
}
