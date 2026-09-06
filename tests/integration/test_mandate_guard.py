"""Integration tests for MandateGuard — full lifecycle under real consensus.

These run against a hosted network (studionet) via:
    gltest tests/integration/test_mandate_guard.py -v -s --network studionet

Unlike the direct suite, `resolve()` here performs a REAL web fetch of the live
demo listing and a REAL multi-validator LLM judgment. The demo listing is
frozen and unambiguous, so the expected verdict direction is deterministic even
though the LLM wording is not.

Balance notes (studionet): transaction fees are studio-covered — signer
balances read 0 before and after. The assertions therefore target the passive
parties (principal, contract) whose balances move only by payout amounts.
Payouts execute on finalization, so the resolve() call waits for
FINALIZED rather than merely ACCEPTED.
"""

import time

import pytest
from gltest import get_contract_factory, get_default_account, get_gl_client
from gltest.assertions import tx_execution_succeeded
from gltest.utils import extract_contract_address
from genlayer_py import create_account
from genlayer_py.types.transactions import TransactionStatus

BOND_WEI = 250 * 10**18
CEILING_WEI = 250 * 10**18
DEPOSIT_WEI = BOND_WEI // 10
WINDOW_SECONDS = 86400  # production default; no time warping on a live network

LISTING_URL = "https://pratikshagayen.github.io/mandate-guard-demo/"

MANDATE_TEXT = (
    "You may book one economy flight ticket from Berlin to Lisbon departing "
    "25 September 2026 for our team trip. Spend at most $250 on the ticket. "
    "Prefer refundable fares over non-refundable ones, even if the refundable "
    "fare costs a bit more."
)

# Real multi-validator LLM consensus on a shared network can take minutes.
RESOLVE_WAIT = {"wait_interval": 10000, "wait_retries": 60}


def _balance(client, address: str) -> int:
    resp = client.provider.make_request("eth_getBalance", [address, "latest"])
    return int(resp["result"], 16)


def _timed(label, fn, **kwargs):
    start = time.monotonic()
    result = fn(**kwargs)
    elapsed = time.monotonic() - start
    print(f"[timing] {label}: {elapsed:.1f}s")
    return result, elapsed


