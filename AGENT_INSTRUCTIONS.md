# Mandate Guard — Coding Agent Instructions

**Read STANDING RULES once. Then execute exactly one step per session.**
Each step below is self-contained: it restates the context it needs. Do not read ahead and do not batch steps.

---

## STANDING RULES

1. **Project:** Mandate Guard, a GenLayer Intelligent Contract that enforces a natural-language spending mandate against an AI agent through a posted bond, an optimistic challenge window, and validator-adjudicated verdicts. The full design is in `README.md`. The plan of record is `PROJECT_ROADMAP.md`. Read both before your first step.
2. **Scope is closed.** Build only what `README.md` describes. If you believe something is missing, do not add it — report it in `PROGRESS.md` and stop.
3. **Never guess.** If a GenLayer API, version, or behaviour is uncertain, verify it in the official docs at https://docs.genlayer.com or with the installed tooling. If you cannot verify it, stop and report.
4. **Stop at every checkpoint.** At the end of each step, append a report to `PROGRESS.md` and stop. Do not begin the next step until the PM has reviewed and approved.
5. **Stop immediately on any blocker**, ambiguity, failing test you cannot fix, or anything that would require deviating from `PROJECT_ROADMAP.md`. Write it in `PROGRESS.md` under `Blockers` and stop. A blocker reported early costs an hour; a blocker discovered at the deadline costs the project.
6. **No silent substitutions.** If a prescribed tool, network, or library is unavailable, report it — do not swap in an alternative on your own authority.
7. **Do not edit** `README.md`, `PROJECT_ROADMAP.md`, `AGENT_INSTRUCTIONS.md`, or `pitch.md`. `PROGRESS.md` is append-only — never rewrite or delete earlier entries.
8. **Use the installed GenLayer skills** where they apply: `genlayer-dev:write-contract`, `genlayer-dev:genvm-lint`, `genlayer-dev:direct-tests`, `genlayer-dev:integration-tests`, `genlayer-dev:genlayer-cli`.
9. **Hard constraints verified against the docs** — these are not negotiable, see `PROJECT_ROADMAP.md` Section 5:
   - Persistent fields declared in the class body with type annotations. `list` → `DynArray[T]`, `dict` → `TreeMap[K,V]`, `int` is forbidden — use `u256`. Only fully instantiated generics. Custom structs need `@allow_storage` + `@dataclass`.
   - Storage objects cannot be used inside non-deterministic blocks — copy them out with `gl.storage.copy_to_memory()` first.
   - Calldata mappings support `str` keys only.
   - Payable methods use `@gl.public.write.payable`; the amount is `gl.message.value` (`u256`, wei).
   - Payouts to an EOA execute **on finalization**, not immediately.
   - For `resolve()`, consensus uses `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` with an independently re-deriving validator. **Never** use `prompt_non_comparative` as the consensus mechanism for the verdict.

---

## STEP 1 — Environment and baseline (Checkpoint CP0)

**Context:** Nothing has been built yet. The folder contains only `README.md`, `pitch.md`, `PROJECT_ROADMAP.md`, `AGENT_INSTRUCTIONS.md`, `PROGRESS.md`. The plan specifies starting from the official GenLayer boilerplate. Before writing any project code, prove the toolchain works unmodified.

**Task:**
1. Clone `https://github.com/genlayerlabs/genlayer-project-boilerplate` into this folder. **Preserve the existing `README.md` and `pitch.md`** — if the boilerplate ships its own `README.md`, save it as `BOILERPLATE_README.md`. Initialise git for this project.
2. Create a Python 3.12+ virtualenv and `pip install -r requirements.txt`.
3. Run `genvm-lint check` against the shipped sample contract.
4. Run `pytest tests/direct/ -v`.
5. `npm install -g genlayer`, then `genlayer init` and `genlayer up`. Studio UI at http://localhost:8080, RPC at http://localhost:4000/api.
6. Deploy the sample contract to localnet with `genlayer deploy`.
7. Run `gltest tests/integration/ -v -s --network localnet`.
8. `cd frontend && npm install && npm run dev` — confirm it loads.

