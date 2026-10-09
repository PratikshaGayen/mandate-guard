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
Every purchase is recorded bound to the merchant's receipt: validators fetch it,
check its SHA-256, and take item, charged amount, purchaser and time from it
        ↓
Anyone can challenge a purchase inside a window
        ↓                                       (no challenge)
GenLayer validators fetch the LIVE listing      Window closes → anyone calls
and judge it against the mandate                finalize_action → UNCHALLENGED
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
  record_action(mandate_id,    operator-only; validators fetch the merchant receipt, check its
    receipt_url, receipt_sha256)  hash, and bind item/amount/purchaser/time from it; opens window
  challenge(action_id)         payable; exact deposit = bond/10, one challenge per action
  resolve(challenge_id)        permissionless; web fetch + LLM leader, validator re-derivation,
                               slash (bond → principal) or release (deposit → operator)
  finalize_action(action_id)   permissionless; closes an action whose window passed unchallenged

tests/direct/                  84 fast in-memory tests (web + LLM mocked)
tests/integration/             full lifecycle under real multi-validator consensus (studionet)
demo/run_demo.py               scripted demo agent: buys, records, challenges the drift, finalizes
demo/merchant.py               client for the demo merchant's checkout (used by demo + tests)
frontend/                      Next.js UI: mandate editor, action feed, verdict panel, and the
                               demo merchant (frozen listing + checkout + signed receipts)
