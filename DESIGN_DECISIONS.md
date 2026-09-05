# Mandate Guard — Design Decisions (STEP 2, CP1)

**Date:** 2026-09-05
**Status:** Design lock for PM review. No contract code written (a disposable URL probe
contract was deployed purely as verification tooling — see §6).
**Scope:** Confirms the four PM rulings in `PROJECT_ROADMAP.md` §4 (D1–D4) are
implementable as written, locks the demo scenario and listing URLs (including the new
D5 ruling), and fixes the verdict schema. Nothing here changes a PM ruling.

---

## D1 — Challenge window

**Ruling:** 24h production default, contract-configurable, 120 s in demo mode.
**Confirmed implementable: yes.**

**Mechanism (verified):** the GenVM clock is pinned to the transaction's datetime.
`datetime.now(timezone.utc)` inside a contract returns the transaction datetime, not the
host wall clock, and **every validator re-executing the transaction sees the same value**.
The same value is also available directly as the ISO-8601 string
`gl.message_raw['datetime']`.

Implementation for the challenge window (relative arithmetic, exactly what the docs
recommend this clock for):

- `register_mandate` takes a `challenge_window_seconds: u256` parameter (default
  `86400`; the demo deploys/registers with `120`).
- `record_action` stores `challenge_closes_at: u256` =
  `int(datetime.now(timezone.utc).timestamp()) + challenge_window_seconds`, using the
  **record_action transaction's** pinned datetime.
- `challenge` rejects if `int(datetime.now(timezone.utc).timestamp()) >= challenge_closes_at`,
  using the **challenge transaction's** pinned datetime (which reflects real elapsed time,
  because it is a separate, later transaction).
- Window checks happen only in write methods; no view method needs the clock.

**Evidence:**

