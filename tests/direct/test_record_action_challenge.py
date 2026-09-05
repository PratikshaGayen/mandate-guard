"""Tests for record_action, challenge, and the carry-forwards from CP2a review.

Deterministic only — no LLM, no web. Time travel via direct_vm.warp().
Run with:
    PYTHONIOENCODING=utf-8 pytest tests/direct/test_record_action_challenge.py -v
"""

from datetime import datetime, timezone

from tests.direct.conftest import to_hex

CONTRACT_PATH = "contracts/mandate_guard.py"

CEILING_WEI = 250 * 10**18
BOND_WEI = 250 * 10**18
DEPOSIT_WEI = BOND_WEI // 10  # D3
WINDOW_SECONDS = 3600

MANDATE_TEXT = "Test mandate text for record_action and challenge."


def _hex(raw_bytes) -> str:
    return "0x" + raw_bytes.hex()


def _iso(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def _register(contract, direct_vm, operator, principal) -> str:
    direct_vm.sender = operator
    direct_vm.value = BOND_WEI
    return contract.register_mandate(MANDATE_TEXT, _hex(principal), CEILING_WEI, WINDOW_SECONDS)


def _record(contract, direct_vm, operator, mandate_id, url="https://example.com/listing"):
    direct_vm.sender = operator
    direct_vm.value = 0
    return contract.record_action(
        mandate_id,
        url,
        "Flex Economy",
        "$220.00",
        "2026-09-05T10:00:00Z",  # purchased_at: evidence only (D9)
    )


class TestCarryForwardA_PrincipalEqualsOperator:
    def test_register_rejects_principal_equal_to_operator(
        self, direct_vm, direct_deploy, direct_alice
    ):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = BOND_WEI

        with direct_vm.expect_revert("Principal equals operator"):
            contract.register_mandate(
                MANDATE_TEXT, to_hex(direct_alice), CEILING_WEI, WINDOW_SECONDS
            )


class TestCarryForwardB_LookupHelpers:
    def test_get_mandate_unknown_id_raises_user_error(self, direct_vm, direct_deploy):
        contract = direct_deploy(CONTRACT_PATH)
        with direct_vm.expect_revert("Unknown mandate id"):
            contract.get_mandate("m-999999")

    def test_get_action_unknown_id_raises_user_error(self, direct_vm, direct_deploy):
        contract = direct_deploy(CONTRACT_PATH)
        with direct_vm.expect_revert("Unknown action id"):
            contract.get_action("a-999999")

    def test_get_challenge_unknown_id_raises_user_error(self, direct_vm, direct_deploy):
        contract = direct_deploy(CONTRACT_PATH)
        with direct_vm.expect_revert("Unknown challenge id"):
            contract.get_challenge("c-999999")

    def test_record_action_unknown_mandate_id_raises_user_error(
        self, direct_vm, direct_deploy, direct_alice
    ):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        with direct_vm.expect_revert("Unknown mandate id"):
            contract.record_action(
                "m-999999", "https://example.com/", "Item", "$1.00", "2026-09-05T10:00:00Z"
            )

    def test_challenge_unknown_action_id_raises_user_error(
        self, direct_vm, direct_deploy, direct_alice
    ):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = DEPOSIT_WEI
        with direct_vm.expect_revert("Unknown action id"):
            contract.challenge("a-999999")

    def test_required_deposit_unknown_action_id_raises_user_error(
        self, direct_vm, direct_deploy
    ):
        contract = direct_deploy(CONTRACT_PATH)
        with direct_vm.expect_revert("Unknown action id"):
            contract.required_deposit("a-999999")


class TestCarryForwardC_RequiredDeposit:
    def test_required_deposit_is_bond_over_ten(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)
        action_id = _record(contract, direct_vm, direct_alice, mandate_id)

        assert contract.required_deposit(action_id) == BOND_WEI // 10


class TestRecordAction:
    def test_action_recorded_and_read_back_every_field(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)

        direct_vm.warp("2026-09-05T12:00:00Z")
        action_id = _record(
            contract, direct_vm, direct_alice, mandate_id,
            url="https://pratikshagayen.github.io/mandate-guard-demo/",
        )
        assert action_id == "a-000001"

        a = contract.get_action(action_id)
        assert a["id"] == "a-000001"
        assert a["mandate_id"] == mandate_id
        assert a["merchant_url"] == "https://pratikshagayen.github.io/mandate-guard-demo/"
        assert a["item"] == "Flex Economy"
        assert a["price"] == "$220.00"  # stays a string (D8) — evidence, not a number
        assert a["purchased_at"] == "2026-09-05T10:00:00Z"  # evidence only (D9)
        assert a["recorded_at"] == int(datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc).timestamp())
        assert a["challenge_closes_at"] == a["recorded_at"] + WINDOW_SECONDS
        assert a["open_challenge_id"] == ""
        assert a["state"] == "OPEN"
        assert "challenge" not in a

        assert contract.get_action_ids_by_mandate(mandate_id) == [action_id]

    def test_non_operator_cannot_record(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)

        direct_vm.sender = direct_charlie
        direct_vm.value = 0
        with direct_vm.expect_revert("Not operator"):
            contract.record_action(
                mandate_id, "https://example.com/", "Item", "$1.00", "2026-09-05T10:00:00Z"
            )

    def test_record_action_on_slashed_bond_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)

        # Direct-mode-only test setup: on-chain, resolve() sets bond_intact = False
        # (STEP 7). There is no public method that flips it before then.
        contract.mandates[mandate_id].bond_intact = False

        direct_vm.sender = direct_alice
        with direct_vm.expect_revert("Bond not intact"):
            contract.record_action(
                mandate_id, "https://example.com/", "Item", "$1.00", "2026-09-05T10:00:00Z"
            )

    def test_action_ids_indexed_per_mandate(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)
        id_1 = _record(contract, direct_vm, direct_alice, mandate_id)
        id_2 = _record(contract, direct_vm, direct_alice, mandate_id)

        assert contract.get_action_ids_by_mandate(mandate_id) == [id_1, id_2]
        assert id_1 != id_2


