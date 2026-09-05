# Mandate Guard — Project Roadmap

**Owner:** PM (this document is PM-controlled — the coding agent does not edit it)
**Source of truth:** `README.md` build scope. Nothing here adds scope beyond that document.
**Event:** GenLayer Agent Tank. Build window 3–17 Sep. Submissions close **17 Sep, 15:30 UTC**.
**Today:** 4 Sep (Day 2 of 15). **13 days remain.**

---

## 1. Phase overview

| Phase | Name | Days | Exit criteria | Checkpoint |
|---|---|---|---|---|
| P0 | Environment & baseline | 4–5 Sep | Boilerplate runs end-to-end unmodified | CP0 |
| P1 | Design lock | 5 Sep | All 4 open questions closed in writing | CP1 |
| P2 | Contract — deterministic core | 6–8 Sep | `register_mandate`, `record_action`, `challenge` pass direct tests | CP2 |
| P3 | Contract — `resolve()` (non-deterministic) | 8–10 Sep | Verdict + slash/release working under equivalence principle | CP3 |
| P4 | Integration tests & deploy | 10–11 Sep | Deployed, integration suite green | CP4 |
| P5 | Frontend | 11–13 Sep | Mandate editor, action feed, challenge, verdict view wired live | CP5 |
| P6 | Demo agent & rehearsal | 13–15 Sep | Scripted drift → challenge → slash runs start-to-finish | CP6 |
| P7 | Submission package | 15–16 Sep | Public repo + portal application submitted | CP7 |
| — | Buffer | 17 Sep | Reserved. Do not plan work here. | — |

**Rule:** the coding agent stops at every checkpoint, writes `PROGRESS.md`, and waits for PM review before starting the next phase.

---

## 2. Phase detail

### P0 — Environment & baseline
Prove the toolchain works before writing a line of Mandate Guard code.

1. Clone `genlayerlabs/genlayer-project-boilerplate` into this folder, preserving the existing `README.md` and `pitch.md`.
2. Python 3.12+ venv, `pip install -r requirements.txt`.
3. `genvm-lint check` the shipped sample contract — must pass.
4. `pytest tests/direct/ -v` — must pass.
5. `npm install -g genlayer`, `genlayer init`, `genlayer up` (Docker 26+).
6. `genlayer deploy` the sample contract to localnet.
7. `gltest tests/integration/ -v -s --network localnet` — must pass.
8. `cd frontend && npm install && npm run dev` — loads in browser.

**Exit:** all 8 steps confirmed green, with actual version numbers recorded.
**Blocker policy:** if Docker is unavailable, stop and report — do not silently switch to GLSim.

### P1 — Design lock
Close the four open questions from `README.md`. PM has issued provisional rulings (Section 4). The agent confirms each is *implementable as stated* and flags any that are not — it does not redesign them.

Also fixed in this phase:
- The demo scenario: one mandate, one compliant action, one drifting action.
- The exact listing URL(s) validators will fetch. **This is the highest-risk external dependency in the project** — it must be a stable, publicly reachable page whose relevant facts do not change during the judging window.

**Exit:** `DESIGN_DECISIONS.md` written, all four questions closed, demo URLs chosen and verified reachable.

### P2 — Contract, deterministic core
No LLM and no web access in this phase. Storage schema plus the three deterministic entry points.

- Storage: mandates, actions, challenges, bonds, deposits, state machine.
- `register_mandate(text)` — payable; the operator bond arrives with this call.
- `record_action(action_json)` — merchant URL, item, price, timestamp.
- `challenge(action_id)` — payable; challenger deposit; enforces the challenge window and one-challenge-per-action.
- View methods for the frontend.
- Direct tests covering every deterministic path, including rejection cases.

**Exit:** `genvm-lint` clean, all direct tests green.

### P3 — `resolve()`, the non-deterministic core
The heart of the project.

- `leader_fn`: fetch the live listing, evaluate the recorded action against the mandate text, return the structured verdict.
- `validator_fn`: **independently re-fetch and re-judge**, then compare decision fields. It must not merely schema-check the leader output (Section 5).
- Settlement: out of mandate → slash the bond, compensate the principal. Within mandate → challenger forfeits the deposit.

**Exit:** verdict stored on-chain, funds move correctly in both directions, direct tests green.

### P4 — Integration tests & deploy
- Integration suite against localnet, then a hosted network.
- Deployment script; contract address recorded in `PROGRESS.md`.

### P5 — Frontend
Exactly the three surfaces named in `README.md` — mandate editor, action feed, challenge button and verdict view. Nothing else.

### P6 — Demo agent & rehearsal
- Scripted agent that deliberately drifts out of mandate.
- Full rehearsal: register → act → drift → challenge → validators fetch live listing → slash. Timed and recorded.

### P7 — Submission package
- Public GitHub repository, required by the rules.
- Repo README, setup instructions, contract address, demo video.
- Portal application submitted. **The submission form fields have not been independently verified** — the portal is login-walled — so verify them directly before writing final copy.
- Pitch copy: `pitch.md` carries an explicit warning that it is written in the wrong voice and must be rewritten before posting. That rewrite is a P7 task.

---

## 3. Checkpoint protocol

After each phase the agent must:
1. Append a report to `PROGRESS.md` using the template in that file.
2. State clearly: DONE / BLOCKED / NEEDS DECISION.
3. **Stop and wait.** No starting the next phase without PM sign-off.

