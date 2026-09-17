# Demo video — shot list and recording notes

Target slot: **90 seconds**, vertical or 16:9, voiceover or talking head.
Source of truth for timing: `scratch/cp6_demo/demo_run*.log` (86–116s continuous; `resolve` is 55–65s of that).

**The one honest edit (PM decision, recorded at CP6):** show register → record → challenge in real time, then **cut to a sped-up clip of the `resolve` wait, labeled "real validator consensus, sped up."** Never present a shortened `resolve()` as if it ran in seconds.

## Recording workflow

1. `python demo/run_demo.py --step` — the script pauses for Enter between stages, so each shot can be captured calmly. Timing lines still print, but the video timeline is whatever you record.
2. Pre-stage the frontend at the mandate editor (`npm run dev`, MetaMask connected to studionet if the wallet round-trip is being shown on camera).
3. Record the browser segments separately from the terminal segments; stitch on the captions.
4. The verdict reveal (SHOT 7) is the payoff — leave it on screen 6–8s with no talking.

## Shots

| # | Time | Screen | Action | Caption / narration beat |
|---|------|--------|--------|--------------------------|
| 1 | 0:00–0:10 | Terminal | `register_mandate` runs via `--step` Enter. Show the mandate text echoed. | "You write what you actually meant — in plain English. Your agent posts a bond against it." |
| 2 | 0:10–0:20 | Browser (action feed) | Compliant action appears: Flex Economy $220, refundable. | "Your agent buys. Instantly — no validator in the purchase path." |
| 3 | 0:20–0:32 | Browser | Drifting action appears: Basic Saver $180, **non-refundable**. Highlight the difference. | "Cheaper. And exactly what you told it not to do. Half of every real instruction is a judgment call — no payment rail can enforce one." |
| 4 | 0:32–0:42 | Browser → terminal | `challenge` runs; deposit 25 GEN read from `required_deposit`. | "Anyone can challenge — the deposit is set by the contract, not the challenger." |
| 5 | 0:42–0:55 | Browser (listing page) | Quick cutaway to the live Atlas Air page. | "Validators don't take anyone's word. They fetch the listing themselves." |
| 6 | 0:55–1:10 | Terminal | **Sped-up `resolve` clip, labeled "real validator consensus, sped up"** (it is 55–65s in reality). | "Each validator re-fetches the page, re-runs the judgment with its own LLM, and they have to agree." |
| 7 | 1:10–1:30 | Terminal → browser | Verdict reveal: `within_mandate: False`, quoted clause, `bond_intact: False`, payouts `250 GEN → principal`, `25 GEN → challenger`. | "Out of mandate. The bond is slashed and you're compensated. Not a vibe — a ruling, with money attached." |

If the slot allows 3 more seconds, SHOT 7 narration closes with the honest-admission line from the pitch ("there's no bounty yet for a stranger to challenge — that's the next thing"), which doubles as the credibility beat.

## If the wallet round-trip is shown on camera

Do it as a cold open before SHOT 1: connect MetaMask, add studionet manually if prompted (chain ID 61999), click **Register mandate and post bond**, show the MetaMask signature, then the mandate appearing in the feed. Studionet is gasless, so no funding step is needed. If anything hangs, cut it — the script path proves the same calls.

## Caption provenance

- Verdict fields shown in SHOT 7 must come from the actual `run_demo.py` output of the recorded run (copy-paste into an overlay if the terminal font is small).
- Do not display a recipient wallet balance as settlement evidence — studionet does not credit EOAs on `emit_transfer` finalization (CP4 finding). Show the on-chain payout record / `bond_intact` flip instead.
