import { EmptyState } from "@/features/heirloom/components/StateViews";

// Placeholder until the advisor screen (Tasks 12-13) replaces it.
export default function AdvisorPage() {
  return (
    <main style={{ padding: "var(--hr-space-5) var(--hr-space-4)" }}>
      <EmptyState title="Advisor view" body="Flags, the knowledge graph and review tabs arrive with the advisor screen." />
    </main>
  );
}
