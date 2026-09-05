# Handover — FIX-1 + STEPS 8–11 (integration, frontend, demo — checkpoints CP4 · CP5a · CP5b · CP6)

**For:** the coding agent · **From:** PM · **Date:** 2026-09-05
**Hand this file to the agent along with the repo.** It is self-contained.

CP3a / CP3b / CP3c are **APPROVED** — the contract is feature-complete and 99/99 direct tests pass.
**One defect must be fixed first (FIX-1, §2). It is a fund-safety bug and it comes before anything
else in this packet.**

This packet is larger again: a fix, then integration and deployment, then the frontend, then the
rehearsed demo. **Work straight through. Write a `PROGRESS.md` entry at CP4, CP5a, CP5b and CP6 as
you finish each, but do not stop between them. Stop for review once, after CP6.**

The exception is §3's network dependency, and the two standing stop rules below, which do **not**
relax because the packet is long:
- **Stop immediately** on a blocker, an ambiguity, or anything needing a deviation.
- **Stop and ask** before anything outward-facing — pushing to a public repo, publishing, or posting.
  STEPS 12–13 are deliberately **not** in this packet for that reason.

---

## 1. Read these first

| File | What it is |
|---|---|
| `README.md` | The design. Source of truth for scope. Do not edit. |
| `DESIGN_DECISIONS.md` | Demo scenario, verdict schema, listing URLs. |
| `PROJECT_ROADMAP.md` | Decision register §4 (D1–D16), verified constraints §5. |
| `AGENT_INSTRUCTIONS.md` | Standing rules + the STEP 8 / 9 / 10 / 11 blocks. |
| `PROGRESS.md` | CP3a–CP3c entries and the PM review beneath CP3c. |

---

## 2. FIX-1 — the bond can be paid out twice. Fix this before STEP 8.

**D16 — a slashed bond must not be slashed again.** Found in PM review of CP3c by reading
`challenge()` and `resolve()` together. Neither one is wrong on its own; the pair is.

The path, concretely:

1. Operator registers a mandate with bond **B**, then records actions **A1** and **A2** while the
   bond is intact. `record_action` correctly refuses new actions once the bond is gone — but these
   two already exist, and both windows are open.
2. A1 is challenged, resolves **out of mandate**: `emit_transfer(value=mandate.bond_wei)` pays **B**
   to the principal and sets `bond_intact = False`.
3. **A2 is still `OPEN` and still challengeable — `challenge()` never checks `bond_intact`.** So it
   accepts a second deposit, sized from `mandate.bond_wei`, which is still the full unreduced figure.
4. That challenge resolves out of mandate too, and `resolve()` pays **B again**. There is no second
   bond to pay it from.

The contract holds every mandate's bond in **one balance**, so the second payout comes out of
somebody else's bond. That is the worst failure mode this contract has: a bug in one mandate silently
drains another principal's money. It is reachable in the demo scenario as it stands — two actions on
one mandate, either of them challengeable.

**Both halves must be fixed; neither alone is sufficient:**

- **`challenge()` rejects when `mandate.bond_intact` is `False`.** Closes the entrance. A mandate
  whose bond is gone has nothing left to secure a challenge, and taking a deposit against it would be
  taking money for a promise the contract cannot keep.
- **`resolve()` must not pay the bond leg if the bond is already gone.** A challenge opened *before*
  the slash is still in flight when it lands, so the entrance check does not cover it. On an
  out-of-mandate verdict with `bond_intact == False`: **skip the bond payout entirely, still return
  the challenger's deposit in full, and still record the verdict and states.** The challenger is made
  whole — they were right, and they should not lose a deposit because someone else got there first.
  Record the skipped leg explicitly in the payouts (a `purpose` naming that the bond was already
  slashed), so the UI and the verdict view tell the truth rather than showing a silent nothing.

**Tests required, and they are the regression tests for this whole class of bug:**
- The full path above end to end: two actions, both challenged, first resolves out of mandate — the
  second challenge is **rejected at `challenge()`**.
