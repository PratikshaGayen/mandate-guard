"""FIX-1 / D16 regression tests — a slashed bond must not be slashed again.

The bug: challenge() never checked bond_intact, and resolve() paid
mandate.bond_wei unconditionally. Two actions on one mandate, both challenged,
both resolving out of mandate paid the bond twice — out of the shared contract
balance, i.e. out of somebody else's money. These tests are the permanent
regression suite for that whole class of bug.

Run with:
    PYTHONIOENCODING=utf-8 pytest tests/direct/test_fix1_double_slash.py -v
"""

import json

import pytest

from tests.direct.test_resolve_leader import (
    BOND_WEI,
    CEILING_WEI,
    DEPOSIT_WEI,
    LISTING_BASIC,
    LISTING_URL,
    MANDATE_TEXT,
    VERDICT_DRIFT,
    WINDOW_SECONDS,
    _hex,
)

CONTRACT_PATH = "contracts/mandate_guard.py"


@pytest.fixture
def payout_capture(direct_vm):
    captured = []

    def hook(vm, request):
        if "PostMessage" in request:
            captured.append(request["PostMessage"])
            return {"ok": None}
        return None

    direct_vm._gl_call_hook = hook
    yield captured
    direct_vm._gl_call_hook = None


def _mandate_with_two_drifting_actions(contract, direct_vm, operator, principal):
    """Register one mandate, record two drifting actions on it."""
    direct_vm.sender = operator
    direct_vm.value = BOND_WEI
    mandate_id = contract.register_mandate(MANDATE_TEXT, _hex(principal), CEILING_WEI, WINDOW_SECONDS)

    direct_vm.value = 0
    action_1 = contract.record_action(
        mandate_id, LISTING_URL, "Basic Saver", "$180.00", "2026-09-05T10:00:00Z"
    )
    action_2 = contract.record_action(
        mandate_id, LISTING_URL, "Basic Saver", "$180.00", "2026-09-05T10:05:00Z"
    )
    return mandate_id, action_1, action_2


def _challenge(direct_vm, contract, challenger, action_id):
    direct_vm.sender = challenger
    direct_vm.value = DEPOSIT_WEI
    return contract.challenge(action_id)


def _resolve_out_of_mandate(direct_vm, contract, caller, challenge_id):
    direct_vm.sender = caller
    direct_vm.value = 0
    return contract.resolve(challenge_id)


def _mock_drifting(direct_vm):
    direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_BASIC})
    direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_DRIFT))
    direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))


