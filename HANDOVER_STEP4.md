# Handover — STEP 4 (`record_action` + `challenge`, checkpoint CP2b)

**For:** the coding agent · **From:** PM · **Date:** 2026-09-05
**Hand this file to the agent along with the repo.** It is self-contained.

CP2a is **APPROVED**. Storage schema and `register_mandate` are in. This step completes the deterministic core.

---

## 1. Read these first

| File | What it is |
|---|---|
| `README.md` | The design. Source of truth for scope. Do not edit. |
| `DESIGN_DECISIONS.md` | Your spec, approved at CP1. |
| `PROJECT_ROADMAP.md` | Decision register §4 (D1–D7), verified constraints §5. |
| `AGENT_INSTRUCTIONS.md` | Standing rules + your task. **STEP 4 only.** |
| `PROGRESS.md` | Read the CP2a entry **and the PM review beneath it** — it carries three items into this step. |
| `contracts/mandate_guard.py` | Your own STEP 3 code. You are extending it. |

Still no LLM and no web access this step. Everything here is deterministic.

---

## 2. Three carry-forwards you must clear first

From the CP2a review. Do these before the new methods, because two of them change code you already shipped.

**(a) Reject `principal == operator` in `register_mandate`.**
You were right not to add an unspecified restriction unasked — keep that instinct. This one is ruled in because it defends an invariant the design already states. `README.md` rests on the two parties being adversaries. If they are the same address, a slash moves funds from an address to itself, costs nothing, and yet the contract records "out of mandate, bond slashed" — a materially false record in a product whose entire value is trustworthy records. Raise `gl.vm.UserError`, add a test.

**(b) Replace bare `KeyError` with `UserError`, behind one helper.**
I probed `get_mandate("m-999999")` on a fresh deployment: it raises a bare `KeyError` with an empty message. That breaks standing rule 9 (no bare Python exception may escape a contract — it breaks GenVM error handling) and gives the frontend nothing to show.

This step adds three more methods taking caller-supplied IDs, so **do not fix it inline three times.** Add private helpers — `_get_mandate_or_raise(mandate_id)`, `_get_action_or_raise(action_id)`, `_get_challenge_or_raise(challenge_id)` — and route **every** lookup, including the existing views, through them. One test per helper asserting the `UserError`.

**(c) Add the `required_deposit` view method.**
Consequence of the exact-deposit rule from CP1: if the amount must match exactly, callers must be able to read it. Signature `required_deposit(action_id: str) -> int`, resolving action → mandate → `bond_wei // u256(10)` (D3). The frontend will read this at STEP 10 rather than computing it client-side.

---

## 3. New PM rulings for this step

**D8 — `record_action` takes typed parameters, not a JSON blob.** Locked signature:

```
record_action(
    mandate_id: str,
    merchant_url: str,
    item: str,
    price: str,          # as shown on the listing, e.g. "$180.00" — a string, not a number
    purchased_at: str,   # caller-supplied evidence only; see D9
) -> str                 # returns action_id
```

`README.md` says `record_action(action_json)`; that describes the *payload*, not the ABI. Calldata gives us typed arguments for free, so a JSON string would only add a parse step and a whole class of malformed-input failures for no benefit. `price` stays a **string** deliberately — it is evidence quoted from the listing, judged as text by the LLM at STEP 5. Do not parse it into a number; USD prices and the wei-denominated ceiling are deliberately not interconvertible (see the USD/GEN seam note in `PROJECT_ROADMAP.md` §4).

**D9 — window arithmetic never touches caller-supplied time.** This is security-relevant, not stylistic.

- `recorded_at` and `challenge_closes_at` are derived from the **transaction's pinned clock** (`int(datetime.now(timezone.utc).timestamp())`, D1), exactly as `register_mandate` already does.
- `purchased_at` is **evidence only** — stored, shown in the UI, and passed to the LLM at STEP 5. It must never enter window arithmetic.
- Why: if the operator supplied the timestamp that sets the window, the operator controls their own challenge window — they could backdate an action and be unchallengeable on arrival. That would quietly destroy the mechanism.
- This needs one new field on the `Action` struct (`purchased_at: str`). Small schema addition, expected.

**D10 — the "window elapsed, unchallenged" state is derived, not poked.** Nothing on-chain fires when a window expires, so that state cannot set itself. **Do not add a poke/settle transaction to advance it** — that is scope, and it puts a liveness requirement on a demo.

