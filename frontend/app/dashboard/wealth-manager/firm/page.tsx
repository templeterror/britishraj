import { RoleGuard } from "@/components/RoleGuard";
import { DashboardShell } from "@/components/DashboardShell";
import { OrganizationProfile } from "@clerk/nextjs";

export default function FirmSettingsPage() {
  return (
    <RoleGuard expected="wealth_manager">
      <DashboardShell roleLabel="Wealth Manager" roleTint="wealth_manager">
        <div className="kb-card" style={{ padding: 0, overflow: "hidden" }}>
          <OrganizationProfile routing="hash" />
        </div>
      </DashboardShell>
    </RoleGuard>
  );
}