**Constraints:** Change nothing in the boilerplate. This step is verification only. If Docker 26+ is unavailable, **stop and report** — do not fall back to GLSim.

**Exit criteria:** All 8 sub-steps green, with the actual observed versions of Python, Node, Docker, the GenLayer CLI, and `genlayer-test` recorded.

**Checkpoint:** Append a CP0 entry to `PROGRESS.md`. Record the versions, the boilerplate directory structure as it actually exists on disk, and any warnings. Then **stop and wait for PM review.**

---

## STEP 2 — Design lock (Checkpoint CP1)

**Context:** The toolchain is verified. `README.md` leaves four questions open; `PROJECT_ROADMAP.md` Section 4 contains the PM rulings that close them. Your job is to confirm each ruling is implementable and to fix the demo scenario — not to redesign anything.

**Task:** Write `DESIGN_DECISIONS.md` containing:
1. **D1 challenge window** — 24h production default, contract-configurable, 120 s in demo mode. Confirm how the contract will read time and state the mechanism you verified.
2. **D2 bond sizing** — operator bond ≥ mandate spend ceiling, 1:1, posted at `register_mandate`. State how the ceiling is supplied and validated.
3. **D3 challenger deposit** — 10% of bond, forfeited to the operator on a failed challenge, one open challenge per action.
4. **D4 equivalence fields** — `within_mandate` compared exactly, `clause_violated` compared semantically, `severity` and `reasoning` excluded from consensus.
5. **The demo scenario** — one mandate in plain English, one compliant action, one deliberately drifting action. Use the `README.md` example as the model: a mandate containing a judgment clause such as "prefer refundable", violated by a non-refundable purchase.
6. **The listing URL(s)** validators will fetch. Verify each is publicly reachable without authentication, and record whether `gl.nondet.web.get()` or `gl.nondet.web.render()` is needed. Choose a **fallback URL** as well.
7. **The verdict JSON schema**, matching `README.md` exactly: `within_mandate`, `clause_violated`, `severity`, `reasoning`.

**Constraints:** Do not change any PM ruling. If one is not implementable as written, say so explicitly, explain why, and stop — the PM decides the alternative, not you. The listing URL is the project's highest external risk: prefer a page whose relevant facts are stable over the next two weeks.

**Exit criteria:** `DESIGN_DECISIONS.md` complete; every URL confirmed reachable with the fetch method recorded.

**Checkpoint:** Append a CP1 entry to `PROGRESS.md` summarising each decision in one line, plus the chosen URLs. Then **stop and wait for PM review.**

---

## STEP 3 — Storage schema and `register_mandate` (Checkpoint CP2a)

**Context:** Design is locked in `DESIGN_DECISIONS.md`. You are now building the contract's deterministic core. **No LLM calls and no web access in this step.**

**Task:**
1. Create the Mandate Guard contract file in `contracts/`.
2. Define the persistent storage schema: mandates, actions, challenges, bonds, deposits, and the per-action state machine.
3. Implement `register_mandate(text)` as a payable method. It stores the natural-language mandate, records the principal and the operator, captures the bond from `gl.message.value`, and enforces D2 bond sizing.
4. Implement the view methods needed to read a mandate back.
5. Write direct tests in `tests/direct/` covering: successful registration, bond below the required minimum rejected, zero-value registration rejected, and correct read-back.

**Constraints:** Obey every storage rule in STANDING RULES item 9. Run `genvm-lint check` on the contract before finishing. Do not implement `record_action`, `challenge`, or `resolve` yet.

**Exit criteria:** `genvm-lint` clean; all direct tests green.

**Checkpoint:** Append a CP2a entry to `PROGRESS.md` including the final storage schema and test results. Then **stop and wait for PM review.**

---

## STEP 4 — `record_action` and `challenge` (Checkpoint CP2b)