class TestChallengeWindow:
    """Window boundary via warp(): inside accepted, at the deadline rejected, outside rejected."""

    def _action_at(self, contract, direct_vm, operator, principal, mandate_id, iso_time):
        direct_vm.warp(iso_time)
        return _record(contract, direct_vm, operator, mandate_id)

    def test_challenge_just_inside_window_accepted(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)
        action_id = self._action_at(
            contract, direct_vm, direct_alice, direct_bob, mandate_id, "2026-09-05T12:00:00Z"
        )
        closes_at = contract.get_action(action_id)["challenge_closes_at"]

        direct_vm.warp(_iso(closes_at - 1))  # one second before the deadline
        direct_vm.sender = direct_charlie
        direct_vm.value = DEPOSIT_WEI
        challenge_id = contract.challenge(action_id)
        assert challenge_id == "c-000001"

    def test_challenge_exactly_at_deadline_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)
        action_id = self._action_at(
            contract, direct_vm, direct_alice, direct_bob, mandate_id, "2026-09-05T12:00:00Z"
        )
        closes_at = contract.get_action(action_id)["challenge_closes_at"]

        direct_vm.warp(_iso(closes_at))  # the deadline itself: now >= closes_at → closed
        direct_vm.sender = direct_charlie
        direct_vm.value = DEPOSIT_WEI
        with direct_vm.expect_revert("Window closed"):
            contract.challenge(action_id)

    def test_challenge_just_outside_window_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)
        action_id = self._action_at(
            contract, direct_vm, direct_alice, direct_bob, mandate_id, "2026-09-05T12:00:00Z"
        )
        closes_at = contract.get_action(action_id)["challenge_closes_at"]

        direct_vm.warp(_iso(closes_at + 1))  # one second past the deadline
        direct_vm.sender = direct_charlie
        direct_vm.value = DEPOSIT_WEI
        with direct_vm.expect_revert("Window closed"):
            contract.challenge(action_id)


