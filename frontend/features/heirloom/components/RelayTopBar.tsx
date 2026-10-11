"use client";

import Link from "next/link";
import { useRelayQuery } from "@/features/heirloom/hooks/useRelayQuery";
import { useSession } from "@/features/heirloom/hooks/useSession";
import ModeBadge from "./ModeBadge";
import styles from "./RelayTopBar.module.css";

const ROLE_LABEL = { advisor: "Advisor", parent: "Client", adult_heir: "Family member" } as const;

export default function RelayTopBar() {
  const session = useSession();
  const health = useRelayQuery<{ status: string }>("/health");

  return (
    <header className={styles.bar}>
      <span className={styles.brand}>
        <span className={styles.mark} aria-hidden="true">
          <svg viewBox="0 0 20 20" width="16" height="16">
            <path d="M4 14.5 10 4.5l6 10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
          </svg>
        </span>
        Heirloom Relay
      </span>
      <div className={styles.utilities}>
        {session ? (
          <span className={styles.persona}>
            {session.person.displayName} · {ROLE_LABEL[session.person.role]}
          </span>
        ) : null}
        <Link href="/relay" className={styles.switch}>
          Switch persona
        </Link>
        <ModeBadge mode={health.meta?.mode} />
      </div>
    </header>
  );
}