- The in-flight case: two challenges both opened *before* either resolves, both resolving out of
  mandate — assert via the payout-capture hook that the bond is paid **exactly once**, that the
  second challenger's deposit is still returned, and that the second verdict is still recorded.
- Sum every captured payout across the scenario and assert it never exceeds bond + deposits paid in.
  That assertion is the one that would have caught this, and it belongs in the suite permanently.

**Also fix while you are in there (minor, not a blocker):** `_coerce_verdict` accepts a negative
`severity`, which then reaches `u256(int(...))` in settlement and raises *after* `emit_transfer` has
been called. The transaction reverts as a whole so no money moves, but the failure is unexplained and
happens at the worst possible moment. Clamp `severity` into `0–100` at coercion time.

Write these into the CP4 entry (or a short `FIX-1` entry ahead of it) with the payout sums pasted.

---

## 3. STEP 8 — integration and deployment (CP4)

Per `AGENT_INSTRUCTIONS.md` STEP 8, plus:

**Check whether studionet's deploy path has recovered before assuming either way.** At CP2b it was
erroring network-wide — a re-deploy of the known-good STEP 2 probe failed identically
(`Position '32' is out of bounds`) while reads against already-deployed contracts still worked. If it
is still down, **write the integration tests anyway and report them as existing-but-unrun.** Do not
fake a pass, and do not quietly skip the step.

Three things this step must settle that direct mode could not:

1. **Real balance movement.** Direct mode cannot move balances (D11), so everything you have proven
   about settlement so far is payout *intent*. This is where it becomes real: assert principal,
   operator, challenger and contract balances before and after, for **both** verdict directions.
   Remember payouts execute **on finalization**, not immediately — wait for it rather than asserting
   too early and calling it a failure.
2. **Storage-copy behaviour inside the non-deterministic block.** `resolve()` reads `mandate.text`
   and the action fields into locals rather than calling `gl.storage.copy_to_memory()`. For plain
   `str` fields that is very likely fine, and direct mode is happy — but direct mode is not GenVM,
   and a lazy storage proxy crossing into the nondet block would fail only here. **If it fails, that
   is the finding, not a nuisance:** switch to `copy_to_memory()` and record it.
3. **Deploy the D10 view-clock probe** (`scratch/step4_probe/view_clock.py`) and close the one open
   verification item from CP2b.

**Confirm the hosted network name from the installed tooling, do not trust the docs** — they show
both `testnet_bradbury` and `testnetAsimov`, while the working aliases are hyphenated
(`studionet`, `localnet`, `testnet-asimov`, `testnet-bradbury`).

Fix failures in the contract, never by weakening a test. A test that passes in direct mode and fails
under real consensus is the most valuable thing this step can produce.

**CP4 entry:** network name, contract address, full test results, and the answers to (1) and (2).

---

## 4. STEP 9 — frontend wiring (CP5a)

Per `AGENT_INSTRUCTIONS.md` STEP 9. Use the boilerplate's existing patterns and stack — Next.js 15,
TanStack Query, the existing `WalletProvider` and client. **No new frameworks, no redesign.**

Bindings for every method the UI needs: `register_mandate`, `record_action`, `challenge`, `resolve`,
and the views — including `required_deposit`, which the UI **reads** rather than computing
client-side (that was the whole point of adding it at STEP 4).

Two things that will bite:
- Payable calls must actually send `value`. Prove it with a round trip: register a mandate with a
  bond from the browser and read it back.
- On a fee-charging deployment, estimate the protocol fee separately from the bond.

---

## 5. STEP 10 — the three UI surfaces (CP5b)

Exactly the three surfaces `README.md` names. **No fourth surface. If you find yourself adding one,
stop and report instead.**

1. **Mandate editor** — plain-English mandate, spend ceiling, bond, submit.
2. **Action feed** — merchant URL, item, price, timestamp, and current state per action.
3. **Challenge button + verdict view** — challenge inside the window with the deposit attached, then
   display `within_mandate`, `clause_violated`, `severity`, `reasoning`, and the resulting slash or
   release.

Specific to what we have built:

- **Derive "window elapsed, unchallenged" in the UI**, from `challenge_closes_at` against wall clock.
  That is D10's chosen branch; the contract will not advance that state for you.