class TestD16DoubleSlash:
    def test_second_challenge_rejected_after_slash(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        """The entrance path: after the bond is slashed, no new challenges."""
        contract = direct_deploy(CONTRACT_PATH)
        _mock_drifting(direct_vm)
        mandate_id, action_1, action_2 = _mandate_with_two_drifting_actions(
            contract, direct_vm, direct_alice, direct_bob
        )

        challenge_1 = _challenge(direct_vm, contract, direct_charlie, action_1)
        _resolve_out_of_mandate(direct_vm, contract, direct_alice, challenge_1)

        direct_vm.value = DEPOSIT_WEI
        direct_vm.sender = direct_charlie
        with direct_vm.expect_revert("Bond not intact"):
            contract.challenge(action_2)

    def test_in_flight_challenges_pay_the_bond_exactly_once(
        self,
        direct_vm,
        direct_deploy,
        direct_alice,
        direct_bob,
        direct_charlie,
        payout_capture,
    ):
        """Both challenges opened before either resolves. The first resolve
        pays the bond; the second resolve must skip the bond leg, still return
        the second deposit, and still record the verdict."""
        contract = direct_deploy(CONTRACT_PATH)
        _mock_drifting(direct_vm)
        mandate_id, action_1, action_2 = _mandate_with_two_drifting_actions(
            contract, direct_vm, direct_alice, direct_bob
        )

        challenge_1 = _challenge(direct_vm, contract, direct_charlie, action_1)
        challenge_2 = _challenge(direct_vm, contract, direct_charlie, action_2)

        _resolve_out_of_mandate(direct_vm, contract, direct_alice, challenge_1)
        _resolve_out_of_mandate(direct_vm, contract, direct_alice, challenge_2)

        # The bond is paid exactly once across the whole scenario.
        bond_payments = [p for p in payout_capture if p["value"] == BOND_WEI]
        assert len(bond_payments) == 1

        # Both deposits were returned in full — the second challenger is whole.
        deposit_returns = [p for p in payout_capture if p["value"] == DEPOSIT_WEI]
        assert len(deposit_returns) == 2

        # The second verdict is still recorded, with the skipped leg named.
        c2 = contract.get_challenge(challenge_2)
        assert c2["state"] == "RESOLVED_UPHELD"
        assert c2["verdict_within_mandate"] is False
        purposes = [p["purpose"] for p in c2["payouts"]]
        assert purposes == ["bond_already_slashed_not_paid", "deposit_returned_to_challenger"]
        skipped = c2["payouts"][0]
        assert skipped["amount_wei"] == 0
        assert skipped["recipient"].lower() == _hex(direct_bob).lower()

        # Actions and mandate reflect reality.
        assert contract.get_action(action_2)["state"] == "RESOLVED_OUT_OF_MANDATE"
        assert contract.get_mandate(mandate_id)["bond_intact"] is False

    def test_total_payouts_never_exceed_bond_plus_deposits(
        self,
        direct_vm,
        direct_deploy,
        direct_alice,
        direct_bob,
        direct_charlie,
        payout_capture,
    ):
        """The invariant that would have caught D16: every wei emitted across
        the scenario must come from the bond plus deposits actually paid in."""
        contract = direct_deploy(CONTRACT_PATH)
        _mock_drifting(direct_vm)
        mandate_id, action_1, action_2 = _mandate_with_two_drifting_actions(
            contract, direct_vm, direct_alice, direct_bob
        )

        challenge_1 = _challenge(direct_vm, contract, direct_charlie, action_1)
        challenge_2 = _challenge(direct_vm, contract, direct_charlie, action_2)
        _resolve_out_of_mandate(direct_vm, contract, direct_alice, challenge_1)
        _resolve_out_of_mandate(direct_vm, contract, direct_alice, challenge_2)

        total_out = sum(int(p["value"]) for p in payout_capture)
        total_in = BOND_WEI + 2 * DEPOSIT_WEI
        assert total_out <= total_in
        assert total_out == BOND_WEI + 2 * DEPOSIT_WEI  # exact: both deposits returned


class TestSeverityClamp:
    def _resolve_and_read_severity(self, direct_vm, direct_deploy, direct_alice, direct_bob, sev):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_BASIC})
        verdict = dict(VERDICT_DRIFT)
        verdict["severity"] = sev
        direct_vm.mock_llm(r"adjudicating", json.dumps(verdict))
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))

        direct_vm.sender = direct_alice
        direct_vm.value = BOND_WEI
        mandate_id = contract.register_mandate(
            MANDATE_TEXT, _hex(direct_bob), CEILING_WEI, WINDOW_SECONDS
        )
        direct_vm.value = 0
        action_id = contract.record_action(
            mandate_id, LISTING_URL, "Basic Saver", "$180.00", "2026-09-05T10:00:00Z"
        )
        challenge_id = _challenge(direct_vm, contract, direct_bob, action_id)
        contract.resolve(challenge_id)
        return contract.get_challenge(challenge_id)["verdict_severity"]

    def test_severity_above_100_clamped(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        assert (
            self._resolve_and_read_severity(direct_vm, direct_deploy, direct_alice, direct_bob, 500)
            == 100
        )

    def test_negative_severity_clamped(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        assert (
            self._resolve_and_read_severity(direct_vm, direct_deploy, direct_alice, direct_bob, -5)
            == 0
        )
