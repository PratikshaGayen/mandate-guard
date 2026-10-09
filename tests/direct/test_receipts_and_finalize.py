"""Receipt binding (D17) and finalize_action (D18).

A recorded purchase must be bound to a merchant receipt that validators fetch and
hash-verify at record time; the item, charged amount, purchaser and timestamp come
from that receipt only. An action whose window closes unchallenged can be
finalized by anyone.

Run with:
    PYTHONIOENCODING=utf-8 pytest tests/direct/test_receipts_and_finalize.py -v
"""

import json
from datetime import datetime, timezone

from tests.direct.conftest import (
    MERCHANT_LISTING_URL,
    canonical_json,
    make_receipt,
    mock_receipt,
    receipt_sha256,
    receipt_url_for,
    record_purchase,
    to_hex,
)

CONTRACT_PATH = "contracts/mandate_guard.py"

CEILING_WEI = 250 * 10**18
BOND_WEI = 250 * 10**18
DEPOSIT_WEI = BOND_WEI // 10
WINDOW_SECONDS = 3600
REGISTERED_AT = "2026-09-05T11:00:00Z"
RECORDED_AT = "2026-09-05T12:00:00Z"


def _hex(raw) -> str:
    return "0x" + raw.hex()


def _iso(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def _registered(direct_vm, direct_deploy, operator, principal):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.warp(REGISTERED_AT)
    direct_vm.sender = operator
    direct_vm.value = BOND_WEI
    mandate_id = contract.register_mandate(
        "Spend at most $250. Prefer refundable fares.", _hex(principal), CEILING_WEI,
        WINDOW_SECONDS,
    )
    direct_vm.warp(RECORDED_AT)
    return contract, mandate_id


def _record_receipt(contract, direct_vm, operator, mandate_id, receipt, url=None, sha=None):
    """Serve `receipt` at its URL and record it, optionally overriding the URL or hash."""
    url = url or receipt_url_for(receipt)
    mock_receipt(direct_vm, url, receipt)
    direct_vm.sender = operator
    direct_vm.value = 0
    return contract.record_action(mandate_id, url, sha or receipt_sha256(receipt))


# ── D17: receipt binding ─────────────────────────────────────────────────────


class TestReceiptBinding:
    def test_purchase_facts_come_from_the_receipt(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(to_hex(direct_alice), "Basic Saver", "180.00", RECORDED_AT)
        action_id = _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt)

        a = contract.get_action(action_id)
        assert a["item"] == "Basic Saver"
        assert a["price"] == "$180.00"
        assert a["purchased_at"] == RECORDED_AT
        assert a["purchaser"] == to_hex(direct_alice)
        assert a["merchant_url"] == MERCHANT_LISTING_URL
        assert a["receipt_id"] == receipt["receipt_id"]
        assert a["receipt_url"] == receipt_url_for(receipt)
        assert a["receipt_sha256"] == receipt_sha256(receipt)

    def test_non_usd_amount_keeps_its_currency(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(
            to_hex(direct_alice), "Flex Economy", "205.00", RECORDED_AT, currency="EUR"
        )
        action_id = _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt)
        assert contract.get_action(action_id)["price"] == "205.00 EUR"

    def test_hash_mismatch_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        """The committed hash pins the receipt: a different document is refused."""
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(to_hex(direct_alice), "Basic Saver", "180.00", RECORDED_AT)
        with direct_vm.expect_revert("receipt_hash_mismatch"):
            _record_receipt(
                contract, direct_vm, direct_alice, mandate_id, receipt, sha="ab" * 32
            )
        assert contract.get_action_ids_by_mandate(mandate_id) == []

    def test_receipt_hash_ignores_key_order_and_whitespace(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        """The hash covers canonical JSON, so transport formatting cannot break it."""
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(to_hex(direct_alice), "Basic Saver", "180.00", RECORDED_AT)
        pretty = json.dumps(dict(reversed(list(receipt.items()))), indent=2)
        url = receipt_url_for(receipt)
        mock_receipt(direct_vm, url, pretty)
        direct_vm.sender = direct_alice
        action_id = contract.record_action(mandate_id, url, receipt_sha256(receipt))
        assert contract.get_action(action_id)["item"] == "Basic Saver"

    def test_purchaser_must_be_the_operator(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(to_hex(direct_charlie), "Basic Saver", "180.00", RECORDED_AT)
        with direct_vm.expect_revert("purchaser on the receipt is not this mandate's operator"):
            _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt)

    def test_receipt_must_share_the_listing_origin(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        """A receipt self-hosted elsewhere does not count as the merchant's."""
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(to_hex(direct_alice), "Basic Saver", "180.00", RECORDED_AT)
        url = receipt_url_for(receipt, origin="https://operator-controlled.test")
        with direct_vm.expect_revert("same https origin"):
            _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt, url=url)

    def test_purchase_before_the_mandate_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(
            to_hex(direct_alice), "Basic Saver", "180.00", "2026-09-01T09:00:00Z"
        )
        with direct_vm.expect_revert("predates the mandate"):
            _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt)

    def test_purchase_in_the_future_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(
            to_hex(direct_alice), "Basic Saver", "180.00", "2026-09-06T12:00:00Z"
        )
        with direct_vm.expect_revert("timestamped in the future"):
            _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt)

    def test_timestamp_without_timezone_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(
            to_hex(direct_alice), "Basic Saver", "180.00", "2026-09-05T12:00:00"
        )
        with direct_vm.expect_revert("not an ISO-8601 timestamp with a timezone"):
            _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt)

    def test_same_receipt_cannot_be_recorded_twice(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(to_hex(direct_alice), "Basic Saver", "180.00", RECORDED_AT)
        first = _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt)
        with direct_vm.expect_revert("already bound to action " + first):
            contract.record_action(mandate_id, receipt_url_for(receipt), receipt_sha256(receipt))

    def test_missing_field_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(to_hex(direct_alice), "Basic Saver", "180.00", RECORDED_AT)
        del receipt["amount"]
        with direct_vm.expect_revert("receipt_missing_amount"):
            _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt)

    def test_unreachable_receipt_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(to_hex(direct_alice), "Basic Saver", "180.00", RECORDED_AT)
        url = receipt_url_for(receipt)
        mock_receipt(direct_vm, url, "Not Found", status=404)
        direct_vm.sender = direct_alice
        with direct_vm.expect_revert("receipt_unusable"):
            contract.record_action(mandate_id, url, receipt_sha256(receipt))

    def test_non_https_receipt_url_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        direct_vm.sender = direct_alice
        with direct_vm.expect_revert("Bad receipt URL"):
            contract.record_action(mandate_id, "http://atlas-air.test/receipts/x", "0" * 64)

    def test_malformed_hash_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        direct_vm.sender = direct_alice
        with direct_vm.expect_revert("Bad receipt hash"):
            contract.record_action(mandate_id, "https://atlas-air.test/receipts/x", "not-a-hash")