- **Say what the contract actually enforces.** An action can be challenged **once ever**, not once at
  a time — the stored field is named `open_challenge_id` and the error text says "one open challenge
  per action", but the code is stricter. Label the button honestly ("Already adjudicated", not
  "Challenge pending").
- **Show the payouts from `get_challenge`** (D12), including FIX-1's already-slashed case. If the
  bond was gone, the verdict view must say so rather than showing a slash that never happened.
- Legible on a projector. This is judged on video.

---

## 6. STEP 11 — demo agent and rehearsal (CP6)

Per `AGENT_INSTRUCTIONS.md` STEP 11. The scripted agent is a **standalone script, not part of the
contract**: register a mandate with a bond, record the compliant action, then record the deliberately
drifting one from `DESIGN_DECISIONS.md`.

- **Time every stage** and record a timing table. The demo has to fit the 90-second slot referenced
  in `pitch.md`. Settlement **finalises** rather than completing instantly — put that in the timeline
  rather than discovering it on camera.
- **Two clean consecutive end-to-end runs from a clean state.** Once is an anecdote.
- **Re-probe the demo listing URL before rehearsing.** A probe recorded 2806 bytes against 2814 from
  curl — most likely CRLF/LF, but confirm the freeze actually held before building a demo on it.
  Confirm the fallback URL works too.
- **No hidden shortcuts — validators must genuinely fetch the live page.** If a stage is too slow for
  the video, report the timing and let me decide what to cut. Do not speed it up by faking a fetch.

**CP6 entry:** the timing table, both runs, and anything that failed or merely looked fragile. Say so
if a stage worked but felt like it might not next time — that is exactly the thing I need before a
live demo, and it is not a failure to report it.

---

## 7. Environment — unchanged, repeated because it bites

- Prefix lint/test commands with `PYTHONIOENCODING=utf-8` or `genvm-lint` crashes *after passing*.
- **Do not remove `_patch_windows_stdin_injection()` from `tests/direct/conftest.py`.** Load-bearing.
- Keep the pinned runner header; ignore the linter's "newer runner available" note (PM ruling).
- Use the canonical `gl.vm.run_nondet_unsafe` spelling — the E010 reachability rule does not
  recognise the `glvm` alias (your CP3a finding).
- **Do not construct `TreeMap()` in `__init__`** — you proved why at CP2a.
- `gl.vm.UserError`, never a bare `Exception`. `u256`, never `int`, in storage. No floats on the
  value path.
- Direct-mode fixtures (`direct_alice` etc.) are **raw bytes** — use `"0x" + direct_bob.hex()`.
- `gl.get_contract_at(...)`, not `gl.contract_at`. `emit_transfer` raises on a zero value.
- Venv: `source .venv/Scripts/activate`. Baseline `9b32b7d`. Commit in logical units.
- `scratch/` must never ship in the public repo at STEP 12.

---

## 8. Definition of done for this packet

- **FIX-1 done first**, with all three regression tests including the payout-sum assertion.
- STEP 8: integration suite written; run if the network allows; real balance assertions in both
  directions; the storage-copy question answered; view-clock probe deployed; address and network
  recorded.
- STEP 9: wallet connects, a bonded mandate registers from the browser and reads back.
- STEP 10: the three surfaces, and only those three, drivable end to end with no CLI.
- STEP 11: two clean consecutive rehearsals with a per-stage timing table.
- `PYTHONIOENCODING=utf-8 genvm-lint check contracts/mandate_guard.py` → clean.
- `PYTHONIOENCODING=utf-8 pytest tests/direct/ -v` → all green, **including the 99 that already
  pass**.
- `CP4`, `CP5a`, `CP5b`, `CP6` entries in `PROGRESS.md`, each with real output, not descriptions.
- **Then stop and wait for PM review.** Do not start STEP 12 — publishing is mine to approve.

Deadline **17 Sep 15:30 UTC**; day 3 of 15, and the contract is feature-complete. That margin exists
so problems can be surfaced early — spend it on reporting a fragile stage, not on quietly working
around one.
