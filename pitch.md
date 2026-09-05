# Mandate Guard — pitch copy

> **WARNING — do not post as-is.**
> This copy is written in the earlier, polished voice that reads as machine-written:
> stacked triads, rhetorical-question-then-punchline, "here's the insight" signposting,
> a zinger at the end of every line. The Injection Court copy was rewritten to fix this;
> this one has not been. **Rewrite in the plain human voice before posting.**
> See `../injection-court/pitch.md` for the target voice.

Kept because the substance and structure are correct — only the delivery needs redoing.

---

## X thread (old voice — needs rewrite)

**1/**
> We gave AI agents wallets before we gave anyone a way to check their judgment.
>
> Your agent can spend your money. Nothing on earth verifies it honored what you actually meant.
>
> I'm building Mandate Guard.

**2/**
> AP2, x402, Visa TAP all solved the same half: numeric limits. Price caps, merchant allowlists, velocity.
>
> But half of every real instruction is a judgment call:
>
> "prefer refundable"
> "a reputable seller"
> "nothing that looks like a scalper"
>
> No rail on earth enforces those.

**3/**
> Worse: in AP2, the party that checks the cart against your intent is your own agent.
>
> The exact party that could be compromised or misaligned.
>
> And AP2's flagship case is "buy the tickets the moment they go on sale."
>
> You're asleep. Nobody is watching.

**4/**
> Mandate Guard:
>
> 1. You write your mandate in plain English
> 2. Your agent posts a bond, transacts instantly — zero added latency
> 3. Anyone can challenge a purchase
> 4. GenLayer validators fetch that live listing and rule on it
> 5. Out of mandate → bond slashed, you're paid

**5/**
> The verdict is structured and on-chain:
>
> {
>  within_mandate: false,
>  clause_violated: "prefer refundable",
>  severity: 3,
>  reasoning: "Non-refundable basic economy. Refundable fare was $40 more."
> }
>
> Not a vibe. A ruling, with money attached.

**6/**
> Why this needs GenLayer and not a server:
>
> You and the agent's operator are adversaries. Neither backend gets to grade the homework.
>
> The call needs judgment, not code. And it needs to read the live web.
>
> Decentralized AI-validator consensus. No substitute.

**7/**
> The real shift:
>
> Today we constrain agents with permissions. Brittle, coarse, broken the moment reality gets specific.
>
> Mandate Guard constrains them with accountability: act freely, be judged, post collateral.
>
> It's how we govern human fiduciaries. It's the only thing that scales.

**8/**
> Agents got payment rails this year. Enforcement never shipped.
>
> Every layer engineered the happy path. None built the part where your agent is wrong at 3am and you wake up to the charge.
>
> That's the layer I'm building.
>
> @GenLayer #AgentTank

---

## 90-second video script (old voice — needs rewrite)

> We gave AI agents wallets this year. We didn't give anyone a way to check their judgment.
>
> AP2, x402, Visa's Trusted Agent Protocol — they all solved the same half. Numeric limits.
> Price caps. Merchant allowlists.
>
> But half of every real instruction you give an agent is a judgment call. *Prefer
> refundable. A reputable seller. Nothing that looks like a scalper.* No payment rail on
> earth can enforce a sentence like that.
>
> And it gets worse. In AP2, the thing that checks the cart against your intent is your own
> agent — the exact party that might be compromised. Meanwhile its flagship use case is "buy
> the tickets the moment they go on sale." Which means you're asleep, and nobody is watching.
>
> So I'm building Mandate Guard.
>
> You write your mandate in plain English. Your agent posts a bond and transacts instantly —
> no added latency. Anyone can challenge a purchase. GenLayer's validators go fetch that live
> listing themselves and rule on it. Out of mandate, the bond is slashed and you're paid.
>
> Here's the real shift. Today we constrain agents with permissions — brittle, coarse,
> useless the moment reality gets specific. Mandate Guard constrains them with accountability.
> Act freely, be judged, post collateral.
>
> That's exactly how we govern human fiduciaries. And it's the only model that scales to
> millions of autonomous transactions.
>
> Every layer engineered the happy path. I'm building the one where your agent is wrong at 3am.

If it runs long, cut the "And it gets worse" paragraph down to
*"And the thing checking your agent's cart against your intent — is your agent."*

---

## Portal submission (old voice — needs rewrite)

**Title**

> Mandate Guard — enforcing what you actually meant when your agent spends

**Notes / Description** (~880 chars, limit is 1000)

> My pitch for Agent Tank. It's called Mandate Guard.
>
> Agent payment rails like AP2 and x402 handle numeric limits fine — price caps, merchant allowlists, spend velocity. But half of any real instruction is a judgment call. "Prefer refundable." "A reputable seller." "Nothing that looks like a scalper." Nothing can enforce those. And in AP2, the thing checking the cart against your intent is your own agent, which is the part most likely to be compromised in the first place.
>
> So the idea is: you write your mandate in plain English, your agent posts a bond and transacts immediately with no added latency, and anyone can challenge a purchase afterwards. GenLayer validators fetch the live listing and rule on whether it actually fit the mandate. If it didn't, the bond gets slashed and you're compensated.
>
> It's constraining agents through accountability rather than permissions.
>
> Full pitch on X, linked below.

---

## Rewrite notes

What to change when redoing the voice:

- Kill the triads. "Price caps, merchant allowlists, velocity" and "brittle, coarse, broken"
  are the loudest tells.
- Drop the signposting: "The real shift:", "Why this needs GenLayer and not a server:".
- Drop or bury the JSON block. It reads as a flourish rather than a detail.
- Vary sentence length deliberately. Let one run long.
- Add at least one admission of something unresolved. That is the strongest human signal
  and AI copy almost never does it. Candidates from the open questions in `README.md`:
  challenge window length, bond sizing, frivolous-challenge deterrence.
- Stop landing a punchline at the end of every post.

---

## Form notes

- Contribution date must match the day the post actually goes up.
- Title is marked optional. Fill it anyway — reviewers scan a list.
- The portal states video pitches earn more GLP than text.
- Deadline reads 2 Sep 12:00 UTC on the main page and 2 Sep 11:59 UTC on the pitch page.
  Treat 11:59 UTC as the real cutoff.
- Submission URL: `portal.genlayer.foundation/submit-contribution?mission=14`
