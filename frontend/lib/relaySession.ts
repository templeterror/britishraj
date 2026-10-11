import { setSession as setRelaySession, getSession as getRelaySession } from "@/features/heirloom/session";
import type { DemoPersona, DemoSessionDTO, Envelope } from "@/features/heirloom/types/contracts";
import type { HeirloomRole } from "@/lib/useRole";

// Our Heirloom role (stored in Supabase) → the Relay demo persona (minted
// by teammate SpurtiNimbali's backend). The relay system was built as a
// standalone persona-picker demo; we skip her PersonaPicker and mint the
// matching persona automatically once a Clerk-authed user has chosen their
// role in /select-role, so the two systems feel like one flow.
export const ROLE_TO_PERSONA: Record<HeirloomRole, DemoPersona> = {
  wealth_manager: "sarah",
  child: "james",
  parent: "robert",
};

const RELAY_BASE_URL =
  `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1`;

export class RelayMintError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "RelayMintError";
    this.status = status;
  }
}

/**
 * Hit the Relay backend to mint a demo-session token for the given persona,
 * then stash the session in sessionStorage via her setSession helper so the
 * screens at /relay/* can read it.
 */
export async function mintRelaySession(role: HeirloomRole): Promise<void> {
  const persona = ROLE_TO_PERSONA[role];
  let res: Response;
  try {
    res = await fetch(`${RELAY_BASE_URL}/demo/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ persona }),
      cache: "no-store",
    });
  } catch (cause) {
    throw new RelayMintError(0, cause instanceof Error ? cause.message : "Network error");
  }
  if (!res.ok) {
    throw new RelayMintError(res.status, `Relay backend returned ${res.status}`);
  }
  const envelope = (await res.json()) as Envelope<DemoSessionDTO>;
  const data = envelope.data;
  setRelaySession({
    token: data.token,
    familyId: data.family_id,
    person: {
      id: data.person.id,
      displayName: data.person.display_name,
      role: data.person.role,
    },
  });
}

/**
 * Mint a Relay session only if one isn't already live in sessionStorage.
 * Call this at the top of /relay/* for returning users (sessionStorage is
 * wiped when the tab closes, so returning users need a fresh mint).
 */
export async function ensureRelaySession(role: HeirloomRole): Promise<void> {
  if (getRelaySession()) return;
  await mintRelaySession(role);
}
