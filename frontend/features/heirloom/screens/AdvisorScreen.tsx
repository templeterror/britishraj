"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import FamilyHeader from "@/features/heirloom/components/FamilyHeader";
import FlagFeed from "@/features/heirloom/components/FlagFeed";
import FlagSheet from "@/features/heirloom/components/FlagSheet";
import { EmptyState, ErrorState, LoadingState } from "@/features/heirloom/components/StateViews";
import { firstName } from "@/features/heirloom/format";
import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import { useRevisionPoll } from "@/features/heirloom/hooks/useRevisionPoll";
import { useSession } from "@/features/heirloom/hooks/useSession";
import type { AdvisorSnapshot, InsightDTO } from "@/features/heirloom/types/contracts";
import styles from "./AdvisorScreen.module.css";

interface OpenFlag {
  id: string;
  key: string;
}

/**
 * Flag feed plus the side sheet for the selected flag. The sheet follows its insight across
 * recomputes (a new row with the same insight_key) and closes when the insight is gone, e.g.
 * after the heir withdraws consent and the next revision poll returns no insights.
 */
export function AdvisorFlags({
  familyId,
  snapshot,
  insights,
  onChanged,
}: {
  familyId: string;
  snapshot: AdvisorSnapshot;
  insights: InsightDTO[];
  onChanged: () => void;
}) {
  const [open, setOpen] = useState<OpenFlag | null>(null);
  const selected = open
    ? (insights.find((i) => i.id === open.id) ?? insights.find((i) => i.insight_key === open.key))
    : undefined;
  if (open && !selected) setOpen(null);

  const select = useCallback(
    (id: string) => {
      const insight = insights.find((i) => i.id === id);
      if (insight) setOpen({ id: insight.id, key: insight.insight_key });
    },
    [insights],
  );
  const close = useCallback(() => setOpen(null), []);
  const heir = snapshot.people.find((p) => p.role === "adult_heir");

  return (
    <>
      <FlagFeed
        insights={insights}
        goalSharing={snapshot.goal_sharing}
        heirName={firstName(heir?.display_name, "The family member")}
        onSelect={select}
      />
      {selected ? (
        <FlagSheet
          key={selected.insight_key}
          familyId={familyId}
          snapshot={snapshot}
          insight={selected}
          onClose={close}
          onChanged={onChanged}
        />
      ) : null}
    </>
  );
}

export default function AdvisorScreen() {
  const session = useSession();
  const familyId = session?.familyId ?? null;
  const snapshot = useRelayQuery<AdvisorSnapshot>(familyId ? `/families/${familyId}/snapshot` : null);
  const insights = useRelayQuery<InsightDTO[]>(familyId ? `/families/${familyId}/insights` : null);
  const { reload: reloadSnapshot } = snapshot;
  const { reload: reloadInsights } = insights;
  const reloadAll = useCallback(() => {
    reloadSnapshot();
    reloadInsights();
  }, [reloadSnapshot, reloadInsights]);
  useRevisionPoll(familyId, reloadAll);

  if (!session || !familyId) {
    return (
      <main className={styles.main}>
        <EmptyState title="No persona selected" body="Choose a demo persona to open the advisor view." />
        <Link href="/relay" className={styles.link}>
          Choose a persona
        </Link>
      </main>
    );
  }

  const error = snapshot.error ?? insights.error;
  return (
    <main className={styles.main}>
      {error && (!snapshot.data || !insights.data) ? (
        <ErrorState error={error} onRetry={reloadAll} />
      ) : !snapshot.data || !insights.data ? (
        <LoadingState label="Loading family" />
      ) : (
        <>
          <FamilyHeader snapshot={snapshot.data} />
          <AdvisorFlags familyId={familyId} snapshot={snapshot.data} insights={insights.data} onChanged={reloadAll} />
        </>
      )}
    </main>
  );
}
