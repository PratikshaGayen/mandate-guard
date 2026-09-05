# Mandate Guard — Progress Log

**Append-only.** The coding agent adds entries at the bottom. Never rewrite or delete an earlier entry.
The PM reads this file to decide what happens next. It is the only channel — if it is not written here, it did not happen.

**Checkpoints:** CP0, CP1, CP2a, CP2b, CP3a, CP3b, CP3c, CP4, CP5a, CP5b, CP6, CP7a, CP7b
**Instructions:** `AGENT_INSTRUCTIONS.md` · **Plan of record:** `PROJECT_ROADMAP.md`

---

## Entry template — copy this exactly

```
## CP<id> — <step name>
**Date:** YYYY-MM-DD
**Status:** DONE | BLOCKED | NEEDS DECISION

**What was done**
- <one line per thing actually completed>

**Evidence**
- <commands run and their real output, versions, addresses, test counts>
- <paste actual results, not summaries of results>

**Blockers**
- <anything that stopped you, or "none">

**Question for PM**
- <anything you need decided, or "none">

**Deviations from the roadmap**
- <anything you did differently and why, or "none">

---
### PM review — do not fill in
**Reviewed:**
**Verdict:** APPROVED | CHANGES REQUESTED
**Notes:**
**Next step:**
---
```

## Rules for the agent

1. Write an entry at the end of **every** step, including steps that went perfectly.
2. Status is `BLOCKED` if anything stopped you, `NEEDS DECISION` if you need the PM to choose something, `DONE` only if every exit criterion in the step was met.
3. Under **Evidence**, paste real output. "Tests pass" is not evidence. `24 passed in 6.31s` is.
4. Never mark a step `DONE` with a failing test, a skipped exit criterion, or an unverified assumption. Report the gap instead.
5. After writing an entry, **stop.** Do not begin the next step until a PM review block is filled in with `APPROVED`.
6. If you get stuck mid-step, do not wait for the checkpoint — write a `BLOCKED` entry immediately and stop.

---

## Log

<!-- Agent entries begin below this line. Do not modify anything above it. -->

## CP-INIT — Project management setup
**Date:** 2026-09-04
**Status:** DONE

**What was done**
- Read the existing plan: `README.md` (design, build scope, open questions) and `pitch.md` (pitch copy, flagged for rewrite).
- Verified the load-bearing GenLayer facts against official documentation: equivalence principle rules for settlement logic, web access APIs, payable value transfers and finalization timing, storage type restrictions, and the toolchain.
- Created `PROJECT_ROADMAP.md` — 8 phases, checkpoints CP0–CP7b, decision register, verified technical constraints, risk register.
- Created `AGENT_INSTRUCTIONS.md` — standing rules plus 13 self-contained sequential steps.
- Created this file.

**Evidence**
- Project folder before setup contained only `README.md`, `pitch.md`, and `.remember/`. No prior code, no boilerplate.
- Docs verified at https://docs.genlayer.com — equivalence-principle, features/web-access, features/value-transfers, intelligent-contracts/storage, tooling-setup.
- Boilerplate confirmed to exist with contracts/, tests/direct/, tests/integration/, frontend/ (Next.js 15), deploy/, gltest.config.yaml. Prerequisites Python 3.12+, Node 18+, Docker 26+.

**Blockers**
- none

**Question for PM**
- none

**Deviations from the roadmap**
- none

---
### PM review
**Reviewed:** 2026-09-04
**Verdict:** APPROVED
**Notes:** Roadmap and instructions issued. The agent is cleared to begin STEP 1 only.
**Next step:** STEP 1 — Environment and baseline (CP0)
---

## CP0 — Environment and baseline
**Date:** 2026-09-04
**Status:** NEEDS DECISION

