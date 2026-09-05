"""Tests for register_mandate and the storage schema (STEP 3, CP2a).

Deterministic only — no LLM, no web. Run with:
    PYTHONIOENCODING=utf-8 pytest tests/direct/test_register_mandate.py -v
"""

import pytest

from tests.direct.conftest import to_hex

CONTRACT_PATH = "contracts/mandate_guard.py"

# 250 GEN in wei — the demo scenario's ceiling (README.md model: "$250").
CEILING_WEI = 250 * 10**18
BOND_WEI = 250 * 10**18  # D2: bond >= ceiling, 1:1
WINDOW_SECONDS = 86400  # D1 production default

MANDATE_TEXT = (
    "You may book one economy flight ticket from Berlin to Lisbon departing "
    "25 September 2026 for our team trip. Spend at most $250 on the ticket. "
    "Prefer refundable fares over non-refundable ones, even if the refundable "
    "fare costs a bit more."
)


def _hex_address(raw_bytes) -> str:
    return "0x" + raw_bytes.hex()


class TestRegisterMandateSuccess:
    def test_register_and_read_back_every_field(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = BOND_WEI

        mandate_id = contract.register_mandate(
            MANDATE_TEXT,
            _hex_address(direct_bob),
            CEILING_WEI,
            WINDOW_SECONDS,
        )

        assert mandate_id == "m-000001"

        m = contract.get_mandate(mandate_id)
        assert m["id"] == "m-000001"
        assert m["text"] == MANDATE_TEXT
        # D7: sender is the operator, the parameter is the principal.
        assert m["operator"].lower() == to_hex(direct_alice).lower()
        assert m["principal"].lower() == to_hex(direct_bob).lower()
        assert m["bond_wei"] == BOND_WEI
        assert m["spend_ceiling_wei"] == CEILING_WEI
        assert m["challenge_window_seconds"] == WINDOW_SECONDS
        assert m["created_at"] > 0
        assert m["bond_intact"] is True

    def test_bond_exactly_equal_to_ceiling_accepted(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        """D2 ruling is >=, so the boundary value must be proven, not assumed."""
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = CEILING_WEI  # exactly the ceiling, not more

        mandate_id = contract.register_mandate(
            MANDATE_TEXT, _hex_address(direct_bob), CEILING_WEI, WINDOW_SECONDS
        )
        assert contract.get_mandate(mandate_id)["bond_wei"] == CEILING_WEI

    def test_operator_index_lists_the_mandate(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = BOND_WEI
        mandate_id = contract.register_mandate(
            MANDATE_TEXT, _hex_address(direct_bob), CEILING_WEI, WINDOW_SECONDS
        )

        ids = contract.get_mandate_ids_by_operator(to_hex(direct_alice))
        assert ids == [mandate_id]


class TestRegisterMandateRejections:
    def test_bond_below_ceiling_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = CEILING_WEI - 1  # one wei short

        with direct_vm.expect_revert("Bond below ceiling"):
            contract.register_mandate(
                MANDATE_TEXT, _hex_address(direct_bob), CEILING_WEI, WINDOW_SECONDS
            )

    def test_zero_value_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = 0

        with direct_vm.expect_revert("Zero value"):
            contract.register_mandate(
                MANDATE_TEXT, _hex_address(direct_bob), CEILING_WEI, WINDOW_SECONDS
            )

    def test_zero_spend_ceiling_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = BOND_WEI

        with direct_vm.expect_revert("Zero ceiling"):
            contract.register_mandate(
                MANDATE_TEXT, _hex_address(direct_bob), 0, WINDOW_SECONDS
            )

    def test_zero_challenge_window_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = BOND_WEI

        with direct_vm.expect_revert("Zero window"):
            contract.register_mandate(
                MANDATE_TEXT, _hex_address(direct_bob), CEILING_WEI, 0
            )

    def test_empty_text_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = BOND_WEI

        with direct_vm.expect_revert("Empty text"):
            contract.register_mandate(
                "   ", _hex_address(direct_bob), CEILING_WEI, WINDOW_SECONDS
            )

    def test_rejected_registration_stores_nothing(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        """After a rejection, the operator's index must still be empty."""
        contract = direct_deploy(CONTRACT_PATH)
        direct_vm.sender = direct_alice
        direct_vm.value = CEILING_WEI - 1

        with direct_vm.expect_revert("Bond below ceiling"):
            contract.register_mandate(
                MANDATE_TEXT, _hex_address(direct_bob), CEILING_WEI, WINDOW_SECONDS
            )

        assert contract.get_mandate_ids_by_operator(to_hex(direct_alice)) == []


class TestMandateIsolation:
    def test_two_operators_no_collision_distinct_ids(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract = direct_deploy(CONTRACT_PATH)

        direct_vm.sender = direct_alice
        direct_vm.value = BOND_WEI
        id_1 = contract.register_mandate(
            MANDATE_TEXT, _hex_address(direct_bob), CEILING_WEI, WINDOW_SECONDS
        )

        direct_vm.sender = direct_charlie
        direct_vm.value = BOND_WEI
        id_2 = contract.register_mandate(
            "Second, entirely different mandate text.",
            _hex_address(direct_bob),
            CEILING_WEI,
            WINDOW_SECONDS,
        )

        assert id_1 != id_2

        m1 = contract.get_mandate(id_1)
        m2 = contract.get_mandate(id_2)
        assert m1["text"] == MANDATE_TEXT
        assert m2["text"] == "Second, entirely different mandate text."
        assert m1["operator"].lower() == to_hex(direct_alice).lower()
        assert m2["operator"].lower() == to_hex(direct_charlie).lower()
        assert m1["principal"].lower() == to_hex(direct_bob).lower()
        assert m2["principal"].lower() == to_hex(direct_bob).lower()

        assert contract.get_mandate_ids_by_operator(to_hex(direct_alice)) == [id_1]
        assert contract.get_mandate_ids_by_operator(to_hex(direct_charlie)) == [id_2]