Instead, **verify** whether `datetime.now(timezone.utc)` returns a meaningful value inside a `@gl.public.view` (it may not — views are read-only and may not carry a transaction datetime). Then:
- If it does → have the action view report the *effective* state, deriving elapsed-ness from `challenge_closes_at`.
- If it does not → leave the stored state as `OPEN`, return `challenge_closes_at` in the view, and let the frontend compare against wall-clock at STEP 10.

Either branch is acceptable. **Verify which, state it in your CP2b entry, and don't guess.**

**Who may challenge:** anyone, per `README.md` ("Anyone can challenge one action inside a window"), explicitly including the principal. Add no restriction on the challenger's identity.

**Reject `record_action` on a mandate whose bond is no longer intact** (`bond_intact == False`). Every recorded action must be backed by a live bond, or there is nothing to slash.

---

## 4. How to test the challenge window — use `warp()`

This is the part of the step that would otherwise cost you an hour. The direct-mode VM can move its clock:

```python
direct_vm.warp("2026-09-05T12:00:00Z")   # ISO-8601 string
```

Verified in `.venv/Lib/site-packages/gltest/direct/vm.py` — `warp()` sets the block timestamp and refreshes `gl.message`, and the harness patches `datetime.datetime` so that `datetime.now()` inside the contract reflects it, including mid-test updates. So the window test is: register → `record_action` at T → `warp` to T + window + 1s → assert `challenge` is rejected.

Test both sides of the boundary: a challenge **just inside** the window succeeds, and one **just outside** is rejected. An off-by-one on a deadline is exactly the kind of bug that survives a happy-path test and ruins a live demo.

---

## 5. Tests required

Beyond the three carry-forward tests in §2, at minimum:

- Action recorded and read back — every field, including `purchased_at` and a `challenge_closes_at` that equals `recorded_at + challenge_window_seconds`.
- A non-operator attempting `record_action` → rejected (only the mandate's registered operator may record).
- `record_action` against an unknown `mandate_id` → `UserError`.
- `record_action` on a mandate with `bond_intact == False` → rejected.
- Challenge accepted just inside the window; rejected just outside it (via `warp`).
- Second challenge on the same action → rejected while one is open.
- Deposit below required → rejected. Deposit **above** required → also rejected (the rule is exact equality, so prove both directions).
- `required_deposit` returns exactly `bond_wei // 10` for a known bond.
- Challenge against an unknown `action_id` → `UserError`.
- The full deterministic path end-to-end in one test: register → record → challenge, asserting the action and challenge states after each.

Assert on the specific `UserError`, not merely that something raised.

---

## 6. Environment — unchanged, repeated because it bites

- Prefix lint/test commands with `PYTHONIOENCODING=utf-8` or `genvm-lint` crashes *after passing*.
- **Do not remove `_patch_windows_stdin_injection()` from `tests/direct/conftest.py`.** Load-bearing.
- Keep the pinned runner header. Ignore the linter's "newer runner available" note (PM ruling).
- Storage rules from `PROJECT_ROADMAP.md` §5 still apply — declare persistent fields in the class body, `u256` not `int`, `TreeMap`/`DynArray`, `str` calldata keys, `gl.vm.UserError` never bare `Exception`.
- **Do not construct `TreeMap()` in `__init__`** — you proved why at CP2a. Any new container follows the same lazy-default pattern.
- Network `studionet`; local Studio is broken, stay away. Venv: `source .venv/Scripts/activate`. Baseline `ba65efb`.
- Housekeeping: `scratch/schema_probe/` is untracked — commit it as evidence or delete it, and make sure `scratch/` never ships in the public repo at STEP 12.

---

## 7. Definition of done

- Carry-forwards (a), (b), (c) all done, each with a test.
- `record_action` and `challenge` implemented per D8/D9; view methods for listing a mandate's actions and reading one action with its challenge state.
- `resolve` **not** implemented — that is STEP 5 and needs its own review.
- `PYTHONIOENCODING=utf-8 genvm-lint check contracts/mandate_guard.py` → clean, no warnings of ours.
- `PYTHONIOENCODING=utf-8 pytest tests/direct/ -v` → all green, **including the 53 that already pass**. Do not break existing tests.
- A `CP2b` entry appended to `PROGRESS.md`: the test matrix and real output (`N passed in Xs`), the D10 verification result, and any schema changes written out.
- **Then stop and wait for PM review.** Do not begin STEP 5.

Stop and write a `BLOCKED` entry the moment you hit a blocker, an ambiguity, or anything needing a deviation. Deadline **17 Sep 15:30 UTC**; day 3 of 15, comfortably on plan — protect that margin by surfacing problems early rather than working around them quietly.
