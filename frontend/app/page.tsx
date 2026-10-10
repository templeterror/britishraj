"use client";

import { SignedIn, SignedOut, RedirectToSignIn, UserButton, useSession } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { getSupabaseClient } from "@/lib/supabase";

type Heir = {
  heir_id: string;
  heir_name: string;
  household_name: string;
  relationship_level: string;
  dollars_at_risk: number;
  priority_score: number;
};

// Proves the Clerk -> Supabase connection by reading the heir_priority view.
// Requires 01_schema.sql and 02_seed.sql to already be applied in Supabase.
function Dashboard() {
  const { session } = useSession();
  const [heirs, setHeirs] = useState<Heir[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    const supabase = getSupabaseClient(session);
    supabase
      .from("heir_priority")
      .select("*")
      .order("priority_score", { ascending: false })
      .limit(10)
      .then(({ data, error }) => {
        if (error) setError(error.message);
        else setHeirs(data as Heir[]);
      });
  }, [session]);

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "2rem 1.5rem" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "1.5rem",
        }}
      >
        <h1>Heirloom</h1>
        <UserButton />
      </header>

      <h2>Who to meet first</h2>
      {error && <p style={{ color: "#e5484d" }}>Couldn&apos;t load heirs yet: {error}</p>}
      {!error && !heirs && <p>Loading...</p>}
      {heirs && heirs.length === 0 && (
        <p>No heirs found yet. Have you run the schema and seed SQL in Supabase?</p>
      )}
      {heirs && heirs.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={cellStyle}>Heir</th>
              <th style={cellStyle}>Household</th>
              <th style={cellStyle}>Relationship</th>
              <th style={cellStyle}>Dollars at risk</th>
              <th style={cellStyle}>Priority score</th>
            </tr>
          </thead>
          <tbody>
            {heirs.map((h) => (
              <tr key={h.heir_id}>
                <td style={cellStyle}>{h.heir_name}</td>
                <td style={cellStyle}>{h.household_name}</td>
                <td style={cellStyle}>{h.relationship_level}</td>
                <td style={cellStyle}>${Number(h.dollars_at_risk).toLocaleString()}</td>
                <td style={cellStyle}>{Number(h.priority_score).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}

const cellStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "0.5rem 0.75rem",
  borderBottom: "1px solid #333",
};

export default function Home() {
  return (
    <>
      <SignedIn>
        <Dashboard />
      </SignedIn>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
}
