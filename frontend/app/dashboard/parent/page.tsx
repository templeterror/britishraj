import { RoleGuard } from "@/components/RoleGuard";
import { DashboardShell } from "@/components/DashboardShell";
import { ParentDashboard } from "@/components/dashboards/ParentDashboard";

export default function ParentDashboardPage() {
  return (
    <RoleGuard expected="parent">
      <DashboardShell roleLabel="Parent" roleTint="parent">
        <ParentDashboard />
      </DashboardShell>
    </RoleGuard>
  );
}
