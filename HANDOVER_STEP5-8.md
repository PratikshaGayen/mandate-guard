# Handover — STEPS 5–8 (`resolve()` end to end, checkpoints CP3a · CP3b · CP3c · CP4)

**For:** the coding agent · **From:** PM · **Date:** 2026-09-05
**Hand this file to the agent along with the repo.** It is self-contained.

CP2b is **APPROVED**. This packet is deliberately larger than the previous ones: it carries the whole
`resolve()` path — leader, validator, settlement — plus integration and deployment. **Work straight
through STEPS 5, 6 and 7 without stopping for review between them.** They are three halves of one
method and splitting them wastes a review cycle each.

**You still write a `PROGRESS.md` entry at CP3a, CP3b and CP3c as you finish each** — those are the
record, and I read them. You just don't wait after them. **Stop for review once, after CP3c.**
STEP 8 (CP4) follows the same pattern but has a network dependency; see §7.

---

## 1. Read these first

| File | What it is |
|---|---|
| `README.md` | The design. Source of truth for scope. Do not edit. |
| `DESIGN_DECISIONS.md` | Your spec — demo scenario, verdict schema. |
| `PROJECT_ROADMAP.md` | Decision register §4 (D1–D15), verified constraints §5. |
| `AGENT_INSTRUCTIONS.md` | Standing rules + the STEP 5 / 6 / 7 / 8 blocks. |
| `PROGRESS.md` | The CP2b entry and the PM review beneath it. |
| `contracts/mandate_guard.py` | Your own code. You are completing it. |

This is the step where the contract stops being deterministic. Read §5 of `PROJECT_ROADMAP.md`
(equivalence principle) before writing `resolve()`.

---

## 2. What I verified for you before writing this

I ran probes so you don't have to discover these the hard way. All are empirical, not inferred — the
probe lives at `scratch/pm_probe/transfer_probe.py`.

**(1) The value-transfer API is `emit_transfer`, not a `send`.**

```python
gl.get_contract_at(some_address).emit_transfer(value=u256(amount))   # default on='finalized'
```

Note `gl.get_contract_at`, **not** `gl.contract_at` — the latter does not exist and fails with
`AttributeError: module 'genlayer.gl' has no attribute 'contract_at'`. The `on` parameter is
`Literal['accepted', 'finalized']`; **keep the `'finalized'` default** — the SDK's own docstring
warns that value transfers on `'accepted'` "may lead to undesired results". `emit_transfer` raises
`ValueError` on a zero value, so never call it with a zero payout — branch around it.

**(2) `emit_transfer` is a silent no-op in direct mode.** It encodes a `PostMessage` gl_call, and
direct mode's handler has no `PostMessage` branch — it neither transfers nor raises. Probe output:
the contract recorded `NOTE: emitted` with nothing moved.

**(3) Contract balance is always `0` in direct mode.** `self.balance` returned `0` even immediately
after a payable call carrying `value=1000`. Direct mode does not credit contract balances from
`gl.message.value`.

**Together (2) and (3) mean the balance assertions STEP 7 asks for are impossible in direct mode.**
That is an environment limit, not a failure of yours. See D11 below for what to do instead. Do not
spend an hour trying to make balances move.

**(4) You can capture the payout instead, and this is what you will assert on.** Direct mode exposes
a `_gl_call_hook` that receives every unhandled gl_call — including `PostMessage`:

```python
captured = []

def hook(vm, request):
    if "PostMessage" in request:
        captured.append(request["PostMessage"])
        return {"ok": None}
    return None

direct_vm._gl_call_hook = hook
```

Verified working; a captured entry looks exactly like this:

```
{'address': Address("0x81b637d8fCD2C6da6359E6963113a1170de795e4"),
 'calldata': {}, 'on': 'finalized', 'value': 400}
```

So you can assert recipient, amount and `on` for every payout. Put the hook in a fixture rather than
repeating it per test.

**(5) `direct_vm.run_validator(...)` exists and is how you test STEP 6.** In direct mode
`gl.vm.run_nondet` runs **only the leader** and returns its result; the validator is captured, not
run. To exercise it:

```python
direct_vm.run_validator()                                  # validator re-derives; returns bool
direct_vm.run_validator(leader_result=<forged verdict>)    # feed a wrong leader verdict
direct_vm.run_validator(leader_error=SomeError("boom"))    # simulate the leader raising
```

Its docstring notes that the validator typically re-runs the leader logic internally and therefore
hits the *current* mocks — so **swap `direct_vm.mock_web` / `mock_llm` between the contract call and
`run_validator()`** to simulate a validator that sees different external data. That is the
disagreement test, and it is the most valuable test in this packet.

