# Mandate Guard

Enforce what you actually meant when your AI agent spends your money — on [GenLayer](https://www.genlayer.com/), the AI-native blockchain where validators read the live web and judge with an LLM.

Built for the GenLayer Agent Tank hackathon (September 2026).

## The problem

Agent payment rails (AP2, x402, Visa's Trusted Agent Protocol) handle numeric limits fine: price caps, merchant allowlists, spend velocity. But half of any real instruction is a judgment call — "prefer refundable fares", "a reputable seller", "nothing that looks like a scalper". No payment rail can enforce a sentence like that.

It gets worse: in AP2, the party that checks the cart against your intent **is your own agent** — exactly the party that could be compromised or prompt-injected. And AP2's flagship demo case is "buy the tickets the moment they go on sale": you're asleep, nobody is watching.

## What it does

```
You register a mandate in plain English (+ post a bond)
        ↓
Agent posts the bond, transacts instantly — zero added latency
        ↓
Every purchase lands on-chain with its evidence
(merchant URL, item, price, timestamps)
        ↓
Anyone can challenge a purchase inside a window
        ↓
GenLayer validators fetch the LIVE listing and judge it against the mandate
        ↓
Out of mandate → bond slashed, principal compensated
Within mandate → challenger loses their deposit
```

The design is optimistic-challenge (like GenLayer's own Optimistic Democracy): the agent never waits for a judge, but every action is backed by collateral and can be adjudicated afterwards.

**The verdict is structured and on-chain** — `within_mandate` (bool), `clause_violated` (quoted clause or null), `severity` (0–100), `reasoning` (free text). A ruling with money attached, not a vibe.

## Why this needs GenLayer

1. **The parties are adversaries.** Principal and operator are on opposite sides; neither one's backend gets to grade its own homework. The judgment comes from a stake-weighted validator committee.
2. **The decision requires judgment, not code.** "Is a non-refundable fare a violation if the refundable one cost $40 more?" No deterministic contract can evaluate that — validators each run their own LLM call.
3. **It has to read the live web.** Validators fetch the actual merchant listing themselves, natively — no oracle, no trusted feeder.

Consensus mechanics: the leader fetches the listing and produces a verdict; every validator **independently re-fetches the page and re-derives its own verdict**, comparing `within_mandate` exactly and `clause_violated` semantically (LLM-mediated comparison). `severity` and `reasoning` are recorded but never compared — they're display fields, and comparing LLM prose byte-for-byte would break consensus.

## Architecture

```
contracts/mandate_guard.py     MandateGuard intelligent contract (Python, GenVM)
  register_mandate(...)        operator registers mandate, bond = value attached
  record_action(...)           operator-only; stores evidence + opens challenge window
  challenge(action_id)         payable; exact deposit = bond/10, one challenge per action
  resolve(challenge_id)        permissionless; web fetch + LLM leader, validator re-derivation,
                               slash (bond → principal) or release (deposit → operator)

tests/direct/                  61 fast in-memory tests (web + LLM mocked)
tests/integration/             full lifecycle under real multi-validator consensus (studionet)
demo/run_demo.py               scripted demo agent: compliant + deliberately drifting actions
frontend/                      Next.js 15 UI: mandate editor, action feed, verdict panel
deploy/deploy_mandate_guard.py deployment script (genlayer_py)
demo-listing/                  the frozen fictional "Atlas Air" merchant page
                               (served via GitHub Pages for the validators to fetch)
```

Key implementation notes:

- **Deterministic time**: the GenVM clock is pinned to the transaction timestamp, so `challenge_closes_at` windows are consensus-safe.
- **Settlement arithmetic is u256-native**; every payout leg is recorded in `payouts_json` so the UI shows exactly what moved.
- **Double-slash impossible**: once a mandate's bond is slashed, no new challenges open, and an in-flight challenge's resolution skips the already-paid bond leg while still returning the deposit. A payout-sum invariant test guards this permanently.
- **Fail-towards-safety**: if the listing fetch fails or the LLM returns malformed JSON, `resolve()` reverts cleanly with no state or money moved — the caller can retry.

## Honest limitations

- **The challenger incentive gap.** A failed challenge loses the deposit; a successful one merely returns it. Net zero upside, real downside — so a rational third party never challenges, and only the principal (who is always motivated) realistically will. v1 ships as-is; a bond-bounty split is the obvious next step.
- **USD/GEN seam.** The mandate prose caps spend in "$250" while bonds and deposits are denominated in GEN-wei; the two are not formally linked. The spend ceiling is a principal-declared wei parameter, never parsed from the prose.
- **Blunt settlement.** Severity is recorded but does not scale the payout: any out-of-mandate ruling slashes the full bond, whether the deviation was $5 or $200.
- **Payouts to plain wallets** on studionet finalize via the contract-not-found handler without crediting the recipient EOA (network-side behaviour, reproduced with probes). The on-chain payout record and contract balance movement are the verifiable settlement evidence.
- **One challenge per action, ever.** Once adjudicated, an action cannot be re-litigated (`open_challenge_id` is never cleared). The name says "open" — the rule is stricter.

## Setup

Prerequisites: Python 3.12+, Node 18+, and a funded GenLayer account for anything on-chain.

```bash
# Python environment (contract + tests)
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash; .venv/bin/activate elsewhere
pip install -r requirements.txt

# Frontend
cd frontend && npm install
cp .env.example .env.local           # set NEXT_PUBLIC_CONTRACT_ADDRESS (see below)
npm run dev                          # http://localhost:3000
```

### Run the fast tests

```bash
pytest tests/direct/ -v
```

61 tests, no network needed — web and LLM calls are mocked. On Windows the tests apply a small compatibility patch (`tests/direct/conftest.py`) for a known gltest file-locking issue.

### Lint the contract

```bash
genvm-lint check contracts/mandate_guard.py
```

### Run the demo agent

```bash
# needs a reachable network; defaults to studionet via gltest.config.yaml
python demo/run_demo.py
```

Deploys a fresh MandateGuard, registers the mandate, records a compliant action (refundable Flex Economy $220) and a deliberately drifting one (non-refundable Basic Saver $180), challenges the drift, and waits for real validator consensus. Expect roughly 2 minutes; the `resolve` stage is 55–65s of genuine multi-validator LLM consensus and is the point.

### Frontend → contract wiring

The deployed demo instance:

| | |
|---|---|
| Network | studionet (chain ID 61999) |
| RPC | `https://studio.genlayer.com/api` |
| Contract | [`0xbd70CB985fA5D581aA7b83c1e27EBf3D1293593b`](https://explorer-studio.genlayer.com/) |

Set `NEXT_PUBLIC_CONTRACT_ADDRESS` in `frontend/.env.local` to point the UI at any instance. MetaMask users: add the network manually (RPC above, chain ID `61999`, currency `GEN`) — studionet has no public RPC-registered chain entry in MetaMask's default list, so the app's `wallet_addEthereumChain` flow needs those values supplied.

To redeploy your own instance instead:

```bash
python deploy/deploy_mandate_guard.py
```

## The merchant listing

Validators fetch the listing themselves during `resolve()`. The demo uses a frozen static page (fictional "Atlas Air" flight AA-281 BER→LIS, Basic Saver $180 non-refundable vs Flex Economy $220 refundable), published at https://pratikshagayen.github.io/mandate-guard-demo/ with the source in [`demo-listing/`](demo-listing/) and a raw-GitHub fallback URL baked into the demo script. It is frozen through judging so every validator fetch is byte-identical.

## Testing evidence

- `pytest tests/direct/ -v` → 61 passed
- `genvm-lint check contracts/mandate_guard.py` → Lint passed / Validation passed
- Integration (studionet, real 5-validator consensus): full lifecycle both verdict directions, contract balance drops by exactly `bond + deposit` on slash and `deposit` on release, asserted on-chain.

`PROGRESS.md` (append-only checkpoint log), `PROJECT_ROADMAP.md`, and `DESIGN_DECISIONS.md` are kept in the repo as the process record.

## License

MIT. Built on the [genlayer-project-boilerplate](https://github.com/genlayerlabs/genlayer-project-boilerplate) (vendor sample contract and its tests were removed during development; the MIT license notice from that boilerplate is retained).
