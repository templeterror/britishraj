"use client";

import Link from "next/link";
import ApprovedMemory from "@/features/heirloom/components/ApprovedMemory";
import GoalCheckIn from "@/features/heirloom/components/GoalCheckIn";
import GoalSharing from "@/features/heirloom/components/GoalSharing";
import InvitationCard from "@/features/heirloom/components/InvitationCard";
import MemoryAsk from "@/features/heirloom/components/MemoryAsk";
import { EmptyState, ErrorState, LoadingState } from "@/features/heirloom/components/StateViews";
import { firstName } from "@/features/heirloom/format";
import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import { useRevisionPoll } from "@/features/heirloom/hooks/useRevisionPoll";
import { useSession } from "@/features/heirloom/hooks/useSession";
import type { HeirSnapshot } from "@/features/heirloom/types/contracts";
import styles from "./HeirScreen.module.css";

/** The adult family member's view: their own goal, what they share, and the explanations shared with them. */
export default function HeirScreen() {
  const session = useSession();
  const familyId = session?.person.role === "adult_heir" ? session.familyId : null;
  const snapshot = useRelayQuery<HeirSnapshot>(familyId ? `/families/${familyId}/snapshot` : null);
  const { reload } = snapshot;
  useRevisionPoll(familyId, reload);

  if (!session || !familyId) {
    return (
      <main className={styles.main}>
        <EmptyState
          title={session ? "This view is for family members" : "No persona selected"}
          body="Choose the family member persona to open this view."
        />
        <Link href="/relay" className={styles.link}>
          Choose a persona
        </Link>
      </main>
    );
  }

  const data = snapshot.data;
  if (!data) {
    return (
      <main className={styles.main}>
        {snapshot.error ? (
          <ErrorState error={snapshot.error} onRetry={reload} />
        ) : (
          <LoadingState label="Loading your goals" />
        )}
      </main>
    );
  }

  const goal = data.my_goals[0] ?? null;
  const advisorName = firstName(data.advisor.display_name, "your advisor");
  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.title}>Your future, on your terms.</h1>
        <p className={styles.lead}>
          {`Welcome, ${firstName(data.me.display_name, "there")}. Your goals stay yours. You choose whether ${advisorName}, your family's advisor, can help.`}
        </p>
      </header>

      {data.invitations.map((invitation, i) => (
        <InvitationCard key={`${invitation.from_display}-${i}`} invitation={invitation} />
      ))}

      <GoalCheckIn familyId={familyId} goal={goal} onSaved={reload} />
      <GoalSharing
        familyId={familyId}
        goalId={goal?.goal_id}
        advisor={data.advisor}
        sharing={data.sharing}
        onChanged={reload}
      />

      {data.planning_prompts.length > 0 ? (
        <section className={styles.section} aria-labelledby="heir-prompts-heading">
          <h2 id="heir-prompts-heading" className={styles.heading}>
            Questions to think about
          </h2>
          <ul className={styles.prompts}>
            {data.planning_prompts.slice(0, 3).map((prompt) => (
              <li key={prompt}>{prompt}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className={styles.section} aria-labelledby="heir-memory-heading">
        <h2 id="heir-memory-heading" className={styles.heading}>
          Decisions your family has explained
        </h2>
        <ApprovedMemory decisions={data.approved_decisions} />
      </section>

      <MemoryAsk familyId={familyId} />
    </main>
  );
}
