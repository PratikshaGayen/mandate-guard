# Mandate Guard

**Status:** finalized as the original pick, then set aside while Injection Court was
explored. Design is intact and unchanged. Pitch copy exists but is written in the earlier,
more polished voice — **needs a rewrite in the plain human voice before posting.** See
`pitch.md`.

**Event:** GenLayer Agent Tank (pitch mission → 2 Sep, build window 3–17 Sep, winners 25 Sep).

---

## The problem

Agent payment rails can enforce numeric limits. They cannot enforce intent.

AP2, x402, Visa Trusted Agent Protocol, Mastercard Agent Pay — all of them handle price
caps, merchant allowlists, and spend velocity. But half of any real instruction you give an
agent is a judgment call:

- "prefer refundable"
- "a reputable seller"
- "nothing that looks like a scalper"
- "a reasonable itinerary"

Nothing in the stack can check those.

## The verified gap

Two facts confirmed during research, both load-bearing for the pitch:

1. **AP2's Intent Mandate captures structured constraints** — size, price ceiling, colour,
   delivery address — and the buyer-side agent verifies the merchant's Cart Mandate against
   it. So the party checking whether the purchase honoured your intent **is your own
   agent**: precisely the party that could be compromised, misaligned, or prompt-injected.

2. **AP2's flagship delegated case is "buy concert tickets the moment they go on sale."**
   Human not present. Nobody watching.

Source: https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol

## What we're building

```
You register a mandate in plain English
        ↓
Agent posts a bond, then transacts instantly (no added latency)
        ↓
Every action lands on-chain with its evidence
   (merchant URL, item, price, timestamp)
        ↓
Anyone can challenge one action inside a window
        ↓
Validators fetch the live listing and rule
        ↓
Out of mandate  → bond slashed, principal compensated
Within mandate  → challenger loses their deposit
```

The optimistic-challenge shape mirrors GenLayer's own Optimistic Democracy, so the
architecture argues for itself.

## The verdict

Structured, so validators can reach consensus on comparable fields:

```python
{
  "within_mandate": False,
  "clause_violated": "prefer refundable",
  "severity": 3,
  "reasoning": "Non-refundable basic economy. Refundable fare was $40 more."
}
```

## Why this needs GenLayer

1. **The parties are adversaries.** You and the agent's operator are on opposite sides.
   Neither one's backend gets to grade the homework.
2. **The decision requires judgment, not code.** "Is a 6am departure a red-eye?" "Is this
   seller reputable?" No deterministic contract can evaluate that.
3. **It has to read the live web.** Validators fetch the actual merchant listing to check
   the claim. Native web access, no oracle.

Latency is handled by design: the agent acts immediately and challenges resolve afterwards,
so validator time never sits in the purchase path.

## Why this survived scrutiny better than Injection Court

Injection Court needed a funding mechanism that doesn't exist yet — someone has to have
staged capital before an incident or a verdict can't pay anyone, and no agent developer
posts a bond today.

Mandate Guard has no such hole. **The bond is the mechanism from step one**, posted by the
operator who wants permission to act on someone else's money. There's no insurance market
to invent and no premium pricing to hand-wave. That's why this idea got stronger under
questioning and the other one got weaker.

## Build scope (3–17 Sep, solo, Python + web)

**Intelligent Contract**
- `register_mandate(text)` — store the natural-language mandate
- `record_action(action_json)` — merchant URL, item, price, timestamp
- `challenge(action_id)` — open a challenge, post deposit
- `resolve(challenge_id)` — validators fetch the listing, evaluate against the mandate,
  return the structured verdict, then slash or release

**Frontend**
- Mandate editor
- Action feed showing what the agent bought
- Challenge button and verdict view

**Demo**
- A scripted agent that drifts out of mandate on purpose
- Challenge it live, show validators reading the real listing, show the bond slash

Start from `genlayerlabs/genlayer-project-boilerplate`.

## Open questions

- Challenge window length. Long enough for a watchdog to notice, short enough that the
  operator's capital isn't locked forever.
- Bond sizing relative to the mandate's spend ceiling.
- What stops frivolous challenges beyond losing the deposit?
- Equivalence principle: compare `within_mandate` and `clause_violated` only, or include
  `severity`? Comparing fewer fields is safer for consensus.

## Context: what already exists on GenLayer

Confirmed built, do not overlap:

| Project | Covers |
|---|---|
| Internet Court (MetaMask, BNB Chain, OKX, 20+) | agent-to-agent commerce disputes |
| Intelligent Oracle | prediction markets, insurance resolution |
| Rally | AI-validator bot/sybil filtering |
| Collective Memory | agent marketplace quality layer |
| Docs examples | football prediction market, DAO proposal compliance, bounty rules, flight-delay insurance, freelance escrow |

Mandate Guard is distinct from Internet Court: that resolves disputes between two agent
counterparties after a commercial breakdown, this enforces a principal's instructions
against their own agent.

## Sources

- https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol
- https://docs.genlayer.com/developers/intelligent-contracts/when-to-use-genlayer
- https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy/finality
- https://github.com/genlayerlabs/genlayer-project-boilerplate