---

## 3. New PM rulings

**D11 — settlement is proven in direct mode by asserting emitted payouts, not balances.**
Because of (2) and (3) above. For each settlement direction, assert: the number of payouts, each
recipient address, each exact wei amount, and `on == 'finalized'`. Real balance movement is verified
on-chain at STEP 8 (§7). **In your CP3c entry, state plainly that direct mode cannot move balances
and that payout assertions stand in** — do not write "balances verified" when what you verified was
intent. That distinction has to survive into the submission.

**D12 — the settlement outcome is recorded in storage.** Add to `Challenge`: the resolved payouts
(recipient + amount for each leg) and a resolution timestamp from the pinned clock. Two reasons:
`README.md` promises a verdict view, and the UI cannot show "bond slashed, 0.5 GEN to the principal"
if the only record of it is an external message that already left. Keep it minimal — this is not a
general ledger.

**D13 — the arithmetic of both settlement directions, locked.** Do not improvise this:

- **`within_mandate == false`** (challenge upheld, operator was out of mandate):
  the **full bond** goes to the principal; the challenger's **deposit is returned in full** to the
  challenger; `mandate.bond_intact → False`; `action.state → RESOLVED_OUT_OF_MANDATE`;
  `challenge.state → RESOLVED_UPHELD`.
- **`within_mandate == true`** (challenge rejected, operator acted within mandate):
  the challenger's **deposit goes to the operator**; the bond is **untouched** and `bond_intact`
  stays `True`; `action.state → RESOLVED_WITHIN_MANDATE`; `challenge.state → RESOLVED_REJECTED`.