class TestFullLifecycle:
    def test_compliant_action_deposit_forfeited_to_operator(self):
        """Compliant path: refundable Flex Economy $220 → within_mandate true,
        deposit forfeited to the operator, bond untouched."""
        client = get_gl_client()
        operator = get_default_account()
        principal = create_account()
        challenger = create_account()

        contract, t_deploy = _timed(
            "deploy", lambda: get_contract_factory("MandateGuard").deploy()
        )

        tx, t = _timed(
            "register_mandate",
            lambda: contract.register_mandate(
                args=[MANDATE_TEXT, principal.address, CEILING_WEI, WINDOW_SECONDS]
            ).transact(value=BOND_WEI),
        )
        assert tx_execution_succeeded(tx)

        mandate_id = contract.get_mandate_ids_by_operator(args=[operator.address]).call()[0]
        mandate = contract.get_mandate(args=[mandate_id]).call()
        assert mandate["text"] == MANDATE_TEXT
        assert mandate["bond_wei"] == BOND_WEI
        assert mandate["bond_intact"] is True
        # The bond is actually held by the contract.
        assert _balance(client, contract.address) == BOND_WEI

        tx, t = _timed(
            "record_action (compliant)",
            lambda: contract.record_action(
                args=[mandate_id, LISTING_URL, "Flex Economy", "$220.00", "2026-09-20T10:00:00Z"]
            ).transact(),
        )
        assert tx_execution_succeeded(tx)
        action_id = contract.get_action_ids_by_mandate(args=[mandate_id]).call()[0]

        challenger_contract = get_contract_factory("MandateGuard").build_contract(
            contract_address=contract.address, account=challenger
        )
        tx, t = _timed(
            "challenge",
            lambda: challenger_contract.challenge(args=[action_id]).transact(value=DEPOSIT_WEI),
        )
        assert tx_execution_succeeded(tx)
        challenge_id = contract.get_action(args=[action_id]).call()["open_challenge_id"]
        assert challenge_id == "c-000001"

        balance_before = _balance(client, principal.address)
        contract_before = _balance(client, contract.address)

        tx, t = _timed(
            "resolve (real fetch + real validator consensus)",
            lambda: contract.resolve(args=[challenge_id]).transact(
                wait_transaction_status=TransactionStatus.FINALIZED,
                wait_triggered_transactions=True,
                **RESOLVE_WAIT,
            ),
        )
        assert tx_execution_succeeded(tx)

        c = contract.get_challenge(args=[challenge_id]).call()
        assert c["state"] == "RESOLVED_REJECTED"
        assert c["verdict_within_mandate"] is True
        assert c["verdict_clause_violated"] is None or c["verdict_clause_violated"] == ""
        assert 0 <= c["verdict_severity"] <= 100
        assert len(c["verdict_reasoning"]) > 0
        assert contract.get_action(args=[action_id]).call()["state"] == "RESOLVED_WITHIN_MANDATE"

        # Balances after finalization: the deposit correctly LEFT the contract.
        assert _balance(client, contract.address) == contract_before - DEPOSIT_WEI
        # Fees are studio-covered; the passive principal's balance is unchanged.
        assert _balance(client, principal.address) == balance_before
        # Same EOA-credit finding as the slash path: the deposit emission to
        # the operator's EOA is recorded on-chain but not credited by the
        # network (see CP4). The payout record is asserted instead.
        payout_record = c["payouts"]
        assert len(payout_record) == 1
        assert payout_record[0]["purpose"] == "deposit_forfeited_to_operator"
        assert int(payout_record[0]["amount_wei"]) == DEPOSIT_WEI

    def test_drifting_action_bond_slashed_to_principal(self):
        """Drifting path: non-refundable Basic Saver $180 → within_mandate false,
        full bond slashed to the principal, deposit returned to the challenger."""
        client = get_gl_client()
        operator = get_default_account()
        principal = create_account()
        challenger = create_account()

        contract, _ = _timed("deploy", lambda: get_contract_factory("MandateGuard").deploy())

        tx, _ = _timed(
            "register_mandate",
            lambda: contract.register_mandate(
                args=[MANDATE_TEXT, principal.address, CEILING_WEI, WINDOW_SECONDS]
            ).transact(value=BOND_WEI),
        )
        assert tx_execution_succeeded(tx)

        mandate_id = contract.get_mandate_ids_by_operator(args=[operator.address]).call()[0]
        tx, _ = _timed(
            "record_action (drifting)",
            lambda: contract.record_action(
                args=[mandate_id, LISTING_URL, "Basic Saver", "$180.00", "2026-09-20T10:00:00Z"]
            ).transact(),
        )
        assert tx_execution_succeeded(tx)
        action_id = contract.get_action_ids_by_mandate(args=[mandate_id]).call()[0]

        challenger_contract = get_contract_factory("MandateGuard").build_contract(
            contract_address=contract.address, account=challenger
        )
        tx, _ = _timed(
            "challenge",
            lambda: challenger_contract.challenge(args=[action_id]).transact(value=DEPOSIT_WEI),
        )
        assert tx_execution_succeeded(tx)
        challenge_id = contract.get_action(args=[action_id]).call()["open_challenge_id"]

        principal_before = _balance(client, principal.address)
        contract_before = _balance(client, contract.address)

        tx, t_resolve = _timed(
            "resolve (real fetch + real validator consensus)",
            lambda: contract.resolve(args=[challenge_id]).transact(
                wait_transaction_status=TransactionStatus.FINALIZED,
                wait_triggered_transactions=True,
                **RESOLVE_WAIT,
            ),
        )
        assert tx_execution_succeeded(tx)

        c = contract.get_challenge(args=[challenge_id]).call()
        assert c["state"] == "RESOLVED_UPHELD"
        assert c["verdict_within_mandate"] is False
        assert len(c["verdict_clause_violated"]) > 0
        assert contract.get_action(args=[action_id]).call()["state"] == "RESOLVED_OUT_OF_MANDATE"
        assert contract.get_mandate(args=[mandate_id]).call()["bond_intact"] is False

        # Balances after finalization: bond + deposit correctly LEFT the
        # contract (verified exactly). FINDING (recorded in CP4): studionet
        # currently does NOT credit emit_transfer payouts to EOA recipients —
        # the external message finalizes via contract_not_found_handler with
        # value_credited=False, reproducible on fresh and existing accounts
        # (see scratch/step8_probe). The payout intent, the exact amounts and
        # the on-chain payout record are verified; the principal's wallet
        # balance cannot be asserted until the network credits EOA payouts.
        assert _balance(client, contract.address) == contract_before - (BOND_WEI + DEPOSIT_WEI)
        payout_record = c["payouts"]
        assert {p["purpose"] for p in payout_record} == {
            "bond_slashed_to_principal",
            "deposit_returned_to_challenger",
        }
        amounts = {p["purpose"]: int(p["amount_wei"]) for p in payout_record}
        assert amounts["bond_slashed_to_principal"] == BOND_WEI
        assert amounts["deposit_returned_to_challenger"] == DEPOSIT_WEI


class TestViewClockOnChain:
    def test_views_see_transaction_pinned_clock(self):
        """Closes the D10 open item: does a @gl.public.view on a live network
        return a meaningful (transaction-pinned) time?"""
        from pathlib import Path

        probe_factory = get_contract_factory(
            contract_file_path="view_clock_probe.py"
        )
        probe = probe_factory.deploy()

        before = int(time.time())
        view_now = probe.view_now(args=[]).call()
        after = int(time.time())
        print(f"[d10] view_now={view_now} wall_clock=[{before},{after}]")
        # A meaningful clock: within ±1 hour of wall clock. If views returned
        # epoch 0 or garbage, this fails — that is the D10 answer.
        assert before - 3600 <= int(view_now) <= after + 3600