class TestReceiptConsensus:
    """The receipt is deterministic data: validators re-fetch and require an exact match."""

    def _recorded(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        receipt = make_receipt(to_hex(direct_alice), "Basic Saver", "180.00", RECORDED_AT)
        _record_receipt(contract, direct_vm, direct_alice, mandate_id, receipt)
        return receipt

    def test_validator_agrees_with_honest_leader(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        self._recorded(direct_vm, direct_deploy, direct_alice, direct_bob)
        assert direct_vm.run_validator() is True

    def test_validator_rejects_a_leader_that_misreports_the_receipt(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        receipt = self._recorded(direct_vm, direct_deploy, direct_alice, direct_bob)
        forged = {k: receipt[k] for k in sorted(receipt)}
        forged["item"] = "Flex Economy"
        forged["amount"] = "220.00"
        assert direct_vm.run_validator(leader_result=canonical_json(forged)) is False

    def test_validator_rejects_when_the_receipt_changed_after_the_leader_read_it(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        """Immutability: the merchant edits the receipt; the validator's own fetch no
        longer matches the committed hash, so it refuses to agree."""
        receipt = self._recorded(direct_vm, direct_deploy, direct_alice, direct_bob)
        tampered = dict(receipt)
        tampered["amount"] = "120.00"
        direct_vm.clear_mocks()
        mock_receipt(direct_vm, receipt_url_for(receipt), tampered)
        assert direct_vm.run_validator() is False

    def test_validator_rejects_an_erroring_leader(
        self, direct_vm, direct_deploy, direct_alice, direct_bob
    ):
        self._recorded(direct_vm, direct_deploy, direct_alice, direct_bob)
        assert direct_vm.run_validator(leader_error=Exception("boom")) is False


# ── D18: finalize_action ─────────────────────────────────────────────────────


class TestFinalizeAction:
    def _open_action(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, mandate_id = _registered(direct_vm, direct_deploy, direct_alice, direct_bob)
        action_id = record_purchase(
            contract, direct_vm, direct_alice, mandate_id, "Flex Economy", "220.00"
        )
        closes_at = contract.get_action(action_id)["challenge_closes_at"]
        return contract, action_id, closes_at

    def test_finalize_before_the_window_closes_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract, action_id, closes_at = self._open_action(
            direct_vm, direct_deploy, direct_alice, direct_bob
        )
        direct_vm.warp(_iso(closes_at - 1))
        direct_vm.sender = direct_charlie
        with direct_vm.expect_revert("Window open"):
            contract.finalize_action(action_id)
        assert contract.get_action(action_id)["state"] == "OPEN"

    def test_finalize_at_the_deadline_by_anyone(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        """Permissionless, and valid from the exact second challenge() stops accepting."""
        contract, action_id, closes_at = self._open_action(
            direct_vm, direct_deploy, direct_alice, direct_bob
        )
        direct_vm.warp(_iso(closes_at))
        direct_vm.sender = direct_charlie  # neither operator nor principal
        result = contract.finalize_action(action_id)

        assert result == {"action_id": action_id, "state": "UNCHALLENGED", "finalized_at": closes_at}
        a = contract.get_action(action_id)
        assert a["state"] == "UNCHALLENGED"
        assert a["finalized_at"] == closes_at

        direct_vm.value = DEPOSIT_WEI
        with direct_vm.expect_revert("Window closed"):
            contract.challenge(action_id)

    def test_finalize_twice_rejected(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        contract, action_id, closes_at = self._open_action(
            direct_vm, direct_deploy, direct_alice, direct_bob
        )
        direct_vm.warp(_iso(closes_at + 10))
        direct_vm.sender = direct_charlie
        contract.finalize_action(action_id)
        with direct_vm.expect_revert("Not finalizable"):
            contract.finalize_action(action_id)

    def test_challenged_action_cannot_be_finalized(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
    ):
        """A challenged action ends through resolve(), never through finalize."""
        contract, action_id, closes_at = self._open_action(
            direct_vm, direct_deploy, direct_alice, direct_bob
        )
        direct_vm.sender = direct_charlie
        direct_vm.value = DEPOSIT_WEI
        contract.challenge(action_id)

        direct_vm.warp(_iso(closes_at + 10))
        direct_vm.value = 0
        with direct_vm.expect_revert("state is CHALLENGED"):
            contract.finalize_action(action_id)

    def test_finalize_unknown_action_rejected(self, direct_vm, direct_deploy):
        contract = direct_deploy(CONTRACT_PATH)
        with direct_vm.expect_revert("Unknown action id"):
            contract.finalize_action("a-999999")
