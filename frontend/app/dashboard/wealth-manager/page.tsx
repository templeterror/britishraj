import { RoleGuard } from "@/components/RoleGuard";
import { DashboardShell } from "@/components/DashboardShell";
import { WealthManagerDashboard } from "@/components/dashboards/WealthManagerDashboard";

export default function WealthManagerDashboardPage() {
  return (
    <RoleGuard expected="wealth_manager">
      <DashboardShell roleLabel="Wealth Manager" roleTint="wealth_manager">
        <WealthManagerDashboard />
      </DashboardShell>
    </RoleGuard>
  );
}