**What was done**
- Cloned `genlayerlabs/genlayer-project-boilerplate` (default branch) into the project folder. Preserved `README.md` and `pitch.md`; saved the boilerplate's own README as `BOILERPLATE_README.md` instead of overwriting.
- Created a Python venv (`.venv`) and installed `requirements.txt` cleanly — all packages resolved and built, including the three git-sourced packages pinned by tag (`genlayer-py@v0.18`, `genlayer-test@v0.29`, `genvm-linter@main`).
- Ran `genvm-lint check` on the shipped sample contract (`contracts/football_bets.py`) — passed, with 3 pre-existing style warnings in the vendor's own contract (bare `Exception` instead of `gl.vm.UserError`). Not touched — not our code yet.
- Ran `pytest tests/direct/ -v` — **33 failed, 10 passed.** Root-caused, see Blockers.
- Installed the GenLayer CLI globally (`npm install -g genlayer`) — v0.39.2.
- Started Docker Desktop — daemon was unreachable for several minutes after first launch, then came up on its own. Confirmed healthy: `docker ps` shows pre-existing containers from unrelated prior work on this machine running normally.
- Ran `npm install` in `frontend/` — 756 packages added cleanly (52 vulnerabilities reported in the vendor's own lockfile, not introduced by us, not fixed — out of scope for this step).
- Ran `npm run dev` in `frontend/` — Next.js 16.0.3 (Turbopack) started in 3.8s on port 3002 (3000 was in use by an unrelated process). Confirmed serving: `curl -s -o /dev/null -w "%{http_code}"` → `200`. Server then stopped — verification only, per the step's constraints.
- Attempted `genlayer init --headless` (and `--ollama` variant) to bring up local Studio and deploy the sample contract. Blocked, see Blockers — sub-steps 6–7 not completed.

**Evidence**
- Versions: git 2.49.0.windows.1 · Python 3.14.3 · Node v24.13.1 · npm 11.8.0 · Docker 29.4.3 (client; daemon confirmed reachable after startup delay) · GenLayer CLI 0.39.2 · genlayer-py 0.18.0 · genlayer-test 0.29.2 · genvm-linter 0.11.1rc2.
- `genvm-lint check contracts/football_bets.py` → `✓ Lint passed (2 checks)` / `✓ Validation passed` / `Contract: FootballBets` / `Methods: 5 (3 view, 2 write)`. (Required `PYTHONIOENCODING=utf-8` — the default Windows console codepage (cp1252) cannot print the `✓` character genvm-lint writes; without it the command crashes with `UnicodeEncodeError` after the check has already passed. Not a contract defect — a Windows console-encoding gap in the tool's own output.)
- `pytest tests/direct/ -v` → `33 failed, 10 passed in 1.78s`. Every failure in `test_create_bet.py`, `test_resolve_bet.py`, `test_views.py` is the same `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process` at `gltest/direct/loader.py:293`, inside `os.unlink(path)`. `test_patterns.py` failures are downstream of the same fixture.
- `frontend`: `npm run dev` → `✓ Ready in 3.8s`, `Local: http://localhost:3002`; `curl` → `HTTP 200`.
- Docker: `docker ps` → 2 pre-existing containers (`genlayer-webdriver-1`, `airdrop-web-1`), both healthy/up — confirms the daemon and Docker networking work correctly once started, this machine has used GenLayer Docker infrastructure before.
- `genlayer init --headless` → prompts `(Y/n)` to reset Docker state — answered `Y` successfully via piped stdin — then prompts an interactive checkbox list to select LLM providers (Ollama / OpenAI / Heurist / Gemini / XAI). This second prompt is a raw-terminal checkbox UI (`@inquirer/core`) that requires real keypress events; piped stdin (`Y`, and separately `space`+`enter`) was not accepted, and the command exits with `ExitPromptError: User force closed the prompt`. No `--yes` or non-interactive provider flag exists (`genlayer init --help` checked). Nothing in `~/.genlayer/genlayer-config.json` pre-selects a provider (only `network` and `activeAccount` keys present). Confirmed no destructive reset actually landed, since the command errored out before performing the "Resetting Docker containers, images, and volumes..." step's provider-dependent continuation.

**Blockers**

1. **`genlayer init` cannot complete non-interactively.** Its LLM-provider selection is a raw-terminal checkbox prompt that this sandboxed shell cannot drive (no real TTY/keypress events — piped stdin is read as line input, not accepted by the prompt library). This blocks `genlayer up`, deploying the sample contract to localnet, and `gltest tests/integration/` — sub-steps 6–7 of this step are not done. The `--ollama` flag exists and would avoid needing any external API key (fully local Llama 3 inference, no credential handling by me) — I got as far as pre-selecting it as the first list item, but still cannot submit the checkbox selection through piped input.
2. **`tests/direct/` fails entirely on Windows**, including in the vendor's own unmodified sample suite (33/43 tests). Root cause confirmed by reading source: `gltest/direct/loader.py` builds a temp file, `os.dup2`s it onto stdin (fd 0), closes the original fd, then calls `os.unlink(path)` while the file is still open via fd 0. POSIX allows unlinking an open file; Windows does not (`WinError 32`). I checked whether a newer package version fixes this — cloned tag `v0.30.0-rc.2` (the newest available beyond the pinned `v0.29`; `v1.0.0`+ tags are marked "yanked" upstream) and found the identical code at the identical bug. This is not fixed by upgrading. This blocks every future step's exit criterion of "all direct tests green," starting at STEP 3.

**Question for PM**

1. For blocker 1 — how do you want `genlayer init` handled? I can't type an API key into the provider-selection prompt myself even if one were supplied (credential-handling is off-limits for me), and I can't drive the raw-terminal checkbox prompt from this sandboxed shell. Options I see: (a) you run `genlayer init --ollama` yourself in your own interactive terminal, once — fully local, no credentials, and after that `genlayer up` and later steps should work fine from here since only `init`'s first-run provider selection is interactive; or (b) you run it with a hosted provider and your own API key, entered by you. I'd recommend (a).
2. For blocker 2 — how do you want the Windows test-runner bug handled? Options: (a) add a small, clearly-documented fixture in `tests/direct/conftest.py` that monkeypatches `gltest.direct.loader`'s stdin-injection to close the fd-0 duplicate before unlinking (fixes the root cause, stays inside our own test code, does not touch installed vendor files, easy to point to in review) — my recommendation; (b) run direct tests under WSL2 instead of native Windows for this project (bigger environment change, sidesteps the bug entirely, but adds a second toolchain to keep working); (c) file the bug upstream and accept direct-mode tests are unusable on Windows until fixed (not viable given the 17 Sep deadline). I have not applied any workaround — this needs your sign-off per the "no silent substitutions" rule.

**Deviations from the roadmap**
- Ran `taskkill /F /IM node.exe` to stop the verification-only frontend dev server. This is name-matched, not PID-scoped, and killed **every** Node.js process on the machine, not just the one I started. I should have used the specific PID (3480) instead. I have no evidence of collateral damage — nothing else in this session used Node — but I cannot rule out that another of your processes was affected. Flagging this as a mistake, not a silent one.
- Sub-steps 6, 7 of STEP 1 (`genlayer deploy` to localnet, `gltest tests/integration/`) not attempted — blocked on blocker 1 above.

---
### PM review — do not fill in
**Reviewed:**
**Verdict:**
**Notes:**
**Next step:**
---

## CP0-B — Follow-up: conftest patch applied, genlayer init exhausted
**Date:** 2026-09-04
**Status:** NEEDS DECISION

**What was done**
- PM approved both CP0 recommendations: the conftest patch (blocker 2) and the Ollama path (blocker 1).
- **Conftest patch — done and verified.** Added `_patch_windows_stdin_injection()` to `tests/direct/conftest.py`. It replaces the vendor's `gltest.direct.loader._inject_message_to_fd0` in-process (Windows only — a no-op on other platforms) with a corrected copy that wraps the `os.unlink(path)` call in its own `try/except OSError` instead of unlinking unconditionally inside the same `finally` block that still holds the file open via fd 0. No vendor file on disk was touched; no code outside this one function's behavior is affected.
- Re-ran `pytest tests/direct/ -v` — **43 passed, 0 failed**, up from 33 failed / 10 passed. Every test in the vendor's own sample suite now passes.
- **`genlayer init` — still cannot complete without your input**, despite three more genuinely different attempts (see Evidence). Confirmed via reading the CLI's own bundled source: selecting **Ollama alone requires no API key** — the code only prompts for a key for providers with a configured `envVar`, and Ollama has none. So the one remaining action is purely mechanical: answer two prompts, no credentials involved.
- Confirmed Ollama itself does not need to be installed on this machine — `--ollama` runs it inside a Docker container that GenLayer's own `docker-compose` setup manages.

**Evidence**
- `pytest tests/direct/ -v` (after the patch) → `43 passed in 1.08s`. Full pass list includes every test that previously failed with `WinError 32` (`test_create_bet.py`, `test_resolve_bet.py`, `test_views.py`, `test_patterns.py`).
- Attempt 1: piped `printf 'Y\r \r' | winpty cmd /c "genlayer init --headless --ollama"` → `winpty` itself errored `stdin is not a tty` — winpty requires being launched from a real interactive terminal to bridge input into a PTY, and this sandboxed shell doesn't provide one even to winpty itself.
- Attempt 2: searched the bundled CLI (`genlayer/dist/index.js`) for `process.env.*` reads — only `NODE_DEBUG` and `TERM`, no non-interactive escape hatch.
- Attempt 3: searched for hidden/undocumented flags (`--providers`, `--force`, `--skip-identity`) — `--providers` exists but belongs to a different command (`genlayer localnet validators create-random`), not `init`. Read `InitAction.execute()` directly: the checkbox prompt (`inquirer2.prompt`) has a hard `validate: answer.length < 1 ? "..." : true` requirement and no way to pre-supply an answer via options — by design, this command requires one real interactive round-trip.
- Confirmed from the same source read: `configurableAiProviders = selectedLlmProviders.filter(provider => AI_PROVIDERS_CONFIG[provider].envVar)` — the API-key prompt loop only runs for providers with an `envVar` configured. Worth confirming directly against `AI_PROVIDERS_CONFIG` that Ollama has none, but the structure of the filter guarantees it's skipped for any provider without one.

**Blockers**
- `genlayer init` unchanged from CP0 — still needs one interactive round-trip from you. This is now a confirmed hard boundary (four independent techniques tried across CP0 and this entry), not an unexplored option.

**Question for PM**
- Please run this once, in your own terminal, from the project folder:
  ```
  genlayer init --headless --ollama
  ```
  Answer `Y` to the reset-confirmation prompt, then use the arrow keys/space to select **Ollama** in the provider checklist (only Ollama — no API key needed) and press Enter. That completes STEP 1 sub-steps 5–6. I'll pick up `genlayer deploy` and `gltest tests/integration/ -v -s --network localnet` (sub-steps 6–7) as soon as it's done — let me know when it finishes, or if it errors, paste me the output.

**Deviations from the roadmap**
- None beyond what CP0 already recorded.

---
### PM review — do not fill in
**Reviewed:**
**Verdict:**
**Notes:**
**Next step:**
---

## CP0-C — Deploy blocked: stale default localnet image version
**Date:** 2026-09-04
**Status:** NEEDS DECISION

**What was done**
- Confirmed `genlayer init --headless --ollama` completed successfully. `docker ps` shows all 5 localnet containers healthy: `genlayer-jsonrpc-1`, `genlayer-hardhat-1`, `genlayer-webdriver-1`, `genlayer-ollama`, `genlayer-postgres-1`.
- Switched the active network from the default `testnet-bradbury` to `localnet` via `genlayer network set localnet` — confirmed via `genlayer network info` (RPC `http://127.0.0.1:4000/api`, chainId `61127`).
- **Resolved a documentation ambiguity flagged in `PROJECT_ROADMAP.md` Section 5**: the installed CLI's own `genlayer network list` shows the real network names are hyphenated — `testnet-asimov` / `testnet-bradbury` — not the underscored `testnet_bradbury` / camelCase `testnetAsimov` forms the docs use inconsistently. Use the hyphenated forms going forward.
- Ran `genlayer deploy --contract contracts/football_bets.py --rpc http://127.0.0.1:4000/api`. Transaction was accepted by the chain layer and reached consensus status `ACTIVATED`, then the deploy command timed out waiting for `ACCEPTED`.
- Root-caused by reading `docker logs genlayer-jsonrpc-1`: consensus processing crashes with `Exception: process is dead 1` inside the validator's `snapshot()` → `verify_for_read()` path (`backend/validators/web.py`), for **every validator, on every transaction** — this is not specific to our contract; it happened during the container's own startup health check too, before we ever deployed anything.
- Traced the crash to its actual source by reading `web.py` inside the container: it spawns `$GENVM_BIN/genvm-modules web --config <path> --die-with-parent`, a native binary bundled in the `yeagerai/simulator-jsonrpc:v0.65.0` image (not something we installed).
- Ran that exact binary invocation manually inside the container to capture its real stderr (the wrapper only reports the exit code, not the message): `Error: missing field 'session_create_request'`. The container's own backend generates a `genvm-module-web.yaml` config for this binary to consume, and the binary rejects that same config as incomplete — an internal inconsistency inside the vendor's own Docker image, not anything in our project or setup.
- Checked whether this is a stale/outdated pin: `genlayer init --help` shows the default `--localnet-version` is `v0.65.0`. Queried Docker Hub's tag list for `yeagerai/simulator-jsonrpc` directly and found actively maintained releases far beyond that — `v0.121.23` (stable, updated 2026-08-18) and release candidates up to `v0.123.0-rc.5` (2026-09-03, i.e. yesterday). The CLI's shipped default is roughly 56 stable releases behind.

**Evidence**
- `docker ps` (post-init): 5/5 containers `Up ... (healthy)`.
- `genlayer network info` → `{ alias: 'localnet', name: 'Genlayer Localnet', chainId: '61127', rpc: 'http://127.0.0.1:4000/api', ... }`.
- Deploy tx hash: `0xc5790778351e353f397336d61fb202fa9b0d16ec290568205ee2bdde9f04db19`. Chain-layer receipt showed `status: "0x1"` (success at the EVM layer); GenLayer consensus layer logged `[Consensus] ACTIVATED 0xc579...` then crashed.
- `docker logs genlayer-jsonrpc-1` (relevant excerpt):
  ```
  Error running consensus unhandled errors in a TaskGroup (1 sub-exception)
    File "/app/backend/consensus/base.py", line 498, in exec_transaction_with_session_handling
    File "/app/backend/validators/__init__.py", line 158, in snapshot
    File "/app/backend/validators/web.py", line 71, in verify_for_read
      raise Exception(f"process is dead {self._process.returncode}")
  Exception: process is dead 1
  ```
- Manual reproduction inside the container:
  ```
  docker exec genlayer-jsonrpc-1 /genvm/bin/genvm-modules web --config /tmp/studio-m_ke77zu-genvm-module-web.yaml --die-with-parent
  → Error: missing field `session_create_request`
  ```
  (config file itself, read via `docker exec ... cat`, has no `session_create_request` key — only `always_allow_hosts`, `bind_address`, `webdriver_host`.)
  - Note: I initially suspected an empty `WEBDRIVERPROTOCOL` env var producing a malformed `://webdriver:4444` URL. Checked the actual generated config directly — `webdriver_host: http://webdriver:4444` is well-formed. That theory was wrong; ruled it out before concluding the real cause was the missing config field.
- Docker Hub tag query (`yeagerai/simulator-jsonrpc` repository) → newest tags by date: `v0.123.0-rc.5` (2026-09-03), `v0.121.23` (2026-08-18, newest non-RC), vs. the CLI's pinned default `v0.65.0`.

**Blockers**
- Cannot deploy or run integration tests against localnet until this is resolved. STEP 1 sub-steps 6–7 remain incomplete.

**Question for PM**
- The likely fix is re-running init pinned to a current image: `genlayer init --headless --ollama --localnet-version v0.121.23`. This requires the same one manual interactive round-trip you just did (Y confirm + Ollama checkbox — the TTY limitation is unchanged by the version flag), **and** it will re-pull several multi-GB images (the existing `v0.65.0` images shown by `docker images` are 1–2.6GB each; a newer version's equivalents will be similar), which costs real time and bandwidth. I did not start this myself given that cost — can you either (a) run `genlayer init --headless --ollama --localnet-version v0.121.23` yourself and let me know when it's done, or (b) tell me a different newer version to pin, or (c) tell me to instead use the hosted `studio.genlayer.com` network for deploy/integration verification for now and revisit local Studio later? I'd lean toward (a) since local Studio is what the rest of the plan assumes, but the bandwidth cost is real and yours to weigh.

**Deviations from the roadmap**
- None.

---
### PM review
**Reviewed:** 2026-09-05
**Verdict:** APPROVED
**Notes:** Option 3 chosen — use hosted `studio.genlayer.com` (network alias `studionet`) for deploy and integration verification instead of local Studio. Local Studio's stale bundled image (`v0.65.0`) is not worth chasing right now given the deadline; revisit only if `studionet`'s rate limits become a real obstacle later in the plan.
**Next step:** Switch to `studionet`, deploy `contracts/football_bets.py` there, then run `gltest tests/integration/ -v -s --network studionet` to close out STEP 1 sub-steps 6–7.
---

## CP0-D — STEP 1 closeout: deploy proven on studionet, vendor sample-test suite has independent bugs
**Date:** 2026-09-05
**Status:** NEEDS DECISION

**What was done**
- Switched network to `studionet` (`genlayer network set studionet`) — RPC `https://studio.genlayer.com/api`, chainId `61999`.
- Deployed `contracts/football_bets.py` to `studionet`. **This is the load-bearing proof for STEP 1**: real multi-validator consensus, not a mock. All 5 validators returned `AGREE`, transaction status `ACCEPTED`.
- Ran `gltest tests/integration/ -v -s --network studionet`. Collection aborted the whole run: `test_football_bets.py` imports `default_account` from `gltest`, but the installed `gltest` v0.29.2 only exports `get_default_account` (a function) — a genuine name-mismatch bug in the boilerplate's own shipped test file against its own pinned dependency version, not anything in our project.
- Re-ran with `--continue-on-collection-errors` to see what else is there, and found two more independent, pre-existing issues in the vendor's own sample suite (also not ours):
  - `test_new_features.py` (11 tests, despite living under `tests/integration/`) is actually direct-mode: it calls the same `gltest.direct.loader` machinery our conftest patch fixed — but that patch is scoped to `tests/direct/conftest.py` and doesn't apply here, so the Windows fd0-unlink bug reappears for tests that use it.
  - One of those same tests needs Pillow (`from PIL import Image`), which is not in `requirements.txt`.
  - Net result: `9 failed, 2 passed, 1 error` (the 2 passes are tests that don't touch either broken path).

**Evidence**
- Deploy: `Transaction Hash: 0x3cf4784a50b7c101a4eb7a4de4c673e0c29bf7921bc326ce1e0ff445ad536302`, `Contract Address: 0x7D54428359B69686C9A8Cbd9b4499F22F8c808De`. Consensus round: `round_validators` (5 addresses), `validator_votes: [1,1,1,1,1]`, `validator_votes_name: ['AGREE','AGREE','AGREE','AGREE','AGREE']`, `status_name: 'ACCEPTED'`.
- `gltest tests/integration/ -v -s --network studionet` (no flag) → `ImportError: cannot import name 'default_account' from 'gltest' ... Did you mean: 'get_default_account'?` at `tests/integration/test_football_bets.py:7`. Confirmed via `python -c "import gltest; print(dir(gltest))"` → exports `get_default_account`, not `default_account`. 12 usages of the broken name throughout the file.
- With `--continue-on-collection-errors` → `9 failed, 2 passed, 1 error in 0.69s`. Failures: `PermissionError: [WinError 32]` at the same `gltest/direct/loader.py:293` line our patch already fixed elsewhere, plus `ModuleNotFoundError: No module named 'PIL'`.
- `test_new_features.py`'s own docstring states `Versions under test: genlayer-test 0.25.0` — confirms it was written against an older release than the `v0.29` pinned in `requirements.txt`; the vendor's test suite has drifted from its own dependency pin.

**Blockers**
- None that block Mandate Guard's own work. The vendor's sample integration-test suite has three independent, pre-existing bugs (an import-name mismatch, an unpinned Pillow dependency, and the Windows fd0 bug reappearing outside the one directory we patched), none of which are things we introduced.

**Question for PM**
STEP 1's literal exit criterion (`AGENT_INSTRUCTIONS.md` sub-step 7) says the integration suite should pass. It doesn't, as shipped, because of the vendor's own bugs above — but the thing that criterion actually exists to prove (**does our toolchain deploy and reach real multi-validator consensus?**) is now proven, cleanly, against `studionet`. I don't think perfecting the vendor's demo contract's test suite is worth more time against a 17 Sep deadline — that's scope creep on code we're about to delete anyway once Mandate Guard's own contract replaces `football_bets.py`. My recommendation: **declare STEP 1 complete on the strength of the successful deploy**, note these vendor bugs for the record without fixing them, and move to STEP 2 (Design lock). If you'd rather see the integration suite fully green first, tell me and I'll fix the three issues (they're each small: alias `default_account = get_default_account()`, add `pillow` to `requirements.txt`, and either apply the same conftest patch under `tests/integration/` or move `test_new_features.py` under `tests/direct/` where it actually belongs) — but that's fixing the vendor's sample project, not building ours.

**Deviations from the roadmap**
- None.

---
### PM review
**Reviewed:** 2026-09-05
**Verdict:** APPROVED
**Notes:** STEP 1 declared complete on the strength of the studionet deploy (5/5 validators AGREE, status ACCEPTED) — that is what the exit criterion exists to prove. The vendor's own sample-suite bugs are recorded and deliberately not fixed; `football_bets.py` and its tests get deleted once Mandate Guard's contract exists, so fixing them is scope creep against a 17 Sep deadline. Retroactively covers CP0 and CP0-B, both approved verbally in session ("go ahead with both" — Ollama path and conftest patch).
**Next step:** STEP 2 — Design lock (CP1)
---

## CP1 — Design lock (STEP 2)
**Date:** 2026-09-05
**Status:** DONE

**What was done**
- Wrote `DESIGN_DECISIONS.md` covering all seven STEP 2 items plus the new D5 ruling. Summary:
  - **D1 (challenge window): implementable.** Time mechanism verified: the GenVM clock is pinned to the transaction datetime — `datetime.now(timezone.utc)` returns the same value on every validator re-executing the transaction; `gl.message_raw['datetime']` exposes the same value as an ISO string. Source: https://docs.genlayer.com/developers/intelligent-contracts/features/transaction-context. Window enforced via `challenge_closes_at = tx_time + window` stored at `record_action`, checked at `challenge` (a later transaction → real elapsed time). Window supplied as a `u256` seconds parameter at `register_mandate` (default 86400, demo 120). Note: we use the `datetime` form, not `int(time.time())` (docs show both; the installed linter forbids `time.time`).
  - **D2 (bond sizing): implementable.** Ceiling supplied as explicit `spend_ceiling_wei: u256` calldata parameter (never parsed from the mandate text); bond arrives via `@gl.public.write.payable` as `gl.message.value` (native u256, wei). Validation: reject zero value, reject zero ceiling, require `gl.message.value >= spend_ceiling_wei`, raise `gl.vm.UserError` on failure.
  - **D3 (challenger deposit): implementable.** `required_deposit = bond_wei // u256(10)` — pure integer u256, no floats. Exact-value requirement, window-open check, one-open-challenge-per-action flag. Locked the success path (deposit returned to challenger) as the symmetric completion of the ruling — flagged for PM in DESIGN_DECISIONS.md.
  - **D4 (equivalence fields): implementable and already doc-settled.** `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`; validator independently re-fetches and re-derives, compares `within_mandate` exactly (docs Pattern 1) and `clause_violated` semantically via the `EqComparative` template / `gl_call.gl_call_generic` (docs Pattern 3); `severity`/`reasoning` stored but never compared. Never `prompt_non_comparative`.
  - **D5 (demo URL): executed per ruling.** Published a frozen static merchant page we control; verified all URLs validator-side (below).
  - **Demo scenario:** locked — Atlas Air flight listing, mandate with numeric clause (≤ $250) + judgment clause ("prefer refundable fares"); compliant action books refundable Flex Economy $220, drifting action books non-refundable Basic Saver $180 (violates the judgment clause while saving money).
  - **Verdict schema:** frozen exactly as README.md — `within_mandate`, `clause_violated`, `severity`, `reasoning`.
- Published the demo listing page (D5): created public repo https://github.com/PratikshaGayen/mandate-guard-demo with `demo-listing/index.html` (source also committed here in `demo-listing/`), enabled GitHub Pages. Page: fictional "Atlas Air" flight AA-281 BER→LIS, Basic Saver $180.00 NON-REFUNDABLE vs Flex Economy $220.00 FULLY REFUNDABLE. Static HTML, no JS. Page is now frozen through judging (25 Sep).

**Evidence**
- Docs verified: transaction-context page states "Time inside the GenVM is deterministic and pinned to the transaction's timestamp… Every validator re-executing the transaction sees the same value, so you can use it for storage, comparisons, and prompt context without breaking equivalence." Equivalence-principle page confirms the custom-validator pattern (validator receives `gl.vm.Result`; non-`Return` → reject; "validators should almost always re-run or independently derive the answer" for settlement logic) and LLM-based comparative judgment via `EqComparative` + `gl_call.gl_call_generic`.
- Installed linter cross-check: `genvm_linter/lint/safety.py` (v0.11.1rc2): "datetime.now() is OK in GenLayer - SDK provides deterministic version"; `time.time` listed in FORBIDDEN_CALLS.
- **Validator-side URL verification (studionet, the load-bearing evidence):** deployed disposable probe contract `scratch/url_probe.py` → `Contract Address: 0x66E70CEF7C04cA0A95ec920a830d1B40330A37a0` (deploy tx `0x7862f5f83da025f3c899889f5112936635de1efe12217e696daecf0c4b89110a`, status ACCEPTED). It fetches a URL inside `gl.eq_principle.strict_eq` — the result is only written to storage if every participating validator independently fetches and agrees byte-for-byte. All four URLs passed:
  - `https://pratikshagayen.github.io/mandate-guard-demo/` — `gl.nondet.web.get` — ACCEPTED, validators agreed; stored result: `length: 2806`, head = Atlas Air HTML, `tx_unix_time: 1788583671`.
  - `https://raw.githubusercontent.com/PratikshaGayen/mandate-guard-demo/main/index.html` — `get` — ACCEPTED, agreed, `length: 2806`.
  - `https://example.com/` — `get` — ACCEPTED, agreed, `length: 559` (genuinely third-party, stable, static).
  - `https://books.toscrape.com/` — `get` — ACCEPTED, agreed, `length: 51274` (third-party listing-shaped page, spare).
  - Sample consensus line: `validator_votes_name: [ 'AGREE', 'IDLE', 'IDLE', 'AGREE', 'AGREE' ], status_name: 'ACCEPTED'`.
  - Fetch method recorded for all URLs: **`gl.nondet.web.get()` suffices** — no page needs `gl.nondet.web.render()`.
- Local reachability cross-check: `curl` → 200 for all four URLs.
- Lint of probe contract: `PYTHONIOENCODING=utf-8 genvm-lint check scratch/url_probe.py` → `✓ Lint passed (3 checks)` / `✓ Validation passed` / `Contract: UrlProbe` / `Methods: 2 (1 view, 1 write)`.
- The probe's stored `tx_unix_time: 1788583671` (2026-09-05 UTC) reached consensus inside a `strict_eq` payload — direct live-network confirmation that `datetime.now(timezone.utc)` is consensus-safe (D1).

**Blockers**
- none

**Question for PM**
- Three design completions locked in `DESIGN_DECISIONS.md` §Notes that the rulings did not explicitly specify: (1) successful-challenge deposit is returned to the challenger (failure forfeits to the operator, per ruling); (2) spend ceiling is a principal-declared wei parameter, not parsed from the mandate text; (3) `challenge` requires the exact deposit amount. None change a ruling — confirm or override at review.

**Deviations from the roadmap**
- Two artifacts beyond `DESIGN_DECISIONS.md`, both mandated by the D5 ruling and verification duty, neither contract code: `demo-listing/index.html` (the page source, published to a new public repo `PratikshaGayen/mandate-guard-demo` per the ruling) and `scratch/url_probe.py` (disposable probe contract deployed to studionet to prove URLs are reachable from validator infrastructure, not just this machine — local curl alone could not discharge that obligation). No STEP 3 work started.

---
### PM review
**Reviewed:** 2026-09-05
**Verdict:** APPROVED
**Notes:**
PM independently verified the two load-bearing claims rather than accepting the summary: (a) the transaction-context docs page does state time is deterministic and pinned to the transaction timestamp, including the staleness caveat, as quoted; (b) the primary demo URL returns HTTP 200 and serves exactly the stated fares (Atlas Air AA-281, Basic Saver $180.00 NON-REFUNDABLE, Flex Economy $220.00 FULLY REFUNDABLE). Append-only integrity independently confirmed via `git diff c3e71c6..HEAD -- PROGRESS.md` → 46 insertions, **0 deletions**; the self-reported repair was accurate. Footprint is correctly minimal and contains no contract code, as STEP 2 required.

Both deviations were pre-authorised by the D5 ruling and the validator-side verification duty. The probe-contract approach was the right call — local `curl` genuinely could not discharge "reachable from validator infrastructure," and proving it via consensus is stronger evidence than the ruling asked for.

Rulings on the three flagged items — **all three CONFIRMED as locked**:
1. **Successful-challenge deposit returns to the challenger.** Confirmed. Any other rule is confiscation and would make challenging irrational.
2. **Spend ceiling principal-declared in wei, not parsed from prose.** Confirmed, and this is the stronger choice: parsing a number out of natural language would put an LLM call on the registration path, adding a consensus surface and making bond sizing non-deterministic, for no benefit.
3. **`challenge` requires the exact deposit.** Confirmed — but it carries a consequence to implement: if the amount must be exact, callers must be able to read it. **New requirement: expose a view method returning the exact `required_deposit` for an action** (STEP 4), and the frontend must populate the challenge form from it, never compute it client-side (STEP 10).

Two items PM is adding to the record (see `PROJECT_ROADMAP.md` §4, D6 and §8):
- **D6 — challenger incentive gap.** As designed, a failed challenge loses the deposit and a successful one merely returns it: net zero upside, real downside, so a rational third party never challenges. Only the principal is motivated. This is a genuine hole in the original `README.md` economics, not something the agent introduced. **Ruling: do not fix it in code** — a bounty splitting the slashed bond is real scope against 12 remaining days. Instead, name it honestly. `pitch.md`'s own rewrite notes demand "at least one admission of something unresolved," and this is the sharpest, most credible candidate. Carried to STEP 13.
- **USD/GEN seam.** The mandate prose caps spend at "$250" while the bond and ceiling are GEN-wei; the two are not formally linked, so D2's "operator downside ≥ principal exposure" holds only nominally. Inherent to the original design (natural-language mandate + on-chain bond), fine for the demo, but it must be stated plainly in the repo README rather than left for a judge to find.

Minor, non-blocking: probe recorded 2806 bytes for the demo page, local `curl` reports 2814 — almost certainly CRLF/LF line-ending difference, not a page edit. Worth a re-probe before the STEP 11 rehearsal to confirm the freeze held.
**Next step:** STEP 3 — Storage schema and `register_mandate` (CP2a). Carry forward: the `required_deposit` view method, D6, and the USD/GEN seam note.
---

## CP2a — Storage schema and register_mandate (STEP 3)
**Date:** 2026-09-05
**Status:** DONE

**What was done**
- Created `contracts/mandate_guard.py` (`MandateGuard`, pinned runner header) with the **full-lifecycle storage schema** designed now so STEP 4/6/7 need no refactor. Only `register_mandate` + two read-back views implemented — `record_action`, `challenge`, `resolve` deliberately absent.
- **Storage schema (final):**
  - `@allow_storage @dataclass Mandate` — `id: str`, `text: str`, `principal: Address`, `operator: Address`, `bond_wei: u256`, `spend_ceiling_wei: u256`, `challenge_window_seconds: u256`, `created_at: u256` (tx-pinned unix seconds, D1), `bond_intact: bool` (goes false when the bond is slashed at STEP 7).
  - `@allow_storage @dataclass Action` — `id: str`, `mandate_id: str`, `merchant_url: str`, `item: str`, `price: str` (recorded text, e.g. `"$220.00"`), `recorded_at: u256`, `challenge_closes_at: u256` (D1: `recorded_at + mandate.challenge_window_seconds`), `open_challenge_id: str` (`""` when none — this is what enforces **one open challenge per action**, D3), `state: str`.
  - `@allow_storage @dataclass Challenge` — `id: str`, `action_id: str`, `mandate_id: str`, `challenger: Address`, `deposit_wei: u256`, `opened_at: u256`, `state: str`, plus flat verdict fields `verdict_within_mandate: bool`, `verdict_clause_violated: str`, `verdict_severity: u256`, `verdict_reasoning: str` (populated at resolve). **Deliberately flat, not a nested `Verdict` struct** — nested storage dataclasses are untested territory in this SDK and the flat form carries zero risk; noted for PM.
  - **Action state machine (5 states, no collapses):** `OPEN` (recorded, window still open) → `CHALLENGED` (challenge open, awaiting resolution) → `RESOLVED_OUT_OF_MANDATE` (verdict false, bond slashed) or `RESOLVED_WITHIN_MANDATE` (verdict true, challenger loses deposit); `UNCHALLENGED` (window elapsed with no challenge — terminal, bond intact). The OPEN→UNCHALLENGED transition happens lazily on read/settlement at STEP 4+, the states exist now.
  - **Challenge state machine (3 states):** `OPEN`, `RESOLVED_UPHELD` (action out of mandate — deposit returned to challenger), `RESOLVED_REJECTED` (action within mandate — deposit forfeited to operator).
  - **Collections & indexes** (Pattern 7, JSON-string id lists under `str` keys — calldata supports `str` keys only): `mandates: TreeMap[str, Mandate]`, `actions: TreeMap[str, Action]`, `challenges: TreeMap[str, Challenge]`; indexes `mandate_ids_by_operator`, `action_ids_by_mandate`, `challenge_ids_by_action`; counters `mandate_counter` / `action_counter` / `challenge_counter: u256`.
  - **ID scheme:** counter-based `str` ids — `m-000001`, `a-000001`, `c-000001` — stable, readable, calldata-safe.
  - **`required_deposit` is computable** for any action (D3, PM's CP1 requirement): `actions[action_id].mandate_id → mandates[mandate_id].bond_wei // u256(10)`. The view method itself is STEP 4 per the handover.
- `register_mandate(text, principal, spend_ceiling_wei, challenge_window_seconds) -> str` per the locked D7 signature: `@gl.public.write.payable`, `gl.message.sender_address` recorded as **operator**, `principal` converted with `Address(...)` (Pattern 5), bond captured from `gl.message.value` (u256 wei). Validations, each raising `gl.vm.UserError`: zero value ("Zero value"), zero ceiling ("Zero ceiling"), zero window ("Zero window"), blank text ("Empty text"), bond below ceiling ("Bond below ceiling", D2 — `>=` so equality is accepted). Appends to the operator's index; returns the mandate id.
- View methods: `get_mandate(mandate_id) -> dict` (every field, addresses as EIP-55 hex, u256 as int) and `get_mandate_ids_by_operator(operator) -> list`.
- Wrote `tests/direct/test_register_mandate.py` — 10 tests covering every required case in the handover §7.

**Evidence**
- `PYTHONIOENCODING=utf-8 genvm-lint check contracts/mandate_guard.py` → `✓ Lint passed (3 checks)` / `✓ Validation passed` / `Contract: MandateGuard` / `Methods: 3 (2 view, 1 write)`. No warnings of our own (the runner-version `ℹ` note is the one the PM ruled to ignore).
- `PYTHONIOENCODING=utf-8 pytest tests/direct/ -v` → **`53 passed in 1.43s`** — the 10 new `test_register_mandate.py` tests plus all 43 pre-existing tests, none broken. Required cases proven: read-back of every stored field; bond below ceiling rejected; bond **exactly equal** to ceiling accepted (boundary); zero-value rejected; zero ceiling rejected; two operators' mandates distinct and non-colliding. Extras: zero window rejected, blank text rejected, and a post-rejection check that the operator index stays empty. Rejections assert on the actual `UserError` message substring via `direct_vm.expect_revert(...)` (e.g. `Bond below ceiling`), not just "something raised".
- **Finding — bare `TreeMap()` in `__init__` is broken in this SDK when the class declares a dataclass-valued TreeMap.** First implementation assigned all six TreeMaps in `__init__`; every test failed with `AssertionError: Is right the same storage type? TreeMap <- TreeMap` at `genlayer/py/storage/_internal/desc_record.py:45` (genvm-std extracted by the pinned runner). Isolated by bisecting with probe contracts in `scratch/schema_probe/`: two `TreeMap[str, str]` fields + `__init__` assignment → passes; adding one `TreeMap[str, Item]` (Item = `@allow_storage @dataclass`) → the `__init__` assignment path fails regardless of assignment order, even for the previously-fine `str`-valued maps. Fix: **declare storage containers in the class body and never construct them in `__init__`** — they auto-default on first access. This is exactly the vendor's `football_bets.py` pattern, which is the same code shape already proven on studionet (5/5 AGREE, CP0-D). u256 counters are still explicitly initialized in `__init__` (verified that assignment works; the probe round-trip `put`/`get`/`has`/`get_or_default`/counter all pass). Probe files kept under `scratch/schema_probe/` as evidence; the probe's pytest file was removed from `tests/direct/` after diagnosis.

**Blockers**
- none

**Question for PM**
- `register_mandate` does **not** reject `principal == operator` (nothing in D7 or the docs specifies it; the adversarial design implies different parties but never mandates a check). I left it out rather than add an unspecified restriction. If you want it rejected, that's a one-line change at STEP 4 review.

**Deviations from the roadmap**
- `scratch/schema_probe/` probe contracts were created and run purely to root-cause the storage bug above; they are not Mandate Guard code and are not imported by anything. No other deviations.

---
### PM review — do not fill in
**Reviewed:**
**Verdict:**
**Notes:**
**Next step:**
---