deploy/deploy_mandate_guard.py deployment script (genlayer_py)
demo-listing/                  source of the frozen fictional "Atlas Air" merchant page
```

Key implementation notes:

- **Purchases are bound to receipts, not self-reported**: `record_action` takes only a receipt URL and its SHA-256. Validators fetch the receipt inside the transaction and must agree byte-for-byte on what it says; the contract then requires the purchaser to be the operator, the receipt to come from the same https origin as the listing it names, the purchase time to fall inside the mandate's life, and the receipt never to have been used before. The hash covers canonical JSON (sorted keys, compact), so transport formatting can't break consensus. Verifying at record time also means an operator can't make a purchase unchallengeable later by deleting the receipt.
- **Unchallenged actions finalize on-chain**: `finalize_action` is permissionless and valid from the exact second `challenge()` stops accepting, so there is no instant when both or neither are possible.
- **Deterministic time**: the GenVM clock is pinned to the transaction timestamp, so `challenge_closes_at` windows are consensus-safe. The receipt's timestamp is checked against the mandate, but the window always comes from the pinned clock.
- **Settlement arithmetic is u256-native**; every payout leg is recorded in `payouts_json` so the UI shows exactly what moved.
- **Double-slash impossible**: once a mandate's bond is slashed, no new challenges open, and an in-flight challenge's resolution skips the already-paid bond leg while still returning the deposit. A payout-sum invariant test guards this permanently.
- **Fail-towards-safety**: if the listing fetch fails or the LLM returns malformed JSON, `resolve()` reverts cleanly with no state or money moved — the caller can retry.

## Honest limitations

- **The challenger incentive gap.** A failed challenge loses the deposit; a successful one merely returns it. Net zero upside, real downside — so a rational third party never challenges, and only the principal (who is always motivated) realistically will. v1 ships as-is; a bond-bounty split is the obvious next step.
- **USD/GEN seam.** The mandate prose caps spend in "$250" while bonds and deposits are denominated in GEN-wei; the two are not formally linked. The spend ceiling is a principal-declared wei parameter, never parsed from the prose.
- **Blunt settlement.** Severity is recorded but does not scale the payout: any out-of-mandate ruling slashes the full bond, whether the deviation was $5 or $200.
- **Payouts to plain wallets** on studionet finalize via the contract-not-found handler without crediting the recipient EOA (network-side behaviour, reproduced with probes). The on-chain payout record and contract balance movement are the verifiable settlement evidence.
- **One challenge per action, ever.** Once adjudicated, an action cannot be re-litigated (`open_challenge_id` is never cleared). The name says "open" — the rule is stricter.
- **The demo merchant is ours.** Atlas Air is fictional and runs on the same Vercel deployment as the UI. Its receipts are HMAC-signed at checkout, so only its checkout can mint them, and the contract's same-origin rule means a receipt hosted anywhere else is refused. What this proves is "issued by the merchant at purchase time"; it does not prove a card was charged. With a real merchant the same binding applies to its own receipt endpoint, and a merchant-signed receipt verified on-chain would be the stronger next step.
- **Finalizing changes state, not money.** `finalize_action` marks an action closed; the bond stays posted for the mandate's other actions. There is no bond-withdrawal path in v1.

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

84 tests, no network needed — web and LLM calls are mocked. `test_receipts_and_finalize.py` covers the receipt binding (every rejection case, validator agreement, and a receipt edited after the leader read it) and `finalize_action`. On Windows the tests apply a small compatibility patch (`tests/direct/conftest.py`) for a known gltest file-locking issue.

### Lint the contract

```bash
genvm-lint check contracts/mandate_guard.py
```

### Run the demo agent

```bash
# needs a reachable network; defaults to studionet via gltest.config.yaml
python demo/run_demo.py
```

Deploys a fresh MandateGuard and registers the mandate with a 120-second window. Buys the refundable Flex Economy ($220) and the deliberately drifting non-refundable Basic Saver ($180) from the demo merchant, recording each bound to its receipt. Challenges the drift and waits for real validator consensus, then waits out the window and finalizes the unchallenged compliant purchase. Expect about three minutes; the `resolve` stage is 55–65s of genuine multi-validator LLM consensus and is the point.

### Frontend → contract wiring

The deployed demo instance:

| | |
|---|---|
| Network | studionet (chain ID 61999) |
| RPC | `https://studio.genlayer.com/api` |
| Contract | [`0x4E897E7e665e6846cb851cB450e7106B85af9AA6`](https://explorer-studio.genlayer.com/address/0x4E897E7e665e6846cb851cB450e7106B85af9AA6) |
| Live UI | https://mandate-guard-five.vercel.app |

Set `NEXT_PUBLIC_CONTRACT_ADDRESS` in `frontend/.env.local` to point the UI at any instance. MetaMask users: add the network manually (RPC above, chain ID `61999`, currency `GEN`) — studionet has no public RPC-registered chain entry in MetaMask's default list, so the app's `wallet_addEthereumChain` flow needs those values supplied.

To redeploy your own instance instead:

```bash
python deploy/deploy_mandate_guard.py
```

## The merchant listing

Validators fetch the listing themselves during `resolve()`. The demo uses a frozen static page (fictional "Atlas Air" flight AA-281 BER→LIS, Basic Saver $180 non-refundable vs Flex Economy $220 refundable). Source is in [`demo-listing/`](demo-listing/), and the same bytes are served at https://mandate-guard-five.vercel.app/atlas-air.html. The listing has to live on the merchant's own origin, next to its receipts, because `record_action` requires the two to match. The original copy at https://pratikshagayen.github.io/mandate-guard-demo/ is unchanged.

The merchant's checkout:

```bash
curl -X POST https://mandate-guard-five.vercel.app/api/atlas-air/checkout \
  -H 'content-type: application/json' \
  -d '{"fare": "basic-saver", "purchaser": "0xYourOperatorAddress"}'
# → {"receipt": {...}, "receipt_url": "https://…/api/atlas-air/receipts/<token>", "receipt_sha256": "…"}
```

Fares are `basic-saver` and `flex-economy`. The receipt's item, amount and timestamp are set by the merchant; the URL token is HMAC-signed, so a receipt cannot be altered or invented.

## Testing evidence

- `pytest tests/direct/ -v` → 84 passed
- `genvm-lint check contracts/mandate_guard.py` → Lint passed / Validation passed, 11 methods (6 view, 5 write)
- Integration (studionet, real 5-validator consensus): full lifecycle both verdict directions, contract balance drops by exactly `bond + deposit` on slash and `deposit` on release, asserted on-chain; purchases bound to live merchant receipts; a wrong receipt hash rejected on-chain; an unchallenged purchase finalized after its window.

`PROGRESS.md` (append-only checkpoint log), `PROJECT_ROADMAP.md`, and `DESIGN_DECISIONS.md` are kept in the repo as the process record.

## License

MIT. Built on the [genlayer-project-boilerplate](https://github.com/genlayerlabs/genlayer-project-boilerplate) (vendor sample contract and its tests were removed during development; the MIT license notice from that boilerplate is retained).
