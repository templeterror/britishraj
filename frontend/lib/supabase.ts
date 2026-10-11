import { createClient } from "@supabase/supabase-js";

// Minimal shape both the client-side (useSession) and server-side (auth())
// Clerk session objects satisfy, so this helper works in either context.
type TokenSource = { getToken: () => Promise<string | null> } | null | undefined;

// Creates a Supabase client that sends the signed-in user's Clerk session
// token with every request, so Supabase's "authenticated" role (and the row
// level security policies that check it) recognize the user. Clerk must be
// added as a third-party auth provider in the Supabase dashboard first
// (Authentication -> Sign In / Providers).
export function getSupabaseClient(clerkSession: TokenSource) {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      async accessToken() {
        return (await clerkSession?.getToken()) ?? null;
      },
    }
  );
}
