"""Tests for resolve() settlement (STEP 7, CP3c), per rulings D11-D15.

Direct mode cannot move balances (D11): emit_transfer is a silent no-op and
contract balances always read 0. These tests therefore capture the emitted
PostMessage payouts via direct_vm._gl_call_hook and assert recipient, exact wei
amount and on == 'finalized' for every leg. Real balance movement is verified
on-chain at STEP 8.

Run with:
    PYTHONIOENCODING=utf-8 pytest tests/direct/test_resolve_settlement.py -v
"""

import json

import pytest

from tests.direct.conftest import to_hex
from tests.direct.test_resolve_leader import (
    BOND_WEI,
    CEILING_WEI,
    DEPOSIT_WEI,
    LISTING_BASIC,
    LISTING_FLEX,
    LISTING_URL,
    MANDATE_TEXT,
    VERDICT_COMPLIANT,
    VERDICT_DRIFT,
    WINDOW_SECONDS,
    _full_path,
    _hex,
)


@pytest.fixture
def payout_capture(direct_vm):
    """Capture emitted value transfers (PostMessage gl_calls) — D11."""
    captured = []

    def hook(vm, request):
        if "PostMessage" in request:
            captured.append(request["PostMessage"])
            return {"ok": None}
        return None

    direct_vm._gl_call_hook = hook
    yield captured
    direct_vm._gl_call_hook = None


class TestSettlementOutOfMandate:
    def test_bond_slashed_to_principal_deposit_returned(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, payout_capture
    ):
        """within_mandate == false: full bond → principal, deposit → challenger."""
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_BASIC})
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_DRIFT))
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_BASIC
        )

        outcome = contract.resolve(challenge_id)

        assert outcome["verdict"]["within_mandate"] is False
        assert len(payout_capture) == 2

        # In _full_path the principal (bob) is also the challenger, so both
        # legs legitimately go to bob: the slashed bond and the returned deposit.
        by_value = sorted((p["value"] for p in payout_capture), reverse=True)
        assert by_value == [BOND_WEI, DEPOSIT_WEI]
        assert all(p["on"] == "finalized" for p in payout_capture)
        assert all(p["address"].as_hex.lower() == _hex(direct_bob).lower() for p in payout_capture)

        m = contract.get_mandate(outcome["verdict"] and _mandate_id(contract, challenge_id))
        assert m["bond_intact"] is False

    def test_states_and_recorded_outcome_after_slash(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, payout_capture
    ):
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_BASIC})
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_DRIFT))
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_BASIC
        )
        action_id = contract.get_challenge(challenge_id)["action_id"]

        contract.resolve(challenge_id)

        a = contract.get_action(action_id)
        assert a["state"] == "RESOLVED_OUT_OF_MANDATE"

        c = contract.get_challenge(challenge_id)
        assert c["state"] == "RESOLVED_UPHELD"
        assert c["verdict_within_mandate"] is False
        assert c["verdict_clause_violated"] == VERDICT_DRIFT["clause_violated"]
        assert c["verdict_severity"] == 2
        assert c["verdict_reasoning"] == VERDICT_DRIFT["reasoning"]
        assert c["resolved_at"] > 0

        recorded = c["payouts"]
        assert len(recorded) == 2
        amounts = {p["purpose"]: p["amount_wei"] for p in recorded}
        assert amounts["bond_slashed_to_principal"] == BOND_WEI
        assert amounts["deposit_returned_to_challenger"] == DEPOSIT_WEI
        assert all(p["recipient"] for p in recorded)


class TestSettlementWithinMandate:
    def test_deposit_forfeited_to_operator_bond_untouched(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, payout_capture
    ):
        """within_mandate == true: deposit → operator, bond untouched."""
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_FLEX})
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        mandate_id = contract.get_challenge(challenge_id)["mandate_id"]
        action_id = contract.get_challenge(challenge_id)["action_id"]

        outcome = contract.resolve(challenge_id)
        assert outcome["verdict"]["within_mandate"] is True

        assert len(payout_capture) == 1
        payout = payout_capture[0]
        assert payout["address"].as_hex.lower() == to_hex(direct_alice).lower()  # operator
        assert payout["value"] == DEPOSIT_WEI
        assert payout["on"] == "finalized"

        m = contract.get_mandate(mandate_id)
        assert m["bond_intact"] is True  # bond untouched

        a = contract.get_action(action_id)
        assert a["state"] == "RESOLVED_WITHIN_MANDATE"

        c = contract.get_challenge(challenge_id)
        assert c["state"] == "RESOLVED_REJECTED"
        assert c["verdict_within_mandate"] is True
        recorded = c["payouts"]
        assert len(recorded) == 1
        assert recorded[0]["purpose"] == "deposit_forfeited_to_operator"
        assert recorded[0]["amount_wei"] == DEPOSIT_WEI


class TestD14ResolveGuard:
    def test_double_resolution_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, payout_capture
    ):
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_FLEX})
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )

        contract.resolve(challenge_id)

        direct_vm.value = 0
        with direct_vm.expect_revert("Already resolved"):
            contract.resolve(challenge_id)

        assert len(payout_capture) == 1  # no second payout emitted

    def test_resolve_unknown_challenge_id_rejected(self, direct_vm, direct_deploy):
        contract = direct_deploy("contracts/mandate_guard.py")
        with direct_vm.expect_revert("Unknown challenge id"):
            contract.resolve("c-999999")

    def test_resolve_is_permissionless(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, payout_capture
    ):
        """D14: anyone may crank resolve — here an uninvolved third party does."""
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_FLEX})
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )

        direct_vm.sender = direct_charlie
        direct_vm.value = 0
        outcome = contract.resolve(challenge_id)
        assert outcome["verdict"]["within_mandate"] is True
        assert len(payout_capture) == 1


class TestD15NoSettleOnFailure:
    def test_failed_resolve_leaves_state_and_money_untouched(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, payout_capture
    ):
        """If the listing is unreachable, nothing settles and nothing is emitted."""
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        # No web mock → the fetch fails.
        action_id = contract.get_challenge(challenge_id)["action_id"]
        mandate_id = contract.get_challenge(challenge_id)["mandate_id"]

        with direct_vm.expect_revert("Resolve failed: fetch_failed"):
            contract.resolve(challenge_id)

        assert len(payout_capture) == 0  # nothing was emitted
        assert contract.get_challenge(challenge_id)["state"] == "OPEN"
        assert contract.get_action(action_id)["state"] == "CHALLENGED"
        assert contract.get_mandate(mandate_id)["bond_intact"] is True

        # And the caller can retry successfully once the page is reachable.
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_FLEX})
        outcome = contract.resolve(challenge_id)
        assert outcome["verdict"]["within_mandate"] is True
        assert len(payout_capture) == 1


def _mandate_id(contract, challenge_id):
    return contract.get_challenge(challenge_id)["mandate_id"]
