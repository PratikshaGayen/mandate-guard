"""Tests for the resolve() leader function (STEP 5, CP3a) and D15 failure handling.

Uses direct_vm.mock_web / mock_llm to simulate the live listing and the LLM.
Run with:
    PYTHONIOENCODING=utf-8 pytest tests/direct/test_resolve_leader.py -v
"""

import json

import pytest

from tests.direct.conftest import to_hex

CONTRACT_PATH = "contracts/mandate_guard.py"

CEILING_WEI = 250 * 10**18
BOND_WEI = 250 * 10**18
DEPOSIT_WEI = BOND_WEI // 10
WINDOW_SECONDS = 3600

LISTING_URL = "https://pratikshagayen.github.io/mandate-guard-demo/"

MANDATE_TEXT = (
    "You may book one economy flight ticket from Berlin to Lisbon departing "
    "25 September 2026 for our team trip. Spend at most $250 on the ticket. "
    "Prefer refundable fares over non-refundable ones, even if the refundable "
    "fare costs a bit more."
)

# The two demo listings (frozen Atlas Air page content, abbreviated to the facts).
LISTING_FLEX = (
    "<html><title>Atlas Air — Flight AA-281</title>"
    "<h3>Flex Economy</h3><span>FULLY REFUNDABLE</span><div>$220.00</div>"
    "<p>This ticket is fully refundable, with free cancellation up to 24 hours "
    "before departure.</p></html>"
)
LISTING_BASIC = (
    "<html><title>Atlas Air — Flight AA-281</title>"
    "<h3>Basic Saver</h3><span>NON-REFUNDABLE</span><div>$180.00</div>"
    "<p>This ticket is non-refundable and cannot be cancelled or changed after "
    "booking.</p></html>"
)

# What a correct adjudicator returns for each demo action.
VERDICT_COMPLIANT = {
    "within_mandate": True,
    "clause_violated": None,
    "severity": 0,
    "reasoning": "Refundable Flex Economy booked at $220.00, within the $250 ceiling.",
}
VERDICT_DRIFT = {
    "within_mandate": False,
    "clause_violated": "Prefer refundable fares over non-refundable ones, even if the "
    "refundable fare costs a bit more.",
    "severity": 2,
    "reasoning": "Non-refundable Basic Saver booked at $180.00 although the refundable "
    "Flex Economy fare was available at $220.00, within the $250 ceiling.",
}


def _hex(raw) -> str:
    return "0x" + raw.hex()


def _full_path(direct_vm, direct_deploy, operator, principal, listing_body):
    """Register → record (compliant or drifting) → challenge. Returns (contract, challenge_id)."""
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = operator
    direct_vm.value = BOND_WEI
    mandate_id = contract.register_mandate(MANDATE_TEXT, _hex(principal), CEILING_WEI, WINDOW_SECONDS)

    direct_vm.value = 0
    if listing_body is LISTING_FLEX:
        action_id = contract.record_action(
            mandate_id, LISTING_URL, "Flex Economy", "$220.00", "2026-09-05T10:00:00Z"
        )
    else:
        action_id = contract.record_action(
            mandate_id, LISTING_URL, "Basic Saver", "$180.00", "2026-09-05T10:00:00Z"
        )

    direct_vm.sender = principal  # anyone may challenge, including the principal
    direct_vm.value = DEPOSIT_WEI
    challenge_id = contract.challenge(action_id)
    return contract, challenge_id


@pytest.fixture
def listing_flex(direct_vm):
    direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_FLEX})


@pytest.fixture
def listing_basic(direct_vm):
    direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_BASIC})


class TestLeaderVerdicts:
    def test_compliant_action_verdict(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )

        verdict = contract.resolve(challenge_id)
        print("\nCOMPLIANT VERDICT JSON:", json.dumps(verdict, sort_keys=True))
        assert verdict["within_mandate"] is True
        assert verdict["clause_violated"] is None
        assert verdict["severity"] == 0
        assert "reasoning" in verdict

    def test_drifting_action_verdict(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_basic
    ):
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_DRIFT))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_BASIC
        )

        verdict = contract.resolve(challenge_id)
        print("\nDRIFTING VERDICT JSON:", json.dumps(verdict, sort_keys=True))
        assert verdict["within_mandate"] is False
        assert verdict["clause_violated"] == VERDICT_DRIFT["clause_violated"]
        assert verdict["severity"] == 2
        assert "reasoning" in verdict

    def test_verdict_prompt_carries_mandate_action_and_listing(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        """The LLM prompt must contain all three adjudication inputs."""
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))

        seen = []
        original_match = direct_vm._match_llm_mock

        def recording_match(prompt):
            seen.append(prompt)
            return original_match(prompt)

        direct_vm._match_llm_mock = recording_match
        try:
            contract, challenge_id = _full_path(
                direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
            )
            contract.resolve(challenge_id)
        finally:
            direct_vm._match_llm_mock = original_match

        prompt = "\n".join(seen)
        assert "Prefer refundable fares" in prompt  # the mandate text
        assert "Flex Economy" in prompt and "$220.00" in prompt  # the recorded action
        assert "FULLY REFUNDABLE" in prompt and "$220.00" in prompt  # the fetched listing


class TestD15FailureCases:
    """A failed fetch or unusable verdict must revert without settling."""

    def test_unreachable_page_reverts(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        # No web mock: the fetch fails.

        with direct_vm.expect_revert("Resolve failed: fetch_failed"):
            contract.resolve(challenge_id)

        assert contract.get_challenge(challenge_id)["state"] == "OPEN"

    def test_error_status_page_reverts(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 500, "body": "Server Error"})

        with direct_vm.expect_revert("Resolve failed: unusable_page"):
            contract.resolve(challenge_id)

        assert contract.get_challenge(challenge_id)["state"] == "OPEN"

    def test_empty_page_reverts(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": "   "})

        with direct_vm.expect_revert("Resolve failed: unusable_page"):
            contract.resolve(challenge_id)

        assert contract.get_challenge(challenge_id)["state"] == "OPEN"

    def test_malformed_llm_output_reverts(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        direct_vm.mock_llm(r"adjudicating", "I believe this purchase is fine.")

        with direct_vm.expect_revert("Resolve failed: llm_invalid_output"):
            contract.resolve(challenge_id)

        assert contract.get_challenge(challenge_id)["state"] == "OPEN"

    def test_llm_json_missing_required_fields_reverts(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        direct_vm.mock_llm(r"adjudicating", json.dumps({"compliant": "yes"}))

        with direct_vm.expect_revert("Resolve failed: llm_invalid_output"):
            contract.resolve(challenge_id)

        assert contract.get_challenge(challenge_id)["state"] == "OPEN"
