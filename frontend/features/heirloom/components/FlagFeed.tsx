"use client";

import { useState } from "react";
import type { GoalSharingLevel, InsightDTO, InsightFilterTag } from "@/features/heirloom/types/contracts";
import FlagCard from "./FlagCard";
import { EmptyState } from "./StateViews";
import styles from "./FlagFeed.module.css";

const FILTERS: Array<{ tag: InsightFilterTag; label: string }> = [
  { tag: "needs_parent_review", label: "Needs parent review" },
  { tag: "heir_conversation", label: "Heir conversation" },
  { tag: "legal_source_conflict", label: "Legal source conflict" },
  { tag: "scenario_mismatch", label: "Scenario mismatch" },
];

export default function FlagFeed({
  insights,
  goalSharing,
  heirName,
  onSelect,
}: {
  insights: InsightDTO[];
  goalSharing: GoalSharingLevel;
  /** First name used in the not-shared empty state. */
  heirName: string;
  onSelect: (id: string) => void;
}) {
  const [filter, setFilter] = useState<InsightFilterTag | null>(null);
  const visible = filter ? insights.filter((i) => i.filter_tags.includes(filter)) : insights;

  return (
    <section className={styles.feed} aria-label="Flags">
      <div className={styles.filters} role="group" aria-label="Filter flags">
        {FILTERS.map((f) => (
          <button
            key={f.tag}
            type="button"
            className={styles.filter}
            aria-pressed={filter === f.tag}
            onClick={() => setFilter(filter === f.tag ? null : f.tag)}
          >
            {f.label}
          </button>
        ))}
      </div>
      {insights.length === 0 ? (
        goalSharing === "not_shared" ? (
          <EmptyState title="No open flags." body={`${heirName} has not shared any current goals.`} />
        ) : (
          <EmptyState title="No open flags under current assumptions." />
        )
      ) : visible.length === 0 ? (
        <EmptyState title="No flags match this filter." />
      ) : (
        <ul className={styles.list}>
          {visible.map((insight) => (
            <li key={insight.id}>
              <FlagCard insight={insight} onOpen={onSelect} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
