"use client";

import { useId } from "react";
import type { InvitationView } from "@/features/heirloom/types/contracts";
import styles from "./InvitationCard.module.css";

/** An invitation the advisor drafted and approved for this family member. Nothing is sent from here. */
export default function InvitationCard({ invitation }: { invitation: InvitationView }) {
  const titleId = useId();
  return (
    <section className={styles.card} aria-labelledby={titleId}>
      <h2 id={titleId} className={styles.title}>
        An invitation from {invitation.from_display}
      </h2>
      <p className={styles.text}>{invitation.text}</p>
    </section>
  );
}
