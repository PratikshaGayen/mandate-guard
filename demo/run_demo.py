"""Scripted demo agent for Mandate Guard.

Standalone script, not part of the contract. Deploys MandateGuard fresh, registers
a mandate with a bond, then buys two fares from the Atlas Air demo merchant and
records each one bound to the merchant's receipt (D17): the compliant Flex Economy
and the deliberately drifting Basic Saver. It challenges the drift and waits for
resolve() to slash the bond, then waits out the 120-second window and finalizes
the unchallenged compliant purchase (D18). Both paths, end to end, on-chain.

The `challenge` and `resolve` calls here use a genlayer_py account directly rather
than a browser click, because a real MetaMask signature needs a funded human wallet
that this environment does not have (see PROGRESS.md CP5a). The on-chain call is
identical either way — challenge() and resolve() do not know or care whether the
caller was a script or a browser — so the rehearsed timing and settlement outcome
are the real ones the live demo will produce.

Usage:
    python demo/run_demo.py            # continuous run (rehearsal timing)
    python demo/run_demo.py --step     # pause between stages for live narration/video
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gltest_cli.config.general import get_general_config  # noqa: E402
from gltest_cli.config.plugin import PluginConfig  # noqa: E402
from gltest_cli.config.user import load_user_config  # noqa: E402
from gltest import get_contract_factory, get_default_account  # noqa: E402
from gltest.assertions import tx_execution_succeeded  # noqa: E402
from genlayer_py import create_account  # noqa: E402
from genlayer_py.types.transactions import TransactionStatus  # noqa: E402

from demo.merchant import COMPLIANT_FARE, DRIFTING_FARE, buy  # noqa: E402

BOND_WEI = 250 * 10**18
CEILING_WEI = 250 * 10**18
DEPOSIT_WEI = BOND_WEI // 10
# Short enough to finalize the compliant purchase inside one run; still ample to
# challenge the drift (the challenge lands ~15s after it is recorded).
WINDOW_SECONDS = 120

MANDATE_TEXT = (
    "You may book one economy flight ticket from Berlin to Lisbon departing "
    "25 September 2026 for our team trip. Spend at most $250 on the ticket. "
    "Prefer refundable fares over non-refundable ones, even if the refundable "
    "fare costs a bit more."
)

RESOLVE_WAIT = {"wait_interval": 10000, "wait_retries": 60}

STEP_MODE = False  # set by --step: pause for Enter between stages (video narration)


def _maybe_pause(label: str) -> None:
    if STEP_MODE:
        print(f"\n>>> [PAUSED for narration] next: {label} — press Enter to continue...")
        input()


def _timed(label, fn, **kwargs):
    start = time.monotonic()
    result = fn(**kwargs)
    elapsed = time.monotonic() - start
    print(f"[timing] {label}: {elapsed:.1f}s")
    return result, elapsed


def main() -> None:
    global STEP_MODE
    parser = argparse.ArgumentParser(description="Mandate Guard demo agent")
    parser.add_argument(
        "--step",
        action="store_true",
        help="pause for Enter between stages (for live narration / video recording)",
    )
    args = parser.parse_args()
    STEP_MODE = args.step

    general_config = get_general_config()
    general_config.user_config = load_user_config("gltest.config.yaml")
    plugin_config = PluginConfig()
    plugin_config.network_name = "studionet"
    general_config.plugin_config = plugin_config

    operator = get_default_account()
    principal = create_account()
    challenger = create_account()

    print(f"Operator:   {operator.address}")
    print(f"Principal:  {principal.address}")
    print(f"Challenger: {challenger.address}")

    timings = {}

    _maybe_pause("deploy")
    contract, timings["deploy"] = _timed(
        "deploy", lambda: get_contract_factory("MandateGuard").deploy()
    )
    print(f"Contract:   {contract.address}")

    _maybe_pause("register_mandate")
    tx, timings["register_mandate"] = _timed(
        "register_mandate",
        lambda: contract.register_mandate(
            args=[MANDATE_TEXT, principal.address, CEILING_WEI, WINDOW_SECONDS]
        ).transact(value=BOND_WEI),
    )
    assert tx_execution_succeeded(tx), "register_mandate failed"
    mandate_id = contract.get_mandate_ids_by_operator(args=[operator.address]).call()[-1]
    print(f"Mandate:    {mandate_id}  (bond {BOND_WEI / 10**18:g} GEN, ceiling ${CEILING_WEI / 10**18:g})")

    _maybe_pause("buy + record_action (compliant)")
    receipt_url, receipt_sha, receipt = buy(COMPLIANT_FARE, operator.address)
    print(f"Receipt:    {receipt['receipt_id']}  {receipt['item']} ${receipt['amount']}  sha256 {receipt_sha[:16]}…")
    tx, timings["record_compliant"] = _timed(
        "record_action (compliant — Flex Economy $220, refundable)",
        lambda: contract.record_action(args=[mandate_id, receipt_url, receipt_sha]).transact(),
    )
    assert tx_execution_succeeded(tx), "record_action (compliant) failed"

    _maybe_pause("buy + record_action (drifting)")
    receipt_url, receipt_sha, receipt = buy(DRIFTING_FARE, operator.address)
    print(f"Receipt:    {receipt['receipt_id']}  {receipt['item']} ${receipt['amount']}  sha256 {receipt_sha[:16]}…")
    tx, timings["record_drifting"] = _timed(
        "record_action (drifting — Basic Saver $180, non-refundable)",
        lambda: contract.record_action(args=[mandate_id, receipt_url, receipt_sha]).transact(),
    )
    assert tx_execution_succeeded(tx), "record_action (drifting) failed"

    action_ids = contract.get_action_ids_by_mandate(args=[mandate_id]).call()
    compliant_action_id, drifting_action_id = action_ids[0], action_ids[-1]
    drift = contract.get_action(args=[drifting_action_id]).call()
    print(f"Actions:    {action_ids}  (drifting = {drifting_action_id})")
    print(f"Bound:      {drift['item']} {drift['price']} bought by {drift['purchaser']} at {drift['purchased_at']}")

    _maybe_pause("challenge (drifting action)")
    challenger_contract = get_contract_factory("MandateGuard").build_contract(
        contract_address=contract.address, account=challenger
    )
    tx, timings["challenge"] = _timed(
        "challenge (drifting action)",
        lambda: challenger_contract.challenge(args=[drifting_action_id]).transact(value=DEPOSIT_WEI),
    )
    assert tx_execution_succeeded(tx), "challenge failed"
    challenge_id = contract.get_action(args=[drifting_action_id]).call()["open_challenge_id"]
    print(f"Challenge:  {challenge_id}")

    _maybe_pause("resolve (real fetch + real validator consensus — 55-65s)")
    tx, timings["resolve"] = _timed(
        "resolve (real fetch + real validator consensus)",
        lambda: contract.resolve(args=[challenge_id]).transact(
            wait_transaction_status=TransactionStatus.FINALIZED,
            wait_triggered_transactions=True,
            **RESOLVE_WAIT,
        ),
    )
    assert tx_execution_succeeded(tx), "resolve failed"

    verdict = contract.get_challenge(args=[challenge_id]).call()
    mandate_after = contract.get_mandate(args=[mandate_id]).call()

    # D18: the compliant purchase was never challenged. Once its window has
    # passed, anyone can finalize it — here, the challenger account.
    closes_at = int(contract.get_action(args=[compliant_action_id]).call()["challenge_closes_at"])
    wait = closes_at - int(time.time()) + 15  # margin for the transaction's pinned clock
    if wait > 0:
        print(f"\nWaiting {wait}s for the compliant purchase's window to close…")
        time.sleep(wait)
    _maybe_pause("finalize_action (compliant, unchallenged)")
    tx, timings["finalize"] = _timed(
        "finalize_action (compliant, unchallenged)",
        lambda: challenger_contract.finalize_action(args=[compliant_action_id]).transact(),
    )
    assert tx_execution_succeeded(tx), "finalize_action failed"
    compliant_after = contract.get_action(args=[compliant_action_id]).call()

    print()
    print("=== VERDICT ===")
    print(f"  within_mandate:   {verdict['verdict_within_mandate']}")
    print(f"  clause_violated:  {verdict['verdict_clause_violated']}")
    print(f"  severity:         {verdict['verdict_severity']}")
    print(f"  reasoning:        {verdict['verdict_reasoning']}")
    print(f"  challenge state:  {verdict['state']}")
    print(f"  bond_intact:      {mandate_after['bond_intact']}")
    print(f"  payouts:          {verdict['payouts']}")
    print()
    print("=== FINALIZED ===")
    print(f"  {compliant_action_id}: {compliant_after['state']} at {compliant_after['finalized_at']}")

    total = sum(timings.values())
    print()
    print("=== TIMING TABLE ===")
    for label, secs in timings.items():
        print(f"  {label:<20} {secs:6.1f}s")
    print(f"  {'TOTAL':<20} {total:6.1f}s")

    assert verdict["verdict_within_mandate"] is False, "expected the drifting action to be judged out of mandate"
    assert verdict["state"] == "RESOLVED_UPHELD"
    assert mandate_after["bond_intact"] is False
    assert compliant_after["state"] == "UNCHALLENGED"
    print()
    print(
        "Demo complete: drift ruled out of mandate and the bond slashed; the compliant "
        "purchase finalized unchallenged."
    )


if __name__ == "__main__":
    main()