**Context:** Storage and `register_mandate` are approved. Continue the deterministic core. **Still no LLM and no web access.**

**Task:**
1. Implement `record_action(action_json)` — stores merchant URL, item, price, timestamp against a mandate, assigns an action id, and opens the challenge window per D1.
2. Implement `challenge(action_id)` as a payable method — takes the challenger deposit per D3, enforces that the challenge window is still open, and enforces one open challenge per action.
3. Implement the view methods the frontend needs: list actions for a mandate, read one action with its challenge state.
4. Write direct tests covering: action recorded and read back; challenge accepted inside the window; challenge rejected after the window closes; second challenge on the same action rejected; challenge with an insufficient deposit rejected; challenge against an unknown action id rejected.

**Constraints:** Only the operator registered on the mandate may record actions against it. Obey the storage rules. `genvm-lint check` must pass. Do not implement `resolve` yet.

**Exit criteria:** `genvm-lint` clean; all direct tests green; the full deterministic path register → act → challenge works end-to-end in tests.

**Checkpoint:** Append a CP2b entry to `PROGRESS.md` with the test matrix and results. Then **stop and wait for PM review.**

---

## STEP 5 — `resolve()` leader function (Checkpoint CP3a)

**Context:** The deterministic core is approved. You now build the non-deterministic heart of the project: the leader's judgment. The validator half comes in the next step — **do not build it yet.**

**Task:**
1. Implement `leader_fn` inside `resolve(challenge_id)`. It must:
   - Copy the mandate text and the recorded action out of storage with `gl.storage.copy_to_memory()` **before** entering the non-deterministic block.
   - Fetch the live listing at the action's merchant URL using the method fixed in `DESIGN_DECISIONS.md`.
   - Prompt the LLM with the mandate text, the recorded action, and the fetched listing.
   - Return the verdict JSON exactly as schemed: `within_mandate`, `clause_violated`, `severity`, `reasoning`.
2. Handle the failure cases explicitly: page unreachable, page content unusable, malformed LLM output. Return a defined failure result rather than raising into an unhandled state.
3. Write direct tests exercising the leader path against the demo scenario — both the compliant action and the drifting action.

**Constraints:** Do not wire consensus or settlement yet. Extract stable structured facts from the page; do not return raw page content. `genvm-lint check` must pass.

**Exit criteria:** The leader produces a correct, well-formed verdict for both demo actions, and degrades cleanly on all three failure cases.

**Checkpoint:** Append a CP3a entry to `PROGRESS.md` including the actual verdict JSON produced for each demo action. Then **stop and wait for PM review.**

---

## STEP 6 — Validator function and consensus (Checkpoint CP3b)

**Context:** The leader function is approved and producing correct verdicts. You now add the validator half so the verdict reaches consensus. This is the single most important correctness requirement in the project.

**Task:**
1. Implement `validator_fn`. It must **independently re-fetch the listing and re-derive its own verdict**, then compare against the leader's.
2. Comparison follows D4 exactly: `within_mandate` must match exactly; `clause_violated` is compared semantically; `severity` and `reasoning` are excluded from consensus.
3. Wire both halves with `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` and store the agreed verdict on-chain.
4. Write direct tests covering: validator agrees with a correct leader verdict; validator rejects a leader verdict whose `within_mandate` is wrong; validator handles the leader returning an exception.

**Constraints — read carefully:** The GenLayer docs state that for settlement logic a validator which only checks the leader's output for a valid JSON shape or an allowed enum value **is not performing consensus**. Your validator must verify the substance by deriving its own answer. **Do not** use `prompt_non_comparative` as the consensus mechanism here. Source: https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle

**Exit criteria:** Consensus reached and the verdict stored; the disagreement path tested and behaving correctly; `genvm-lint` clean.

**Checkpoint:** Append a CP3b entry to `PROGRESS.md` stating exactly how the validator derives its answer and which fields are compared. Then **stop and wait for PM review.**

---

## STEP 7 — Settlement: slash and release (Checkpoint CP3c)

