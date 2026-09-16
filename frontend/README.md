# Mandate Guard — frontend

Next.js 15 UI for the Mandate Guard intelligent contract (`contracts/mandate_guard.py`).

Three surfaces:

- **Mandate editor** — plain-English mandate, principal address, spend ceiling (GEN), challenge window (seconds). Bond = spend ceiling, posted with the registration.
- **Action feed** — per-mandate purchases with evidence (merchant URL, item, price, timestamps) and derived challenge-window state.
- **Verdict panel** — challenge an action (deposit read live from the contract's `required_deposit`, never computed client-side) and display the full structured verdict plus recorded payouts.

## Setup

See the [root README](../README.md#setup) for prerequisites and the deployed contract address.

```bash
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_CONTRACT_ADDRESS
npm run dev
```

Wallet: MetaMask with the GenLayer studionet network added manually (RPC `https://studio.genlayer.com/api`, chain ID `61999`, currency `GEN`).