The full bond to the principal — not a fraction — is what `README.md` describes ("slashes the bond
and compensates the principal") and it is the simplest rule that is obviously correct. No fee, no
split, no burn. **Note the consequence honestly in your entry:** a slash pays the principal the whole
bond regardless of how small the actual overspend was, so a $5 overrun on a $250 mandate costs the
operator the entire bond. That is a known crudeness of the v1 mechanism, it is deliberate, and it
belongs in the pitch alongside D6 — not papered over with a severity-weighted payout you invent now.
`severity` is captured in the verdict and displayed; it does **not** scale the money.

**D14 — `resolve()` may be called by anyone, and only once.** It is a permissionless crank; the whole
point is that settlement doesn't depend on either party cooperating. Reject with `UserError`: an
unknown `challenge_id`, and a challenge whose state is not `OPEN` (this is the double-resolution
guard). Deliberately **do not** require the challenge window to have closed — a challenge already
exists, so there is nothing left to wait for.

**D15 — a failed fetch or an unusable verdict must not settle.** If the listing is unreachable, the
page is unusable, or the LLM output is malformed, `resolve()` must **revert** with a clear
`UserError` and leave every piece of state and money exactly where it was. Do not invent a "could not
determine" resolution that keeps the deposit, and do not default to either verdict — a default is a
silent transfer of money based on a network error. Reverting means the caller can retry when the page
is reachable, which is the right behaviour. Your STEP 5 tests for the three failure cases assert the
revert.

---

## 4. STEP 5 — the leader function (write a CP3a entry, then keep going)

Per `AGENT_INSTRUCTIONS.md` STEP 5, plus:

- `gl.storage.copy_to_memory()` on the mandate text and the action **before** the non-deterministic
  block. Storage objects are not usable inside it.
- Fetch the listing at `action.merchant_url` by the method fixed in `DESIGN_DECISIONS.md`.
- The prompt gets: the mandate text, the recorded action (item, price, `purchased_at`,
  `merchant_url`), and the fetched listing. Return the verdict as schemed — `within_mandate`,
  `clause_violated`, `severity`, `reasoning`.
- Return **stable extracted facts**, never raw page content. Two validators fetching the same page
  seconds apart get different bytes; they must still agree on the facts.
- `json.dumps(..., sort_keys=True)` (Pattern 6) anywhere a verdict is serialised. Unstable key order
  is a consensus failure waiting to happen.
- Tests: both demo actions (compliant Flex Economy $220; drifting Basic Saver $180) via
  `direct_vm.mock_web` / `mock_llm`, plus the three D15 failure cases.

**CP3a entry must contain the actual verdict JSON produced for each demo action**, pasted, not
described.

## 5. STEP 6 — the validator (write a CP3b entry, then keep going)

Per `AGENT_INSTRUCTIONS.md` STEP 6. The one constraint that matters:

> The validator must **independently re-fetch and re-derive its own verdict**, then compare. A
> validator that only checks the leader's output for valid JSON or an allowed enum value **is not
> performing consensus** for settlement logic.
> Source: https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle

D4 governs the comparison: `within_mandate` **exactly**; `clause_violated` **semantically**;
`severity` and `reasoning` **excluded**. Wire with `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`.

Tests, using `run_validator()` per §2(5): validator agrees with a correct leader verdict; validator
**rejects** a leader verdict whose `within_mandate` is flipped; validator handles the leader raising.
Add the one that proves the mechanism: swap the web mock between the call and `run_validator()` so
the validator sees a *different listing* and legitimately disagrees.

**CP3b entry must state exactly how the validator derives its own answer and which fields are
compared** — that paragraph is the project's core technical claim and it will be read by judges.

## 6. STEP 7 — settlement (write a CP3c entry, then STOP for review)

Per `AGENT_INSTRUCTIONS.md` STEP 7, as amended by D11–D15. Also:

- `u256` throughout; no floats anywhere on the value path.
- Payouts to an EOA execute **on finalization**, not immediately — the demo timeline at STEP 11 has
  to account for that. Say so in the entry.
- A view method exposing the resolved outcome (verdict fields + recorded payouts), for the UI.
- Tests: both directions with payout assertions (D11), double-resolution rejected (D14), resolve on
  an unknown id rejected, and the three D15 failure cases leaving state untouched.

**This is the end of P3 — the contract is feature-complete. Stop here and wait for PM review.**

---

## 7. STEP 8 — integration and deployment (CP4) — conditional, read carefully

Attempt this **only after CP3c is approved**. It has a known external dependency:

**studionet's deploy path was erroring network-wide at CP2b** — a re-deploy of the known-good STEP 2
probe failed identically (`Position '32' is out of bounds`) while reads against already-deployed
contracts still succeeded. It may have recovered; check before assuming either way.

So: **write the integration tests regardless** — the full lifecycle, register → record → challenge →
resolve → settle, both verdict directions — and try to run them. If the network is still broken,
write a `BLOCKED` entry that is explicit that the *tests exist and are unrun*, and do not fake a pass.

Two things to do while you are there:
1. **Deploy the D10 view-clock probe** (`scratch/step4_probe/view_clock.py`) and complete the on-chain
   half of that verification — it is the one open verification item from CP2b.
2. **Confirm the hosted network name from the installed tooling**, do not trust the docs — they show
   both `testnet_bradbury` and `testnetAsimov`, and the working aliases are hyphenated
   (`testnet-asimov`, `testnet-bradbury`, `studionet`, `localnet`).

Fix failures in the contract, not by weakening tests. A test that passes in direct mode and fails
under real consensus is a genuine finding and the most valuable thing this step can produce — report
it, don't paper over it.

---

## 8. Environment — unchanged, repeated because it bites

- Prefix lint/test commands with `PYTHONIOENCODING=utf-8` or `genvm-lint` crashes *after passing*.
- **Do not remove `_patch_windows_stdin_injection()` from `tests/direct/conftest.py`.** Load-bearing.
- Keep the pinned runner header. Ignore the linter's "newer runner available" note (PM ruling).
- **Do not construct `TreeMap()` in `__init__`** — you proved why at CP2a.
- `gl.vm.UserError`, never a bare `Exception`. `u256`, never `int`, in storage.
- Direct-mode fixtures (`direct_alice` etc.) are **raw bytes**, not `Address` — use
  `"0x" + direct_bob.hex()` when a method takes a hex string.
- Venv: `source .venv/Scripts/activate`. Baseline `87579a8`. Commit in logical units.
- `scratch/` must never ship in the public repo at STEP 12 — carried forward.

---

## 9. Definition of done for this packet

- `resolve()` complete: leader, validator via `run_nondet_unsafe`, settlement per D13.
- D11–D15 all honoured; D12's storage addition written out in the CP3c entry.
- `PYTHONIOENCODING=utf-8 genvm-lint check contracts/mandate_guard.py` → clean.
- `PYTHONIOENCODING=utf-8 pytest tests/direct/ -v` → all green, **including the 73 that already
  pass**. Do not break existing tests.
- `CP3a`, `CP3b` and `CP3c` entries in `PROGRESS.md`, each with real output (`N passed in Xs`), the
  verdict JSON, and the payout assertions.
- **Then stop and wait for PM review.** STEP 8 only after that review.

Stop and write a `BLOCKED` entry the moment you hit a blocker, an ambiguity, or anything needing a
deviation — that rule does not relax just because this packet is longer. Deadline **17 Sep 15:30
UTC**; day 3 of 15. This packet is the riskiest part of the build; surfacing a problem here early is
worth more than finishing it quietly late.
