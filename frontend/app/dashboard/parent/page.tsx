import { RoleGuard } from "@/components/RoleGuard";
import { DashboardShell, DashboardCard } from "@/components/DashboardShell";

export default function ParentDashboard() {
  return (
    <RoleGuard expected="parent">
      <DashboardShell roleLabel="Parent">
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
      </DashboardShell>
    </RoleGuard>
  );
}
