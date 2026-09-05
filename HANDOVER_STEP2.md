# Handover — STEP 2 (Design lock, checkpoint CP1)

**For:** the coding agent · **From:** PM · **Date:** 2026-09-05
**Hand this file to the agent along with the repo.** It is self-contained.

---

## 1. Read these first, in this order

| File | What it is |
|---|---|
| `README.md` | The design. The source of truth for scope. Not written by you, do not edit. |
| `PROJECT_ROADMAP.md` | The plan of record — phases, decision register (§4), verified technical constraints (§5). |
| `AGENT_INSTRUCTIONS.md` | Standing rules + your task. **You are executing STEP 2 only.** |
| `PROGRESS.md` | What happened so far. Read entries CP-INIT through CP0-D. |

Your task is the **STEP 2** block in `AGENT_INSTRUCTIONS.md`. This file does not replace it — it adds environment facts learned since it was written.

---

## 2. Environment state — verified, current

STEP 1 is complete. The toolchain is proven working. Specifics you need:

**Repo**
- Git is initialised. Baseline commit `c3e71c6`, working tree clean. Commit your work in logical units so the PM can review diffs.
- Python venv at `.venv/`. Activate with `source .venv/Scripts/activate` (Git Bash on Windows).

**Versions actually installed** — Python 3.14.3, Node v24.13.1, npm 11.8.0, Docker 29.4.3, GenLayer CLI 0.39.2, genlayer-py 0.18.0, genlayer-test 0.29.2, genvm-linter 0.11.1rc2.

**Network: use `studionet`, not localnet.**
- Active network is already set to `studionet` → `https://studio.genlayer.com/api`, chainId `61999`.
- Local Studio is **broken on this machine** and is not worth fixing — the CLI's default localnet image (`v0.65.0`) ships a `genvm-modules` binary that rejects its own generated config (`missing field 'session_create_request'`), crashing consensus for every transaction. Full diagnosis in `PROGRESS.md` CP0-C. PM decision: use hosted Studio. Do not spend time on localnet.
- `studionet` is shared and rate-limited. Expect occasional slowness; don't mistake it for a bug in your code.
- Real network aliases are **hyphenated**: `localnet`, `studionet`, `testnet-asimov`, `testnet-bradbury`. The docs inconsistently show `testnet_bradbury` / `testnetAsimov` — those are wrong. Verified from `genlayer network list`.

**Two Windows-specific gotchas that will waste your time if you don't know them**
1. **Always prefix lint/test commands with `PYTHONIOENCODING=utf-8`.** `genvm-lint` prints a `✓` character that the default Windows console codepage (cp1252) cannot encode; without this the command crashes with `UnicodeEncodeError` *after the check has already passed*, which looks like a lint failure but isn't.
   ```
   PYTHONIOENCODING=utf-8 genvm-lint check contracts/<file>.py
   PYTHONIOENCODING=utf-8 pytest tests/direct/ -v
   ```
2. **`tests/direct/conftest.py` contains a load-bearing patch — do not remove or "clean up" `_patch_windows_stdin_injection()`.** It fixes a genuine bug in gltest v0.29 (and v0.30.0-rc.2) where the direct-mode loader deletes a temp file that is still open via fd 0. POSIX allows that; Windows does not. Without the patch, **every** direct-mode test fails with `WinError 32`. With it, 43/43 pass. If you add direct tests in a new directory, that directory needs the same patch.

**Known-broken vendor sample code — leave it alone**
The boilerplate's own `tests/integration/` suite has three pre-existing bugs (wrong import name `default_account`, missing Pillow dependency, and direct-mode tests misfiled under `integration/`). PM decision: **do not fix these.** `contracts/football_bets.py` and its tests are the vendor's demo and get deleted once Mandate Guard's contract exists. Do not let them distract you.

**Disposable artifact:** sample contract deployed at `0x7D54428359B69686C9A8Cbd9b4499F22F8c808De` on studionet (5/5 validators AGREE). Proof the pipeline works. Not ours, don't build on it.

---

## 3. Your deliverable

One file: **`DESIGN_DECISIONS.md`**, covering the seven items in `AGENT_INSTRUCTIONS.md` STEP 2.

**You are confirming decisions, not making them.** D1–D4 are already ruled on by the PM in `PROJECT_ROADMAP.md` §4. Your job is to verify each is *implementable as written* and say how. If one is not implementable, **say so explicitly, explain why, and stop** — the PM picks the alternative, not you.

