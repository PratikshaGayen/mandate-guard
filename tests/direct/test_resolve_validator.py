"""Tests for the resolve() validator function (STEP 6, CP3b).

The validator independently re-fetches and re-derives its own verdict, then
compares per D4: within_mandate exactly, clause_violated semantically,
severity/reasoning excluded. direct_vm.run_validator() exercises the captured
validator; swapping mocks between the contract call and run_validator()
simulates a validator that sees different external data.

Run with:
    PYTHONIOENCODING=utf-8 pytest tests/direct/test_resolve_validator.py -v
"""

import json

import pytest

from tests.direct.test_resolve_leader import (
    CEILING_WEI,
    DEPOSIT_WEI,
    LISTING_BASIC,
    LISTING_FLEX,
    LISTING_URL,
    BOND_WEI,
    MANDATE_TEXT,
    VERDICT_COMPLIANT,
    VERDICT_DRIFT,
    WINDOW_SECONDS,
    _full_path,
    _hex,
)
from tests.direct.test_resolve_leader import _full_path as setup_path

CONTRACT_PATH = "contracts/mandate_guard.py"


@pytest.fixture
def listing_flex(direct_vm):
    direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_FLEX})


class TestValidatorAgreement:
    def test_validator_agrees_with_correct_leader_verdict(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        contract.resolve(challenge_id)

        assert direct_vm.run_validator() is True

    def test_validator_agrees_on_failure_marker_agreement(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        """Leader and validator both see the page down: they agree on the error
        marker, and resolve() reverts cleanly (D15) rather than settling."""
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        # No web mock → both fetches fail with the identical marker.

        with direct_vm.expect_revert("Resolve failed: fetch_failed"):
            contract.resolve(challenge_id)

        assert direct_vm.run_validator() is True


class TestValidatorRejections:
    def test_validator_rejects_flipped_within_mandate(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        """The core consensus test: the leader's verdict says compliant, but the
        validator's own re-derivation says violation → Disagree."""
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )

        contract.resolve(challenge_id)

        # Swap the LLM mock: the validator now derives the drifting verdict.
        direct_vm._llm_mocks.clear()
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_DRIFT))

        forged = dict(VERDICT_COMPLIANT)
        assert direct_vm.run_validator(leader_result=json.dumps(forged)) is False

    def test_validator_rejects_when_its_own_fetch_sees_a_different_listing(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        """The disagreement mechanism end to end: the validator re-fetches the
        live listing and gets different page content, so its independently
        derived verdict differs from the leader's."""
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )

        contract.resolve(challenge_id)

        # The page changed between the leader's fetch and the validator's:
        # it now shows the non-refundable Basic Saver fare.
        direct_vm._web_mocks.clear()
        direct_vm._llm_mocks.clear()
        direct_vm.mock_web(r"pratikshagayen\.github\.io", {"status": 200, "body": LISTING_BASIC})
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_DRIFT))

        assert direct_vm.run_validator(leader_result=json.dumps(VERDICT_COMPLIANT)) is False

    def test_validator_rejects_leader_error(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        contract.resolve(challenge_id)

        assert direct_vm.run_validator(leader_error=ValueError("boom")) is False

    def test_validator_rejects_malformed_leader_json(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )
        contract.resolve(challenge_id)

        assert direct_vm.run_validator(leader_result="not json at all") is False

    def test_validator_rejects_when_exactly_one_side_saw_a_violation_clause(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        """Both agree the action is compliant, but only the leader quoted a
        violated clause — one null, one non-null → Disagree."""
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_COMPLIANT))
        contract, challenge_id = _full_path(
            direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_FLEX
        )

        leader_verdict = dict(VERDICT_COMPLIANT)
        leader_verdict["clause_violated"] = "Spend at most $250 on the ticket."
        contract.resolve(challenge_id)

        assert direct_vm.run_validator(leader_result=json.dumps(leader_verdict)) is False


class TestSemanticClauseComparison:
    def _resolved(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        direct_vm.mock_llm(r"adjudicating", json.dumps(VERDICT_DRIFT))
        return _full_path(direct_vm, direct_deploy, direct_alice, direct_bob, LISTING_BASIC)

    def test_paraphrased_clauses_agree(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        """D4: clause_violated compares semantically — a paraphrase of the same
        clause must pass even though the strings differ."""
        contract, challenge_id = self._resolved(direct_vm, direct_deploy, direct_alice, direct_bob)

        leader_verdict = dict(VERDICT_DRIFT)
        leader_verdict["clause_violated"] = "prefer refundable fares"  # short paraphrase
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))
        contract.resolve(challenge_id)

        assert direct_vm.run_validator(leader_result=json.dumps(leader_verdict)) is True

    def test_different_clauses_disagree(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        contract, challenge_id = self._resolved(direct_vm, direct_deploy, direct_alice, direct_bob)

        leader_verdict = dict(VERDICT_DRIFT)
        leader_verdict["clause_violated"] = "Spend at most $250 on the ticket."  # different clause
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": False}))
        contract.resolve(challenge_id)

        assert direct_vm.run_validator(leader_result=json.dumps(leader_verdict)) is False

    def test_severity_and_reasoning_are_excluded_from_consensus(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        """D4: severity and reasoning may differ wildly without breaking agreement."""
        contract, challenge_id = self._resolved(direct_vm, direct_deploy, direct_alice, direct_bob)

        leader_verdict = dict(VERDICT_DRIFT)
        leader_verdict["severity"] = 3
        leader_verdict["reasoning"] = "A completely different explanation."
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", json.dumps({"same": True}))
        contract.resolve(challenge_id)

        assert direct_vm.run_validator(leader_result=json.dumps(leader_verdict)) is True

    def test_unanswerable_clause_comparison_disagrees(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, listing_flex
    ):
        """If the equivalence-check LLM returns garbage, the safe direction is Disagree."""
        contract, challenge_id = self._resolved(direct_vm, direct_deploy, direct_alice, direct_bob)

        leader_verdict = dict(VERDICT_DRIFT)
        leader_verdict["clause_violated"] = "prefer refundable fares"
        direct_vm.mock_llm(r"CLAUSE-EQUIVALENCE-CHECK", "I cannot answer that.")
        contract.resolve(challenge_id)

        assert direct_vm.run_validator(leader_result=json.dumps(leader_verdict)) is False
