import { RoleGuard } from "@/components/RoleGuard";
import { DashboardShell, DashboardCard } from "@/components/DashboardShell";

export default function ChildDashboard() {
  return (
    <RoleGuard expected="child">
      <DashboardShell roleLabel="Child / Heir">
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
      </DashboardShell>
    </RoleGuard>
  );
}