Specific research you actually need to do:

- **D1 (challenge window)** — the roadmap says 24h production / 120s demo mode, contract-configurable. You must determine **how a contract reads current time deterministically** and state the mechanism you verified, with a source. There is a `datetime` field on the transaction message that looks relevant — verify it, don't assume it. Confirm it is consensus-safe (identical across validators for a given transaction), because the whole challenge-window mechanism depends on that.
- **D2 (bond sizing)** — bond ≥ mandate spend ceiling, 1:1. State how the ceiling gets supplied at `register_mandate` and how it's validated. Remember `int` is forbidden in storage; use `u256`, wei-denominated.
- **D3 (challenger deposit)** — 10% of bond, forfeited on a failed challenge, one open challenge per action. Confirm the arithmetic works in `u256` with no floating point.
- **D4 (equivalence fields)** — `within_mandate` exact, `clause_violated` semantic, `severity`/`reasoning` excluded. This one is already settled by the docs (see `PROJECT_ROADMAP.md` §5) — just confirm you understand it and restate the mechanism (`gl.vm.run_nondet_unsafe` with an independently re-deriving validator; **never** `prompt_non_comparative` for the verdict).
- **Demo scenario** — one plain-English mandate containing a judgment clause (`README.md`'s "prefer refundable" is the model), one compliant action, one deliberately drifting action.
- **Verdict schema** — exactly `within_mandate`, `clause_violated`, `severity`, `reasoning`, matching `README.md`.

---

## 4. New PM ruling — D5, demo listing URL

This is the project's **highest external risk** and I'm closing it now so you don't dither.

**Ruling: use a listing page we control as the primary demo URL** — a static page published via GitHub Pages or `raw.githubusercontent.com`, representing the merchant listing (item, price, refundable/non-refundable terms).

Rationale: real merchant sites are hostile to this demo — bot detection, JS-heavy rendering, A/B tests, prices that move, and pages that may simply differ by the time judging happens on 25 Sep. A controlled page removes all of that while changing **nothing** about the mechanism being demonstrated: validators still perform a genuine live fetch of a real public URL over the open internet and genuinely agree or disagree on what they read. That is the claim `README.md` makes, and it remains true.

Two obligations that come with this ruling:
1. **Also verify one genuinely third-party public page fetches correctly** (something stable and static). You don't have to build the demo on it — just prove the contract reads the real web, and record the result. This is what lets us say "works on the real web" honestly.
2. **Be transparent in the submission** that the demo merchant page is one we host. Do not imply otherwise. If a judge asks, the answer should already be in the README.

Pick a **fallback URL** as well, per the original STEP 2 task.

Verify every URL you choose is reachable **from Studio's infrastructure**, not just from this machine — the fetch happens validator-side. Record for each URL whether `gl.nondet.web.get()` suffices or `gl.nondet.web.render()` is needed.

---

## 5. Rules that matter most

1. **Scope is closed.** Build only what `README.md` describes. Something missing? Report it, don't add it.
2. **Never guess.** Verify against https://docs.genlayer.com or the installed tooling. Can't verify? Stop and report.
3. **No silent substitutions.** Tool/network/library unavailable → report it, don't swap in your own alternative.
4. **STEP 2 writes no contract code.** It is a design-lock step. Do not start implementing `register_mandate` — that's STEP 3, and it needs PM sign-off on your `DESIGN_DECISIONS.md` first.
5. **Do not edit** `README.md`, `PROJECT_ROADMAP.md`, `AGENT_INSTRUCTIONS.md`, `pitch.md`, or this file. `PROGRESS.md` is **append-only**.

---

## 6. Definition of done

- `DESIGN_DECISIONS.md` exists and covers all seven items plus D5.
- Every URL confirmed reachable, with its required fetch method recorded.
- The time mechanism for D1 is verified against a real source and cited.
- A `CP1` entry appended to `PROGRESS.md` using that file's template: one line per decision, the chosen URLs, real evidence (commands and their actual output), and any blockers.
- **Then stop and wait for PM review.** Do not begin STEP 3.

If you hit a blocker, an ambiguity, or anything requiring a deviation from the roadmap — stop immediately, write a `BLOCKED` entry in `PROGRESS.md`, and wait. A blocker reported early costs an hour; one found at the deadline costs the project. Deadline is **17 Sep 15:30 UTC**; we are on day 3 of 15.
