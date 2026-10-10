import { RoleGuard } from "@/components/RoleGuard";
import { DashboardShell } from "@/components/DashboardShell";
import { ChildDashboard } from "@/components/dashboards/ChildDashboard";

export default function ChildDashboardPage() {
  return (
    <RoleGuard expected="child">
      <DashboardShell roleLabel="Child / Heir">
        <ChildDashboard />
      </DashboardShell>
    </RoleGuard>
  );
}
