"use client";

import { useState } from "react";
import { Navbar } from "@/components/Navbar";
import { MandateEditor } from "@/components/MandateEditor";
import { ActionFeed } from "@/components/ActionFeed";
import { useMandates } from "@/lib/hooks/useMandateGuard";

export default function HomePage() {
  const { data: mandates } = useMandates();
  const [selectedMandateId, setSelectedMandateId] = useState<string | null>(null);

  const activeMandateId = selectedMandateId ?? mandates?.[0]?.id ?? null;
  const activeMandate = mandates?.find((m) => m.id === activeMandateId);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-grow pt-20 pb-12 px-4 md:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto space-y-8">
          <div className="text-center mb-2">
            <h1 className="text-4xl md:text-5xl font-bold mb-3">Mandate Guard</h1>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              An agent posts a bond and acts on your behalf. Anyone can challenge
              an action inside the window; validators fetch the live listing and
              judge the mandate.
            </p>
          </div>

          {/* Surface 1 — mandate editor */}
          <MandateEditor />

          {/* Mandate picker for the feed */}
          {mandates && mandates.length > 0 && (
            <div className="brand-card p-6 space-y-3">
              <div>
                <h2 className="text-xl font-semibold">Mandates</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Registered by the connected operator. Verify the stored text
                  matches what the principal asked for before letting the agent act.
                </p>
              </div>
                <select
                  value={activeMandateId ?? ""}
                  onChange={(e) => setSelectedMandateId(e.target.value || null)}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  {mandates.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.id} — bond intact: {m.bond_intact ? "yes" : "NO"} —{" "}
                      {m.text.slice(0, 60)}…
                    </option>
                  ))}
                </select>
                {activeMandate && (
                  <div className="space-y-1 text-sm">
                    <p className="font-medium">Registered mandate text:</p>
                    <p className="italic border-l-2 border-border pl-3">
                      {activeMandate.text}
                    </p>
                  </div>
                )}
            </div>
          )}

          {/* Surfaces 2 + 3 — action feed with challenge and verdict view */}
          <ActionFeed mandateId={activeMandateId} />
        </div>
      </main>
    </div>
  );
}
