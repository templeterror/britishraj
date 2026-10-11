import { RoleGuard } from "@/components/RoleGuard";
import { DashboardShell } from "@/components/DashboardShell";
import { PermissionGate } from "@/components/PermissionGate";
import { OrganizationProfile } from "@clerk/nextjs";

export default function FirmSettingsPage() {
  return (
    <RoleGuard expected="wealth_manager">
      <DashboardShell roleLabel="Wealth Manager" roleTint="wealth_manager">
        {/* Firm settings (members, billing, org profile) are gated to the
            built-in org:sys_profile:manage permission, which only the
            org:admin role carries by default. Advisors (org:advisor) can
            manage client families but not the firm itself. */}
        <PermissionGate
          permission="org:sys_profile:manage"
          fallback={
            <div className="kb-card">
              <p style={{ color: "var(--text-secondary)" }}>
                Firm settings are limited to firm admins. Ask an admin at your firm to make
                changes here, or to grant you the Admin role.
              </p>
            </div>
          }
        >
          <div className="kb-card" style={{ padding: 0, overflow: "hidden" }}>
            <OrganizationProfile routing="hash" />
          </div>
        </PermissionGate>
      </DashboardShell>
    </RoleGuard>
  );
}