Mid-phase, the agent stops immediately and reports if it hits any blocker, any ambiguity, or anything that would require deviating from this roadmap.

---

## 4. Decision register

The four open questions from `README.md`. PM rulings are provisional defaults chosen so the build can proceed; the principal may override any of them.

| # | Question | PM ruling | Rationale |
|---|---|---|---|
| D1 | Challenge window length | 24h production default, contract-configurable; **120 s in demo mode** | Short enough to demo live, long enough to be credible in production |
| D2 | Bond sizing | Operator bond ≥ the mandate spend ceiling, 1:1, posted at `register_mandate` | Operator downside at least equals the principal exposure. Simplest defensible rule |
| D3 | Frivolous-challenge deterrence | Challenger deposit = 10% of bond, forfeited to the operator on a failed challenge; one open challenge per action | This is the mechanism `README.md` already names; the cap prevents challenge spam |
| D4 | Equivalence principle fields | Compare `within_mandate` **exactly**; compare `clause_violated` **semantically**; exclude `severity` and `reasoning` from consensus | Fewest compared fields is safest for consensus, as the plan itself notes. See Section 5 |

---

## 5. Verified technical constraints

Confirmed against official GenLayer documentation on 4 Sep. These are guardrails for the coding agent, not suggestions.

**Equivalence principle — this decides D4.**
The docs are explicit that for *settlement logic* a validator must independently derive the answer and compare decision fields; a validator that only checks the leader output for valid JSON shape or an allowed enum value is not performing consensus. `resolve()` is settlement logic, so:
- Use a custom validator function via `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`.
- **Do not** use `prompt_non_comparative` as the consensus mechanism for the verdict.
- Source: https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle

**Web access** — native, no oracle needed:
- `gl.nondet.web.get(url)` for static pages and APIs.
- `gl.nondet.web.render(url, mode='html'|'text'|'screenshot', wait_after_loaded='5s')` for JavaScript-heavy pages.
- Extract stable structured facts inside the non-deterministic block; do not return raw page content for comparison.
- Source: https://docs.genlayer.com/developers/intelligent-contracts/features/web-access

**Value transfers — the bond mechanism is natively supported:**
- Receive with `@gl.public.write.payable`; the amount is `gl.message.value` (`u256`, wei; 1 GEN = 10^18 wei).
- Paying out to an EOA is an *external message* via the ghost contract and **always executes on finalization**, not immediately. Settlement timing must account for this.
- Source: https://docs.genlayer.com/developers/intelligent-contracts/features/value-transfers

**Storage rules — common failure points:**
- Persistent fields must be declared **in the class body with type annotations**. A field created as `self.x = ...` outside the class body is discarded.
- `list[T]` → `DynArray[T]`; `dict[K,V]` → `TreeMap[K,V]`; `int` is forbidden — use `u256` / `i32` / etc.
- Only fully instantiated generics: `TreeMap[str, u256]`, never bare `TreeMap`.
- Calldata mappings support **`str` keys only**.
- Custom structs need `@allow_storage` + `@dataclass`.
- **Storage objects cannot be used inside non-deterministic blocks** — copy them out first with `gl.storage.copy_to_memory()`. This directly affects `resolve()`, which must read the mandate text out of storage before prompting.
- Source: https://docs.genlayer.com/developers/intelligent-contracts/storage

**Toolchain:** Python 3.12+, Node 18+, Docker 26+. `genvm-lint` for linting, `pytest tests/direct/` for direct tests, `gltest tests/integration/` for integration tests, `genlayer init` / `genlayer up` for local Studio (UI at http://localhost:8080, RPC at http://localhost:4000/api).

**Unresolved:** the docs reference both `testnet_bradbury` (gltest config) and `testnetAsimov` (genlayer-js chains). Do not assume either — confirm the current network name from the installed tooling at P4.

---

## 6. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| A competing build, **AgentMandate** — "consensus-bound permission receipts for autonomous AI agents", Autonomous Protocols track — is already submitted and is adjacent to this concept | High | Lead with what is distinct: the adversarial principal-vs-operator framing, the posted bond, and validators reading the *live merchant listing*. Do not restate their framing |
| Demo listing URL changes or goes down during judging | High | Choose a stable page at P1, snapshot expected values, keep a fallback URL ready |
| Validators disagree and consensus fails on the verdict | High | D4 keeps the compared surface minimal. Test disagreement paths explicitly at P3 |
| Payouts execute only on finalization | Medium | Confirmed behaviour, not a bug — design the demo timeline around it |
| Frontend consumes days that belong to the contract | Medium | P5 is capped at the three surfaces in `README.md`. No additions |
| `pitch.md` posted in its current voice | Medium | The file itself warns against this. Rewrite is a P7 task |
| Portal submission fields unverified | Low | Verify at P7 before writing final copy |

---

## 7. Track selection

`README.md` does not name a track, and one is required at submission. No code depends on this, so the decision is deferred to P7.

**PM recommendation: Agentic Commerce Infrastructure.** That track explicitly lists "agent-liability insurance — covers agent misbehavior" among the ideas wanted, which is what a slashable operator bond is. It also avoids competing head-on with Internet Court, which dominates Onchain Justice, and with AgentMandate in Autonomous Protocols.

**Alternative: Onchain Justice** — defensible, since the challenge-and-verdict flow is rule enforcement decided from evidence. Weaker positioning, for the reason above.

Principal decides at P7.