class TestChallengeDeposit:
    def _setup(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)
        action_id = _record(contract, direct_vm, direct_alice, mandate_id)
        return contract, action_id

    def test_deposit_below_required_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract, action_id = self._setup(direct_vm, direct_deploy, direct_alice, direct_bob)
        direct_vm.sender = direct_charlie
        direct_vm.value = DEPOSIT_WEI - 1
        with direct_vm.expect_revert("Wrong deposit"):
            contract.challenge(action_id)

    def test_deposit_above_required_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        """The rule is exact equality (CP1) — prove the over-funding direction too."""
        contract, action_id = self._setup(direct_vm, direct_deploy, direct_alice, direct_bob)
        direct_vm.sender = direct_charlie
        direct_vm.value = DEPOSIT_WEI + 1
        with direct_vm.expect_revert("Wrong deposit"):
            contract.challenge(action_id)


class TestOneOpenChallengePerAction:
    def test_second_challenge_rejected_while_first_open(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)
        action_id = _record(contract, direct_vm, direct_alice, mandate_id)

        direct_vm.sender = direct_charlie
        direct_vm.value = DEPOSIT_WEI
        contract.challenge(action_id)

        direct_vm.value = DEPOSIT_WEI
        with direct_vm.expect_revert("Challenge exists"):
            contract.challenge(action_id)

    def test_different_challenger_also_blocked_while_one_open(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        """One open challenge per action — even from a different address."""
        contract = direct_deploy(CONTRACT_PATH)
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)
        action_id = _record(contract, direct_vm, direct_alice, mandate_id)

        direct_vm.sender = direct_charlie
        direct_vm.value = DEPOSIT_WEI
        contract.challenge(action_id)

        direct_vm.sender = direct_bob
        direct_vm.value = DEPOSIT_WEI
        with direct_vm.expect_revert("Challenge exists"):
            contract.challenge(action_id)


class TestEndToEndDeterministicPath:
    def test_register_record_challenge_with_state_assertions(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract = direct_deploy(CONTRACT_PATH)

        # 1. Register — operator posts the bond (D7).
        mandate_id = _register(contract, direct_vm, direct_alice, direct_bob)
        m = contract.get_mandate(mandate_id)
        assert m["bond_intact"] is True
        assert m["operator"].lower() == to_hex(direct_alice).lower()

        # 2. Record action — window opens from the pinned clock (D9).
        direct_vm.warp("2026-09-05T12:00:00Z")
        action_id = _record(contract, direct_vm, direct_alice, mandate_id)
        a = contract.get_action(action_id)
        assert a["state"] == "OPEN"
        assert a["open_challenge_id"] == ""

        # 3. Anyone (here: the principal, explicitly allowed) challenges with the
        #    exact deposit read from the contract, not computed client-side.
        required = contract.required_deposit(action_id)
        assert required == DEPOSIT_WEI
        direct_vm.warp("2026-09-05T12:30:00Z")  # inside the window
        direct_vm.sender = direct_bob
        direct_vm.value = required
        challenge_id = contract.challenge(action_id)

        a = contract.get_action(action_id)
        assert a["state"] == "CHALLENGED"
        assert a["open_challenge_id"] == challenge_id
        assert a["challenge"]["id"] == challenge_id
        assert a["challenge"]["challenger"].lower() == to_hex(direct_bob).lower()
        assert a["challenge"]["deposit_wei"] == DEPOSIT_WEI
        assert a["challenge"]["state"] == "OPEN"
        assert contract.get_action_ids_by_mandate(mandate_id) == [action_id]
