"use client";

// Thin wrapper around Clerk's <Show> for organization permission checks.
// Pass any permission key from Dashboard -> Organizations -> Roles &
// Permissions, custom (e.g. "org:families:manage") or built-in system
// permissions (e.g. "org:sys_profile:manage", granted to org:admin by
// default). Renders `children` only if the active member has that
// permission on the active organization; otherwise renders `fallback`.
import { Show } from "@clerk/nextjs";
import type { ReactNode } from "react";

export function PermissionGate({
  permission,
  fallback = null,
  children,
}: {
  permission: string;
  fallback?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Show when={{ permission }} fallback={fallback}>
      {children}
    </Show>
  );
}