**Context:** Verdicts now reach consensus. The final contract piece is moving the money — the mechanism the whole project rests on.

**Task:**
1. On `within_mandate == false`: slash the operator's bond and compensate the principal.
2. On `within_mandate == true`: the challenger forfeits their deposit to the operator, and the bond is untouched.
3. Close the challenge, mark the action resolved, and make the outcome readable through a view method.
4. Write direct tests asserting balances before and after in **both** directions, and that a resolved challenge cannot be resolved twice.

**Constraints:** Payouts to an EOA are external messages that execute **on finalization**, not immediately — your tests and the demo timeline must account for this. Use `u256` throughout; no floating-point arithmetic on value. `genvm-lint check` must pass.

**Exit criteria:** Both settlement directions verified by balance assertions; double-resolution rejected; the full contract lints clean and every direct test passes.

**Checkpoint:** Append a CP3c entry to `PROGRESS.md` with before/after balances for both paths. Then **stop and wait for PM review.** This is the end of P3 — the contract is now feature-complete.

---

## STEP 8 — Integration tests and deployment (Checkpoint CP4)

**Context:** The contract is feature-complete and passes direct tests. Direct tests run in memory; you now need proof it works under real consensus.

**Task:**
1. Write integration tests in `tests/integration/` covering the full lifecycle: register → record action → challenge → resolve → settle, for both verdict directions.
2. Run them against localnet: `gltest tests/integration/ -v -s --network localnet`.
3. Confirm the correct current hosted-network name from the installed tooling — **do not assume**; the docs reference both `testnet_bradbury` and `testnetAsimov`. Then run the suite against it.
4. Write or adapt the deployment script in `deploy/` and deploy. Record the contract address and network.

**Constraints:** Fix failures in the contract, not by weakening tests. If a test passes in direct mode but fails under real consensus, that is a genuine finding — report it, do not paper over it.

**Exit criteria:** Integration suite green on localnet and on a hosted network; contract deployed; address recorded.

**Checkpoint:** Append a CP4 entry to `PROGRESS.md` with the network name, contract address, and full test results. Then **stop and wait for PM review.**

---

## STEP 9 — Frontend wiring (Checkpoint CP5a)

**Context:** A contract is deployed at the address in `PROGRESS.md` CP4. The boilerplate ships a Next.js 15 frontend with GenLayerJS. You now connect it to Mandate Guard.

**Task:**
1. Point the frontend at the deployed contract and network.
2. Implement the read and write bindings for every contract method the UI needs: `register_mandate`, `record_action`, `challenge`, `resolve`, and the views.
3. Confirm wallet connection and that a payable call correctly sends value.
4. Prove one full round trip from the browser: register a mandate with a bond and read it back.

**Constraints:** Use the boilerplate's existing patterns and stack. Do not introduce new frameworks or a redesign. Payable calls must send `value`; on a fee-charging deployment, estimate the protocol fee separately.

**Exit criteria:** Wallet connects; a mandate is registered from the browser with a bond attached and reads back correctly.

**Checkpoint:** Append a CP5a entry to `PROGRESS.md` recording what worked and any wiring problems. Then **stop and wait for PM review.**

---

## STEP 10 — The three UI surfaces (Checkpoint CP5b)

**Context:** The frontend is wired to the contract. Build exactly the three surfaces `README.md` names — no more.

**Task:**
1. **Mandate editor** — write a mandate in plain English, set the spend ceiling, post the bond, submit.
2. **Action feed** — the list of what the agent bought against a mandate: merchant URL, item, price, timestamp, and current state (open / challenged / resolved).
3. **Challenge button and verdict view** — challenge an action within its window with the deposit attached, then display the returned verdict showing `within_mandate`, `clause_violated`, `severity`, `reasoning`, and the resulting slash or release.

**Constraints:** These three surfaces only. No dashboards, no analytics, no auth, no extra pages. The UI must be legible on a projector during a demo — this is judged on video. If you find yourself adding a fourth surface, stop and report instead.

