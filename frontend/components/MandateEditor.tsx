"use client";

import { useState } from "react";
import { Loader2, ShieldPlus } from "lucide-react";
import { useRegisterMandate } from "@/lib/hooks/useMandateGuard";
import { useWallet } from "@/lib/genlayer/wallet";
import { success, error } from "@/lib/utils/toast";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

/**
 * Surface 1 — Mandate editor: plain-English mandate, principal address,
 * spend ceiling, challenge window, and the operator bond posted with the call.
 */
export function MandateEditor({ onRegistered }: { onRegistered?: () => void }) {
  const { isConnected, address } = useWallet();
  const registerMandate = useRegisterMandate();

  const [text, setText] = useState("");
  const [principal, setPrincipal] = useState("");
  const [ceilingGen, setCeilingGen] = useState("250");
  const [windowSeconds, setWindowSeconds] = useState("86400");

  const isSubmitting = registerMandate.isPending;

  async function handleSubmit() {
    if (!text.trim()) {
      error("Missing mandate", { description: "Write the mandate in plain English first." });
      return;
    }
    if (!/^0x[0-9a-fA-F]{40}$/.test(principal)) {
      error("Invalid principal", { description: "The principal must be a 0x-prefixed address." });
      return;
    }
    const ceiling = Number(ceilingGen);
    if (!Number.isFinite(ceiling) || ceiling <= 0) {
      error("Invalid ceiling", {
        description: "The spend ceiling must be a positive number of GEN.",
      });
      return;
    }
    const windowSec = Number(windowSeconds);
    if (!Number.isInteger(windowSec) || windowSec <= 0) {
      error("Invalid window", {
        description: "The challenge window must be a positive number of seconds.",
      });
      return;
    }

    try {
      const ceilingWei = BigInt(Math.round(ceiling * 1e18)).toString();
      await registerMandate.mutateAsync({
        text: text.trim(),
        principal: principal.trim(),
        spendCeilingWei: ceilingWei,
        challengeWindowSeconds: String(windowSec),
      });
      success("Mandate registered", {
        description: "The operator bond was posted with the registration.",
      });
      onRegistered?.();
    } catch (e: any) {
      error("Registration failed", { description: e?.message ?? String(e) });
    }
  }

  const bondGen = (Number(ceilingGen) || 0).toLocaleString(undefined, {
    maximumFractionDigits: 4,
  });

  return (
    <div className="brand-card p-6 space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-xl font-semibold">
          <ShieldPlus className="h-5 w-5" />
          Register a mandate
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          The operator posts the bond. The principal is the party the bond
          protects — it must be a different address.
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="mandate-text">Mandate (plain English)</Label>
        <textarea
          id="mandate-text"
          placeholder={'e.g. "You may book one economy flight ticket... Spend at most $250. Prefer refundable fares."'}
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-base shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="mandate-principal">Principal address</Label>
        <Input
          id="mandate-principal"
          placeholder="0x…"
          value={principal}
          onChange={(e) => setPrincipal(e.target.value)}
          className="font-mono text-sm"
        />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="mandate-ceiling">Spend ceiling (GEN)</Label>
          <Input
            id="mandate-ceiling"
            type="number"
            min="0"
            step="any"
            value={ceilingGen}
            onChange={(e) => setCeilingGen(e.target.value)}
            className="text-base"
          />
          <p className="text-xs text-muted-foreground">
            The bond posted equals this ceiling, 1:1 (≥ {bondGen} GEN).
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="mandate-window">Challenge window (seconds)</Label>
          <Input
            id="mandate-window"
            type="number"
            min="1"
            value={windowSeconds}
            onChange={(e) => setWindowSeconds(e.target.value)}
            className="text-base"
          />
          <p className="text-xs text-muted-foreground">
            86400 = 24 h. The demo uses 120 s.
          </p>
        </div>
      </div>
      <Button
        onClick={handleSubmit}
        disabled={isSubmitting || !isConnected}
        className="w-full text-base"
        size="lg"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Registering with bond…
          </>
        ) : (
          <>Register mandate and post bond</>
        )}
      </Button>
      {!isConnected && (
        <p className="text-sm text-muted-foreground">
          Connect the operator wallet to register a mandate.
        </p>
      )}
      {address && (
        <p className="text-xs text-muted-foreground break-all">
          Registering as operator: {address}
        </p>
      )}
    </div>
  );
}
