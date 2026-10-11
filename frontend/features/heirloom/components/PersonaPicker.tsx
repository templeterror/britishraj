"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import relay, { RELAY_BASE_URL, RelayApiError, createRelayClient } from "@/features/heirloom/api/client";
import { ErrorState } from "@/features/heirloom/components/StateViews";
import { getSession, setSession, clearSession } from "@/features/heirloom/session";
import type { DemoPersona, DemoSessionDTO, FamilyRole } from "@/features/heirloom/types/contracts";
import styles from "./PersonaPicker.module.css";

const PERSONAS: Array<{ persona: DemoPersona; name: string; roleLabel: string; blurb: string }> = [
  { persona: "sarah", name: "Sarah Lin", roleLabel: "Lead advisor", blurb: "Reviews flags, verifies records, drafts actions." },
  { persona: "robert", name: "Robert Morgan", roleLabel: "Client", blurb: "Decides which explanations the family may see." },
  { persona: "james", name: "James Morgan", roleLabel: "Adult family member", blurb: "Keeps goals private and chooses what to share." },
];

const ROUTE_BY_ROLE: Record<FamilyRole, string> = {
  advisor: "/relay/advisor",
  parent: "/relay/parent",
  adult_heir: "/relay/heir",
};

async function mintSarahToken(): Promise<string> {
  return (await relay.post<DemoSessionDTO>("/demo/sessions", { persona: "sarah" })).data.token;
}

async function postReset(token: string): Promise<void> {
  await createRelayClient({ baseUrl: RELAY_BASE_URL, getToken: () => token, onUnauthenticated: () => clearSession() }).post(
    "/demo/reset",
  );
}

export default function PersonaPicker() {
  const router = useRouter();
  const [busy, setBusy] = useState<DemoPersona | "reset" | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const retryRef = useRef<() => void>(() => {});

  async function choose(persona: DemoPersona) {
    retryRef.current = () => void choose(persona);
    setBusy(persona);
    setError(null);
    setNotice(null);
    try {
      const { data } = await relay.post<DemoSessionDTO>("/demo/sessions", { persona });
      setSession({
        token: data.token,
        familyId: data.family_id,
        person: { id: data.person.id, displayName: data.person.display_name, role: data.person.role },
      });
      router.push(ROUTE_BY_ROLE[data.person.role]);
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Request failed"));
    } finally {
      // Always clear busy, even on the success path. The component usually
      // unmounts on navigation, but when the user returns via "Switch
      // persona" it can re-use this state — leaving busy set would keep
      // every card and the Reset button disabled (cursor: not-allowed).
      setBusy(null);
    }
  }

  async function resetDemo() {
    retryRef.current = () => void resetDemo();
    setBusy("reset");
    setError(null);
    setNotice(null);
    try {
      // /demo/reset needs any demo token. A stored token may be stale (backend restarted, expired):
      // a 401 clears the session and we retry once with a freshly minted Sarah token.
      const stored = getSession()?.token ?? null;
      if (stored) {
        try {
          await postReset(stored);
        } catch (e) {
          if (!(e instanceof RelayApiError && e.status === 401)) throw e;
          await postReset(await mintSarahToken());
        }
      } else {
        await postReset(await mintSarahToken());
      }
      clearSession();
      setNotice("Demo data reset.");
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Request failed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className={styles.page}>
      <p className={styles.banner}>Synthetic Morgan family · demo mode · no real client data</p>
      <h1 className={styles.heading}>Choose a persona</h1>
      <p className={styles.lede}>Each persona sees only what the server allows for that role.</p>

      <div className={styles.grid}>
        {PERSONAS.map((p) => (
          <button
            key={p.persona}
            type="button"
            className={styles.card}
            disabled={busy !== null}
            onClick={() => void choose(p.persona)}
          >
            <span className={styles.name}>{p.name}</span>
            <span className={styles.role}>{p.roleLabel}</span>
            <span className={styles.blurb}>{p.blurb}</span>
          </button>
        ))}
      </div>

      {error ? <ErrorState error={error} onRetry={() => retryRef.current()} /> : null}

      <div className={styles.footer}>
        <button type="button" className={styles.reset} disabled={busy !== null} onClick={() => void resetDemo()}>
          Reset demo
        </button>
        {notice ? (
          <span className={styles.notice} role="status">
            {notice}
          </span>
        ) : null}
      </div>
    </main>
  );
}