**Exit criteria:** All three surfaces work against the deployed contract; the complete flow is drivable from the browser with no CLI.

**Checkpoint:** Append a CP5b entry to `PROGRESS.md` listing each surface and its status. Then **stop and wait for PM review.**

---

## STEP 11 — Demo agent and rehearsal (Checkpoint CP6)

**Context:** The full system works. `README.md` calls for a scripted agent that drifts out of mandate on purpose, challenged live, with validators reading the real listing and the bond slashed.

**Task:**
1. Write the scripted agent — a standalone script, not part of the contract. It registers a mandate with a bond, records one compliant action, then records the deliberately drifting action from `DESIGN_DECISIONS.md`.
2. Rehearse the full sequence end-to-end: run the agent → challenge the drifting action in the UI → validators fetch the live listing → verdict returns → bond slashed → principal compensated.
3. **Time each stage** and record the timings. The demo must fit inside the 90-second video slot referenced in `pitch.md`.
4. Run the rehearsal at least twice, from a clean state, and confirm it is reproducible.
5. Confirm the fallback listing URL also works.

**Constraints:** No hidden shortcuts — validators must genuinely fetch the live page. If a stage is too slow for the video, report the timing; the PM decides what to cut. Note that settlement finalises rather than completing instantly, and account for that in the timeline.

**Exit criteria:** Two clean consecutive end-to-end runs with per-stage timings recorded.

**Checkpoint:** Append a CP6 entry to `PROGRESS.md` with the timing table and anything that failed or looked fragile. Then **stop and wait for PM review.**

---

## STEP 12 — Public repository and documentation (Checkpoint CP7a)

**Context:** The build is demo-ready. Submission requires a **public GitHub repository** plus a full project application. This step covers the repository.

**Task:**
1. Verify no secrets, private keys, or `.env` files are committed. Check the git history, not just the working tree.
2. Write the repository README: what Mandate Guard is, why it needs GenLayer, architecture, setup instructions someone else can actually follow, the deployed contract address and network, and how to run the demo.
3. Confirm a clean clone builds and the direct tests pass from scratch.
4. Push to a public GitHub repository.

**Constraints:** Do not publish anything until the secret check passes. The repo README is for a stranger who has never seen this project — the existing `README.md` is a design document and is not a substitute. Keep `PROGRESS.md`, `PROJECT_ROADMAP.md`, and `DESIGN_DECISIONS.md` in the repo; they are evidence of process.

**Exit criteria:** Public repo live, clean clone verified, no secrets in history.

**Checkpoint:** Append a CP7a entry to `PROGRESS.md` with the repository URL and the result of the secret scan. Then **stop and wait for PM review.**

---

## STEP 13 — Submission (Checkpoint CP7b)

**Context:** Final step. The repository is public and the demo is rehearsed. What remains is the portal submission and the pitch copy.

**Task:**
1. Open the submission form at https://portal.genlayer.foundation/agent-tank/hackathon/submit and **record the exact fields it asks for**. These have not been verified — do not write copy against assumed fields.
2. Record the demo video from the STEP 11 rehearsal.
3. Draft the submission copy. **`pitch.md` must not be used as-is** — that file carries an explicit warning that it is written in a machine-sounding voice. Follow its own "Rewrite notes" section: no triads, no signposting, vary sentence length, include at least one honest admission of something unresolved, and stop landing a punchline on every line.
4. Report the drafted copy, the chosen track, and the video to the PM **before submitting anything**.
5. Submit only after PM approval.

**Constraints:** Track selection is a PM decision — see `PROJECT_ROADMAP.md` Section 7. Do not submit without explicit approval. Deadline is **17 Sep 15:30 UTC**; aim to submit on 16 Sep and keep 17 Sep as buffer.

**Exit criteria:** Submission accepted, with confirmation captured.

**Checkpoint:** Append a CP7b entry to `PROGRESS.md` with the form fields as they actually appeared, the final copy, the track chosen, and the submission confirmation. Then **stop.**