1. Official docs — Transaction Context
   (https://docs.genlayer.com/developers/intelligent-contracts/features/transaction-context):
   "Time inside the GenVM is deterministic and pinned to the transaction's timestamp…
   Every validator re-executing the transaction sees the same value, so you can use it
   for storage, comparisons, and prompt context without breaking equivalence."
   The page shows `int(datetime.now(timezone.utc).timestamp())` used for exactly this
   expiry pattern, and `gl.message_raw['datetime']` as the raw message field.
2. Installed linter — `genvm_linter/lint/safety.py` (v0.11.1rc2) explicitly allows
   `datetime.now()` with the comment "datetime.now() is OK in GenLayer - SDK provides
   deterministic version", while listing `time.time` among forbidden calls. We will use
   the `datetime` form (not `int(time.time())`, which the docs also show but the linter
   flags) so `genvm-lint` stays clean.
3. Live-network proof — a probe contract on studionet recorded
   `int(datetime.now(timezone.utc).timestamp())` inside a `strict_eq` non-deterministic
   block alongside a web fetch. Validators agreed on a payload containing the clock
   reading (`tx_unix_time: 1788583671`, i.e. 2026-09-05 UTC) and the transaction was
   ACCEPTED — direct confirmation the clock is consensus-safe on a real validator set.

**Docs caveat adopted into the design:** the pinned datetime "may be minutes or hours
old" relative to wall-clock by the time of re-execution. Irrelevant here: both
`challenge_closes_at` and the challenge-time check are transaction datetimes, so the
window is measured consistently on-chain.

## D2 — Bond sizing

**Ruling:** operator bond ≥ mandate spend ceiling, 1:1, posted at `register_mandate`.
**Confirmed implementable: yes.**

- The spend ceiling is supplied as an explicit calldata parameter
  `spend_ceiling_wei: u256` to `register_mandate(text, challenge_window_seconds,
  spend_ceiling_wei)`. It is a number declared by the principal, **not parsed out of the
  natural-language mandate** (parsing numbers from prose is fragile and unnecessary —
  the LLM judges the mandate text; the numeric ceiling exists only to size the bond).
- The bond arrives with the same call: `register_mandate` is `@gl.public.write.payable`,
  and the amount is `gl.message.value` (native `u256`, wei-denominated; 1 GEN = 10^18
  wei). No conversion, no `int`, no floats anywhere on the value path.
- Validation, in order: reject zero-value calls (`gl.message.value == 0`), reject
  non-positive ceilings (`spend_ceiling_wei == 0`), then require
  `gl.message.value >= spend_ceiling_wei`, raising `gl.vm.UserError` (never a bare
  `Exception` — that crashes GenVM error handling per the linter's rules). On success the
  bond is tracked as this mandate's held balance and the mandate is stored.
- Note for the demo: the listing prices are USD strings read from the page; the verdict
  is a text-vs-text judgment (mandate text vs recorded action vs listing). The
  wei-denominated ceiling sizes the bond and is not numerically compared to a USD price.

## D3 — Challenger deposit

**Ruling:** deposit = 10% of bond, forfeited to the operator on a failed challenge, one
open challenge per action. **Confirmed implementable: yes.**

- Deposit arithmetic in pure integer `u256`: `required_deposit = bond_wei // u256(10)`
  (identical to `bond * 10 // 100` under floor division). No floating point — GenLayer
  value paths are integer-only anyway.
- `challenge(action_id)` is `@gl.public.write.payable`; requires
  `gl.message.value == required_deposit` (exact — keeps accounting unambiguous),
  the window still open (D1), and no challenge already open on the action.
- One-open-challenge-per-action enforced with a storage flag/set on the action; a second
  concurrent challenge reverts.
- Settlement: `within_mandate == false` → bond slashed, principal compensated (payout is
  an external message that executes **on finalization**); `within_mandate == true` →
  deposit forfeited to the operator and the challenger's deposit is not returned.
  If a challenge is resolved in the challenger's favour, the deposit is returned to the
  challenger. (Roadmap wording only specifies the failed-challenge destination; the
  success path must return it — flagged here so it is a locked design choice, not an
  improvisation later.)

## D4 — Equivalence fields

**Ruling:** `within_mandate` compared exactly; `clause_violated` compared semantically;
`severity` and `reasoning` excluded from consensus. **Confirmed implementable: yes, and
this is the documented pattern.**

Mechanism, per the equivalence-principle docs
(https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle):

- `resolve()` copies mandate text and recorded action out of storage with
  `gl.storage.copy_to_memory()` **before** the non-deterministic block (storage objects
  cannot be used inside one).
- `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` — never
  `prompt_non_comparative`, which the docs say is not consensus for settlement logic.
- `leader_fn`: fetch the live listing (fetch method per §6 below), prompt the LLM with
  mandate text + recorded action + listing content, return the verdict dict (§7).
- `validator_fn`: receives a `gl.vm.Result` — if not `isinstance(..., gl.vm.Return)`
  (leader errored) it returns `False` (Disagree). Otherwise it **independently re-fetches
  and re-derives its own verdict**, then compares decision fields:
  - `within_mandate`: exact `==` (docs Pattern 1, partial field matching).
  - `clause_violated`: semantic comparison. If both sides say `None` (or one says a
    violation and the other does not), it decides exactly. Otherwise the validator uses
    LLM-based comparative judgment (docs Pattern 3) — the `EqComparative` template via
    `gl_call.gl_call_generic` with a principle of the form: "`within_mandate` must match
    exactly; `clause_violated` must refer to the same mandate clause; severity and
    reasoning may differ."
  - `severity`, `reasoning`: stored on-chain for display, never compared.

## D5 — Demo listing URLs (new PM ruling, 2026-09-05)

**Ruling:** primary demo URL is a page we control (GitHub Pages), plus one genuinely
third-party page to prove the contract reads the real web, plus a fallback URL.
Transparency about self-hosting goes in the submission (P7), not into the demo page.

**Published page:** a static, no-JavaScript fictional merchant listing — "Atlas Air",
flight AA-281 Berlin (BER) → Lisbon (LIS), 25 Sep 2026, two fares: **Basic Saver
$180.00, NON-REFUNDABLE** and **Flex Economy $220.00, FULLY REFUNDABLE**. Source lives in
`demo-listing/index.html` in this repo and is published at
https://github.com/PratikshaGayen/mandate-guard-demo. The page will be **frozen** — no
edits through 25 Sep — so the facts validators read cannot move.

| Role | URL | Fetch method | Local check | Validator-side check (studionet) |
|---|---|---|---|---|
| Primary demo listing | https://pratikshagayen.github.io/mandate-guard-demo/ | `gl.nondet.web.get()` | HTTP 200 | ACCEPTED, consensus agreed on content (2806 bytes, Atlas Air HTML) |
| Fallback listing (same page, different serving infra) | https://raw.githubusercontent.com/PratikshaGayen/mandate-guard-demo/main/index.html | `gl.nondet.web.get()` | HTTP 200 | ACCEPTED, consensus agreed on content (2806 bytes) |
| Third-party stability proof | https://example.com/ | `gl.nondet.web.get()` | HTTP 200 | ACCEPTED, consensus agreed (559 bytes) |
| Third-party listing-shaped page (spare) | https://books.toscrape.com/ | `gl.nondet.web.get()` | HTTP 200 | ACCEPTED, consensus agreed (51,274 bytes) |

- Reachability was proven **validator-side**, not just locally: a disposable probe
  contract (deployed at `0x66E70CEF7C04cA0A95ec920a830d1B40330A37a0` on studionet,
  source in `scratch/url_probe.py`) fetched each URL inside a `strict_eq` block. The
  result is only written to storage when every participating validator independently
  fetches and agrees on the content byte-for-byte — all four probes did, each with
  majority-AGREE consensus (the 2 IDLE validators per round are non-participants, the
  normal studionet pattern).
- All four pages are static: **`gl.nondet.web.get()` suffices for every URL**;
  `gl.nondet.web.render()` is not needed for the demo. If a future URL ever needs JS
  rendering, `render(url, mode='text')` is the fallback — not required for anything
  chosen here.
- `books.toscrape.com` is the emergency spare only — it is a real third-party page with
  real prices, but it is not our scenario; the demo runs on the Atlas Air page.
- **P7 obligation recorded:** the public submission must state that the demo merchant
  page is hosted by us (github.com/PratikshaGayen/mandate-guard-demo) and that the
  validator fetch is nonetheless a genuine live fetch over the open internet.

## Demo scenario

**Mandate (plain English, registered by the principal):**

> "You may book one economy flight ticket from Berlin to Lisbon departing 25 September
> 2026 for our team trip. Spend at most $250 on the ticket. Prefer refundable fares over
> non-refundable ones, even if the refundable fare costs a bit more."

It contains a numeric clause (spend ceiling ≤ $250) and a judgment clause ("prefer
refundable fares") — the README.md model.

**Action A (compliant):** agent books **Flex Economy, $220.00, fully refundable** and
records it (`merchant_url` = primary URL, item "Flex Economy", price "$220.00").
Expected verdict: `within_mandate: true`, `clause_violated: null` — refundable fare
chosen, price inside the ceiling. The challenger loses their deposit.

**Action B (deliberate drift):** agent books **Basic Saver, $180.00, non-refundable**.
Expected verdict: `within_mandate: false`, `clause_violated: "prefer refundable fares"`,
`severity: 2`, `reasoning: "Non-refundable Basic Saver booked at $180.00 although the
refundable Flex Economy fare was available at $220.00, within the $250 ceiling."`
The bond is slashed and the principal compensated.

Action B violates the judgment clause while *saving money* — deliberately chosen so the
demo shows the product enforces intent, not just numbers.

## Verdict schema

Exactly as `README.md`, frozen:

```json
{
  "within_mandate": false,
  "clause_violated": "prefer refundable fares",
  "severity": 2,
  "reasoning": "Non-refundable Basic Saver booked at $180.00 although the refundable Flex Economy fare was available at $220.00, within the $250 ceiling."
}
```

- `within_mandate: bool` — the only exact-compared field (D4).
- `clause_violated: str | null` — the violated clause quoted from the mandate text;
  `null` when the action is within mandate. Semantic-compared (D4).
- `severity: int` (use `u256` in the contract) — 0–3; stored, excluded from consensus.
- `reasoning: str` — stored, excluded from consensus.

## Notes and open items for the PM

1. **Successful-challenge deposit path** (D3): the roadmap specifies forfeit on failure;
   return-to-challenger on success is the symmetric completion and is locked here.
   Flag if you want a different rule.
2. **Spend-ceiling units** (D2): ceiling is wei-denominated and principal-declared; the
   demo's USD prices are judged as text. No unit-conversion code exists or is needed.
3. `scratch/url_probe.py` and the probe contract deployment are verification tooling,
   not Mandate Guard code. The probe contract can be left on studionet or ignored; it
   holds no funds beyond deployment fees.
4. studionet rounds showed 3 AGREE + 2 IDLE (non-participating) validators per
   transaction — consistent with every prior studionet transaction in this project, not
   a defect.
