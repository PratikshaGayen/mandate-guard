"""Scripted demo agent for Mandate Guard — STEP 11 rehearsal (checkpoint CP6).

Standalone script, not part of the contract. Deploys MandateGuard fresh, registers
a mandate with a bond, records the compliant action, then records the deliberately
drifting action from DESIGN_DECISIONS.md — then challenges the drifting action and
waits for resolve() to slash the bond, exactly as the live demo will.

The `challenge` and `resolve` calls here use a genlayer_py account directly rather
than a browser click, because a real MetaMask signature needs a funded human wallet
that this environment does not have (see PROGRESS.md CP5a). The on-chain call is
identical either way — challenge() and resolve() do not know or care whether the
caller was a script or a browser — so the rehearsed timing and settlement outcome
are the real ones the live demo will produce.

Usage:
    python demo/run_demo.py
"""

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

BOND_WEI = 250 * 10**18
CEILING_WEI = 250 * 10**18
DEPOSIT_WEI = BOND_WEI // 10
WINDOW_SECONDS = 86400  # production default

LISTING_URL = "https://pratikshagayen.github.io/mandate-guard-demo/"

MANDATE_TEXT = (
    "You may book one economy flight ticket from Berlin to Lisbon departing "
    "25 September 2026 for our team trip. Spend at most $250 on the ticket. "
    "Prefer refundable fares over non-refundable ones, even if the refundable "
    "fare costs a bit more."
)

RESOLVE_WAIT = {"wait_interval": 10000, "wait_retries": 60}


def _timed(label, fn, **kwargs):
    start = time.monotonic()
    result = fn(**kwargs)
    elapsed = time.monotonic() - start
    print(f"[timing] {label}: {elapsed:.1f}s")
    return result, elapsed


def main() -> None:
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

    contract, timings["deploy"] = _timed(
        "deploy", lambda: get_contract_factory("MandateGuard").deploy()
    )
    print(f"Contract:   {contract.address}")

    tx, timings["register_mandate"] = _timed(
        "register_mandate",
        lambda: contract.register_mandate(
            args=[MANDATE_TEXT, principal.address, CEILING_WEI, WINDOW_SECONDS]
        ).transact(value=BOND_WEI),
    )
    assert tx_execution_succeeded(tx), "register_mandate failed"
    mandate_id = contract.get_mandate_ids_by_operator(args=[operator.address]).call()[-1]
    print(f"Mandate:    {mandate_id}  (bond {BOND_WEI / 10**18:g} GEN, ceiling ${CEILING_WEI / 10**18:g})")

    tx, timings["record_compliant"] = _timed(
        "record_action (compliant — Flex Economy $220, refundable)",
        lambda: contract.record_action(
            args=[mandate_id, LISTING_URL, "Flex Economy", "$220.00", "2026-09-20T10:00:00Z"]
        ).transact(),
    )
    assert tx_execution_succeeded(tx), "record_action (compliant) failed"

    tx, timings["record_drifting"] = _timed(
        "record_action (drifting — Basic Saver $180, non-refundable)",
        lambda: contract.record_action(
            args=[mandate_id, LISTING_URL, "Basic Saver", "$180.00", "2026-09-20T10:05:00Z"]
        ).transact(),
    )
    assert tx_execution_succeeded(tx), "record_action (drifting) failed"

    action_ids = contract.get_action_ids_by_mandate(args=[mandate_id]).call()
    drifting_action_id = action_ids[-1]
    print(f"Actions:    {action_ids}  (drifting = {drifting_action_id})")

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

    print()
    print("=== VERDICT ===")
    print(f"  within_mandate:   {verdict['verdict_within_mandate']}")
    print(f"  clause_violated:  {verdict['verdict_clause_violated']}")
    print(f"  severity:         {verdict['verdict_severity']}")
    print(f"  reasoning:        {verdict['verdict_reasoning']}")
    print(f"  challenge state:  {verdict['state']}")
    print(f"  bond_intact:      {mandate_after['bond_intact']}")
    print(f"  payouts:          {verdict['payouts']}")

    total = sum(timings.values())
    print()
    print("=== TIMING TABLE ===")
    for label, secs in timings.items():
        print(f"  {label:<20} {secs:6.1f}s")
    print(f"  {'TOTAL':<20} {total:6.1f}s")

    assert verdict["verdict_within_mandate"] is False, "expected the drifting action to be judged out of mandate"
    assert verdict["state"] == "RESOLVED_UPHELD"
    assert mandate_after["bond_intact"] is False
    print()
    print("Rehearsal complete: drifting action correctly ruled out of mandate, bond slashed.")


if __name__ == "__main__":
    main()
