"use client";

import Link from "next/link";
import { useCallback, useId, useRef, useState, type KeyboardEvent } from "react";
import ActivityLog from "@/features/heirloom/components/ActivityLog";
import DecisionReview from "@/features/heirloom/components/DecisionReview";
import FamilyGraph from "@/features/heirloom/components/FamilyGraph";
import FamilyHeader from "@/features/heirloom/components/FamilyHeader";
import FamilyPermissions from "@/features/heirloom/components/FamilyPermissions";
import FlagFeed from "@/features/heirloom/components/FlagFeed";
import FlagSheet from "@/features/heirloom/components/FlagSheet";
import IntentReview from "@/features/heirloom/components/IntentReview";
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

const TABS = [
  { id: "flags", label: "Flags" },
  { id: "graph", label: "Knowledge graph" },
  { id: "intents", label: "Estate intents" },
  { id: "decisions", label: "Decision memory" },
  { id: "permissions", label: "Family permissions" },
  { id: "activity", label: "Activity" },
] as const;

type TabId = (typeof TABS)[number]["id"];

/**
 * The advisor's working views of one family. `refreshKey` changes whenever the screen refetches
 * (a write here, or a revision poll that saw a change), so the graph, activity and the family
 * member's preview refetch too.
 */
export function AdvisorTabs({
  familyId,
  snapshot,
  insights,
  refreshKey,
  onChanged,
}: {
  familyId: string;
  snapshot: AdvisorSnapshot;
  insights: InsightDTO[];
  refreshKey: number;
  onChanged: () => void;
}) {
  const baseId = useId();
  const [tab, setTab] = useState<TabId>("flags");
  const tabRefs = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({});

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) return;
    e.preventDefault();
    const i = TABS.findIndex((t) => t.id === tab);
    const next = TABS[(i + step + TABS.length) % TABS.length].id;
    setTab(next);
    tabRefs.current[next]?.focus();
  }

  return (
    <>
      <div role="tablist" aria-label="Advisor views" className={styles.tabs} onKeyDown={onKeyDown}>
        {TABS.map((t) => (
          <button
            key={t.id}
            ref={(el) => {
              tabRefs.current[t.id] = el;
            }}
            type="button"
            role="tab"
            id={`${baseId}-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`${baseId}-panel`}
            tabIndex={tab === t.id ? 0 : -1}
            className={styles.tab}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${baseId}-panel`} aria-labelledby={`${baseId}-tab-${tab}`} className={styles.panel}>
        {tab === "flags" ? (
          <AdvisorFlags familyId={familyId} snapshot={snapshot} insights={insights} onChanged={onChanged} />
        ) : tab === "graph" ? (
          <FamilyGraph familyId={familyId} assets={snapshot.assets} refreshKey={refreshKey} onChanged={onChanged} />
        ) : tab === "intents" ? (
          <IntentReview snapshot={snapshot} onChanged={onChanged} />
        ) : tab === "decisions" ? (
          <DecisionReview snapshot={snapshot} onChanged={onChanged} />
        ) : tab === "permissions" ? (
          <FamilyPermissions familyId={familyId} snapshot={snapshot} refreshKey={refreshKey} onChanged={onChanged} />
        ) : (
          <ActivityLog familyId={familyId} refreshKey={refreshKey} />
        )}
      </div>
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
  const [refreshKey, setRefreshKey] = useState(0);
  const reloadAll = useCallback(() => {
    reloadSnapshot();
    reloadInsights();
    setRefreshKey((n) => n + 1);
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
          <AdvisorTabs
            familyId={familyId}
            snapshot={snapshot.data}
            insights={insights.data}
            refreshKey={refreshKey}
            onChanged={reloadAll}
          />
        </>
      )}
    </main>
  );
}
