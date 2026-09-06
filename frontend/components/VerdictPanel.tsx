"use client";

import { useState } from "react";
import { Gavel, Loader2, ScrollText } from "lucide-react";
import {
  useChallenge,
  useResolveChallenge,
} from "@/lib/hooks/useMandateGuard";
import type { Action } from "@/lib/contracts/types";
import { success, error } from "@/lib/utils/toast";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";

function formatWei(wei: number | string): string {
  return (Number(wei) / 1e18).toLocaleString(undefined, { maximumFractionDigits: 4 });
}

const PAYOUT_LABELS: Record<string, string> = {
  bond_slashed_to_principal: "Bond slashed → principal",
  deposit_returned_to_challenger: "Deposit returned → challenger",
  deposit_forfeited_to_operator: "Deposit forfeited → operator",
  bond_already_slashed_not_paid:
    "Bond already slashed — nothing further to pay (the bond leg was skipped)",
};

/**
 * Surface 3 — verdict view: the structured verdict and the resulting payouts.
 * Shows what the contract recorded (D12), including FIX-1's already-slashed
 * case: if the bond was gone, it says so instead of showing a phantom slash.
 */
export function VerdictPanel({
  challengeId,
  action,
}: {
  challengeId: string | null;
  action: Action;
}) {
  const { data: challenge, isLoading } = useChallenge(challengeId);
  const resolveChallenge = useResolveChallenge();

  async function handleResolve() {
    if (!challengeId) {
      return;
    }
    try {
      await resolveChallenge.mutateAsync({ challengeId });
      success(
        "Resolution finalized intent recorded",
        { description: "Validators fetched the live listing and adjudicated. Payouts execute on finalization." }
      );
    } catch (e: any) {
      error("Resolution failed", e?.message ?? String(e));
    }
  }

  return (
    <div className="rounded-lg bg-muted/40 p-4 space-y-3">
      <div className="flex items-center gap-2 font-semibold">
        <ScrollText className="h-4 w-4" />
        Verdict
      </div>

      {challengeId === null && (
        <p className="text-sm text-muted-foreground">
          No challenge was opened on this action.
        </p>
      )}

      {challengeId !== null && isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading challenge…
        </div>
      )}

      {challengeId !== null && challenge && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {challenge.state === "OPEN" && (
              <>
                <Badge className="bg-amber-500 text-black">Awaiting resolution</Badge>
                <Button
                  size="sm"
                  onClick={handleResolve}
                  disabled={resolveChallenge.isPending}
                >
                  {resolveChallenge.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Validators adjudicating…
                    </>
                  ) : (
                    <>
                      <Gavel className="mr-2 h-4 w-4" />
                      Resolve (validators fetch the live listing)
                    </>
                  )}
                </Button>
              </>
            )}
            {challenge.state === "RESOLVED_UPHELD" && (
              <Badge className="bg-red-600 text-white">
                Challenge upheld — out of mandate
              </Badge>
            )}
            {challenge.state === "RESOLVED_REJECTED" && (
              <Badge className="bg-green-600 text-white">
                Challenge rejected — within mandate
              </Badge>
            )}
          </div>

          {challenge.state !== "OPEN" && (
            <div className="space-y-2 text-sm">
              <div className="grid grid-cols-[180px_1fr] gap-1 items-start">
                <span className="text-muted-foreground">Within mandate:</span>
                <span
                  className={
                    "font-bold " +
                    (challenge.verdict_within_mandate ? "text-green-500" : "text-red-500")
                  }
                >
                  {String(challenge.verdict_within_mandate)}
                </span>
                <span className="text-muted-foreground">Clause violated:</span>
                <span className="font-mono text-xs break-all">
                  {challenge.verdict_clause_violated || "—"}
                </span>
                <span className="text-muted-foreground">Severity:</span>
                <span>{Number(challenge.verdict_severity)} / 100</span>
                <span className="text-muted-foreground">Reasoning:</span>
                <span className="italic">{challenge.verdict_reasoning}</span>
              </div>
              <div className="border-t border-border" />
              <div>
                <div className="text-muted-foreground mb-1">Recorded payouts:</div>
                {challenge.payouts.length === 0 ? (
                  <p className="text-muted-foreground">None recorded.</p>
                ) : (
                  <ul className="space-y-1">
                    {challenge.payouts.map((p, i) => (
                      <li key={i} className="text-sm">
                        {PAYOUT_LABELS[p.purpose] ?? p.purpose} —{" "}
                        <span className="font-medium">{formatWei(p.amount_wei)} GEN</span>
                        <span className="text-xs text-muted-foreground break-all">
                          {" "}
                          to {p.recipient}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="text-xs text-muted-foreground mt-1">
                  Payouts execute on finalization, not instantly.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
