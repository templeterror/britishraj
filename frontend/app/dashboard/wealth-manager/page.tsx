import { RoleGuard } from "@/components/RoleGuard";
import { DashboardShell, DashboardCard } from "@/components/DashboardShell";

export default function WealthManagerDashboard() {
  return (
    <RoleGuard expected="wealth_manager">
      <DashboardShell roleLabel="Wealth Manager">
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
      </DashboardShell>
    </RoleGuard>
  );
}
