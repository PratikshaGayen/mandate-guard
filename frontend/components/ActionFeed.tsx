"use client";

import { useState } from "react";
import { Activity, ExternalLink, Gavel, Loader2, Clock } from "lucide-react";
import {
  useMandateActions,
  useMandates,
  useRequiredDeposit,
  useChallengeAction,
} from "@/lib/hooks/useMandateGuard";
import { useWallet } from "@/lib/genlayer/wallet";
import { success, error } from "@/lib/utils/toast";
import type { Action } from "@/lib/contracts/types";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { VerdictPanel } from "./VerdictPanel";

/**
 * D10: the contract stores OPEN and never advances it; "window elapsed,
 * unchallenged" is derived here from challenge_closes_at against wall clock.
 */
function effectiveState(a: Action): { label: string; className: string } {
  const nowSec = Math.floor(Date.now() / 1000);
  if (a.state === "OPEN") {
    if (nowSec >= Number(a.challenge_closes_at)) {
      return {
        label: "UNCHALLENGED (window elapsed)",
        className: "bg-secondary text-secondary-foreground",
      };
    }
    return { label: "OPEN", className: "bg-green-600 text-white" };
  }
  if (a.state === "CHALLENGED") {
    return { label: "CHALLENGED", className: "bg-amber-500 text-black" };
  }
  if (a.state === "RESOLVED_OUT_OF_MANDATE") {
    return { label: "RESOLVED — OUT OF MANDATE", className: "bg-red-600 text-white" };
  }
  if (a.state === "RESOLVED_WITHIN_MANDATE") {
    return { label: "RESOLVED — WITHIN MANDATE", className: "bg-green-600 text-white" };
  }
  return { label: a.state, className: "bg-secondary text-secondary-foreground" };
}

function formatWei(wei: number | string | bigint): string {
  return (Number(wei) / 1e18).toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function ChallengeButton({ action }: { action: Action }) {
  const { isConnected } = useWallet();
  const challengeAction = useChallengeAction();
  const [depositWei, setDepositWei] = useState<string | null>(null);

  const adjudicated =
    action.state === "RESOLVED_OUT_OF_MANDATE" ||
    action.state === "RESOLVED_WITHIN_MANDATE";
  const hasChallenge = action.open_challenge_id !== "";
  const windowElapsed = Math.floor(Date.now() / 1000) >= Number(action.challenge_closes_at);
  const canChallenge =
    !adjudicated && !hasChallenge && !windowElapsed && isConnected;

  // The exact deposit is read from the contract, never computed client-side.
  const enabled = canChallenge;
  const queryEnabled = enabled;

  // Lazily fetch the required deposit when the button is available.
  const { data: required } = useRequiredDeposit(queryEnabled ? action.id : null);

  async function handleChallenge() {
    if (!required) {
      return;
    }
    try {
      await challengeAction.mutateAsync({ actionId: action.id, depositWei: required.toString() });
      success("Challenge opened", {
        description: `Deposit of ${formatWei(required)} GEN attached.`,
      });
      setDepositWei(required.toString());
    } catch (e: any) {
      error("Challenge failed", e?.message ?? String(e));
    }
  }

  if (adjudicated) {
    return (
      <Badge variant="outline" className="text-sm">
        Already adjudicated
      </Badge>
    );
  }
  if (hasChallenge) {
    return (
      <Badge className="bg-amber-500 text-black text-sm">
        Challenged — awaiting resolution
      </Badge>
    );
  }
  if (windowElapsed) {
    return (
      <Badge variant="outline" className="text-sm">
        Window elapsed
      </Badge>
    );
  }
  return (
    <Button
      onClick={handleChallenge}
      disabled={!enabled || challengeAction.isPending || !required}
      size="sm"
      className="text-sm"
    >
      {challengeAction.isPending ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Challenging…
        </>
      ) : (
        <>
          <Gavel className="mr-2 h-4 w-4" />
          Challenge{required ? ` (${formatWei(required)} GEN)` : ""}
        </>
      )}
    </Button>
  );
}

/**
 * Surface 2 — Action feed: what the agent bought, with live state.
 * Surface 3 (challenge + verdict) opens for the selected action below the feed.
 */
export function ActionFeed({ mandateId }: { mandateId: string | null }) {
  const { data: actions, isLoading } = useMandateActions(mandateId);
  const { data: mandates } = useMandates();
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);

  const mandate = mandates?.find((m) => m.id === mandateId);
  const selectedAction = actions?.find((a) => a.id === selectedActionId) ?? null;
  const selectedChallengeId =
    selectedAction && selectedAction.open_challenge_id !== ""
      ? selectedAction.open_challenge_id
      : null;

  return (
    <div className="brand-card p-6 space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-xl font-semibold">
          <Activity className="h-5 w-5" />
          Action feed
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Every action the agent recorded against this mandate.
          {mandate ? ` Bond intact: ${mandate.bond_intact ? "yes" : "NO — slashed"}.` : ""}
        </p>
      </div>
        {isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading actions…
          </div>
        )}
        {!isLoading && (!actions || actions.length === 0) && (
          <p className="text-muted-foreground">
            No actions recorded yet. The agent records purchases here.
          </p>
        )}
        {actions?.map((a) => {
          const st = effectiveState(a);
          return (
            <div
              key={a.id}
              className="rounded-lg border p-4 space-y-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="font-semibold text-lg">{a.item}</div>
                <Badge className={st.className}>{st.label}</Badge>
              </div>
              <div className="grid gap-1 text-sm">
                <div>
                  <span className="text-muted-foreground">Price: </span>
                  <span className="font-medium">{a.price}</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-muted-foreground">Listing: </span>
                  <a
                    href={a.merchant_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-500 hover:underline break-all flex items-center gap-1"
                  >
                    {a.merchant_url} <ExternalLink className="h-3 w-3 inline" />
                  </a>
                </div>
                <div className="flex items-center gap-1">
                  <Clock className="h-3 w-3 text-muted-foreground" />
                  <span className="text-muted-foreground">
                    Purchased at {a.purchased_at} · window closes{" "}
                    {new Date(Number(a.challenge_closes_at) * 1000).toLocaleTimeString()}
                  </span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <ChallengeButton action={a} />
                {(a.open_challenge_id !== "" ||
                  a.state.startsWith("RESOLVED")) && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedActionId(a.id === selectedActionId ? null : a.id)}
                  >
                    {a.id === selectedActionId ? "Hide verdict" : "Show verdict"}
                  </Button>
                )}
              </div>
              {a.id === selectedActionId && (
                <VerdictPanel
                  challengeId={selectedChallengeId}
                  action={a}
                />
              )}
            </div>
          );
        })}
    </div>
  );
}
