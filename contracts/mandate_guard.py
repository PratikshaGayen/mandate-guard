# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
Mandate Guard — enforces a natural-language spending mandate against an AI agent
through a posted operator bond, an optimistic challenge window, and
validator-adjudicated verdicts.

STEP 3 scope: storage schema for the full lifecycle + register_mandate + read-back
views. record_action / challenge / resolve are later steps and are intentionally
absent.

Design decisions referenced below (D1-D5) are locked in DESIGN_DECISIONS.md.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from genlayer import *


@allow_storage
@dataclass
class Mandate:
    id: str
    text: str
    principal: Address
    operator: Address
    bond_wei: u256
    spend_ceiling_wei: u256
    challenge_window_seconds: u256
    created_at: u256
    bond_intact: bool


@allow_storage
@dataclass
class Action:
    id: str
    mandate_id: str
    merchant_url: str
    item: str
    price: str
    purchased_at: str
    recorded_at: u256
    challenge_closes_at: u256
    open_challenge_id: str
    state: str


@allow_storage
@dataclass
class Challenge:
    id: str
    action_id: str
    mandate_id: str
    challenger: Address
    deposit_wei: u256
    opened_at: u256
    state: str
    verdict_within_mandate: bool
    verdict_clause_violated: str
    verdict_severity: u256
    verdict_reasoning: str


# Action states — the five situations that must not collapse into each other.
ACTION_OPEN = "OPEN"  # recorded, challenge window still open
ACTION_UNCHALLENGED = "UNCHALLENGED"  # window elapsed with no challenge
ACTION_CHALLENGED = "CHALLENGED"  # challenge open, awaiting resolution
ACTION_RESOLVED_OUT = "RESOLVED_OUT_OF_MANDATE"  # verdict: bond slashed
ACTION_RESOLVED_IN = "RESOLVED_WITHIN_MANDATE"  # verdict: challenger loses deposit

# Challenge states.
CHALLENGE_OPEN = "OPEN"
CHALLENGE_UPHELD = "RESOLVED_UPHELD"  # action was out of mandate; deposit returned
CHALLENGE_REJECTED = "RESOLVED_REJECTED"  # action within mandate; deposit forfeited


class MandateGuard(gl.Contract):
    mandates: TreeMap[str, Mandate]
    actions: TreeMap[str, Action]
    challenges: TreeMap[str, Challenge]

    # Pattern 7 indexes: JSON-encoded id lists under str keys.
    mandate_ids_by_operator: TreeMap[str, str]
    action_ids_by_mandate: TreeMap[str, str]
    challenge_ids_by_action: TreeMap[str, str]

    mandate_counter: u256
    action_counter: u256
    challenge_counter: u256

    def __init__(self):
        # Storage containers (TreeMap fields) are deliberately NOT constructed
        # here: bare TreeMap() in __init__ breaks storage-desc identity in this
        # SDK when a dataclass-valued TreeMap is declared (verified by probe,
        # see CP2a). Declared fields auto-default on first access — the same
        # proven pattern as the vendor's football_bets.py.
        self.mandate_counter = u256(0)
        self.action_counter = u256(0)
        self.challenge_counter = u256(0)

    @gl.public.write.payable
    def register_mandate(
        self,
        text: str,
        principal: str,
        spend_ceiling_wei: u256,
        challenge_window_seconds: u256,
    ) -> str:
        if int(gl.message.value) == 0:
            raise gl.vm.UserError(
                "Zero value: register_mandate is payable and must carry the operator bond"
            )
        if int(spend_ceiling_wei) == 0:
            raise gl.vm.UserError("Zero ceiling: spend_ceiling_wei must be greater than zero")
        if int(challenge_window_seconds) == 0:
            raise gl.vm.UserError(
                "Zero window: challenge_window_seconds must be greater than zero"
            )
        if not text or not text.strip():
            raise gl.vm.UserError("Empty text: mandate text must not be empty")
        if int(gl.message.value) < int(spend_ceiling_wei):
            raise gl.vm.UserError(
                "Bond below ceiling: value must be at least spend_ceiling_wei (D2)"
            )

        principal_addr = Address(principal)
        operator = gl.message.sender_address
        if principal_addr == operator:
            raise gl.vm.UserError(
                "Principal equals operator: the two parties must be different addresses"
            )

        self.mandate_counter = u256(int(self.mandate_counter) + 1)
        mandate_id = "m-{:06d}".format(int(self.mandate_counter))

        self.mandates[mandate_id] = Mandate(
            id=mandate_id,
            text=text,
            principal=principal_addr,
            operator=operator,
            bond_wei=gl.message.value,
            spend_ceiling_wei=spend_ceiling_wei,
            challenge_window_seconds=challenge_window_seconds,
            created_at=u256(int(datetime.now(timezone.utc).timestamp())),
            bond_intact=True,
        )

        operator_key = operator.as_hex
        id_list = json.loads(self.mandate_ids_by_operator.get(operator_key) or "[]")
        id_list.append(mandate_id)
        self.mandate_ids_by_operator[operator_key] = json.dumps(id_list)

        return mandate_id

    def _get_mandate_or_raise(self, mandate_id: str) -> Mandate:
        mandate = self.mandates.get(mandate_id)
        if mandate is None:
            raise gl.vm.UserError("Unknown mandate id: " + mandate_id)
        return mandate

    def _get_action_or_raise(self, action_id: str) -> Action:
        action = self.actions.get(action_id)
        if action is None:
            raise gl.vm.UserError("Unknown action id: " + action_id)
        return action

    def _get_challenge_or_raise(self, challenge_id: str) -> Challenge:
        challenge = self.challenges.get(challenge_id)
        if challenge is None:
            raise gl.vm.UserError("Unknown challenge id: " + challenge_id)
        return challenge

    @gl.public.write
    def record_action(
        self,
        mandate_id: str,
        merchant_url: str,
        item: str,
        price: str,
        purchased_at: str,
    ) -> str:
        mandate = self._get_mandate_or_raise(mandate_id)
        if gl.message.sender_address != mandate.operator:
            raise gl.vm.UserError(
                "Not operator: only the mandate's registered operator may record actions"
            )
        if not mandate.bond_intact:
            raise gl.vm.UserError(
                "Bond not intact: every recorded action must be backed by a live bond"
            )

        # D9: the window is derived exclusively from the transaction's pinned
        # clock. `purchased_at` is caller-supplied evidence — stored and shown,
        # never used in window arithmetic.
        now = u256(int(datetime.now(timezone.utc).timestamp()))

        self.action_counter = u256(int(self.action_counter) + 1)
        action_id = "a-{:06d}".format(int(self.action_counter))

        self.actions[action_id] = Action(
            id=action_id,
            mandate_id=mandate_id,
            merchant_url=merchant_url,
            item=item,
            price=price,
            purchased_at=purchased_at,
            recorded_at=now,
            challenge_closes_at=u256(int(now) + int(mandate.challenge_window_seconds)),
            open_challenge_id="",
            state=ACTION_OPEN,
        )

        id_list = json.loads(self.action_ids_by_mandate.get(mandate_id) or "[]")
        id_list.append(action_id)
        self.action_ids_by_mandate[mandate_id] = json.dumps(id_list)

        return action_id

    @gl.public.write.payable
    def challenge(self, action_id: str) -> str:
        action = self._get_action_or_raise(action_id)
        if action.open_challenge_id != "":
            raise gl.vm.UserError(
                "Challenge exists: one open challenge per action (D3)"
            )
        now = int(datetime.now(timezone.utc).timestamp())
        if now >= int(action.challenge_closes_at):
            raise gl.vm.UserError("Window closed: the challenge window has elapsed (D1)")

        mandate = self._get_mandate_or_raise(action.mandate_id)
        required_deposit = int(mandate.bond_wei) // 10
        if int(gl.message.value) != required_deposit:
            raise gl.vm.UserError(
                "Wrong deposit: challenge deposit must be exactly bond_wei // 10 (D3)"
            )

        self.challenge_counter = u256(int(self.challenge_counter) + 1)
        challenge_id = "c-{:06d}".format(int(self.challenge_counter))

        self.challenges[challenge_id] = Challenge(
            id=challenge_id,
            action_id=action_id,
            mandate_id=action.mandate_id,
            challenger=gl.message.sender_address,
            deposit_wei=gl.message.value,
            opened_at=u256(now),
            state=CHALLENGE_OPEN,
            # Verdict fields are placeholders until resolve() populates them;
            # state == OPEN is the marker that they are unpopulated.
            verdict_within_mandate=False,
            verdict_clause_violated="",
            verdict_severity=u256(0),
            verdict_reasoning="",
        )

        action.open_challenge_id = challenge_id
        action.state = ACTION_CHALLENGED

        id_list = json.loads(self.challenge_ids_by_action.get(action_id) or "[]")
        id_list.append(challenge_id)
        self.challenge_ids_by_action[action_id] = json.dumps(id_list)

        return challenge_id

    @gl.public.view
    def required_deposit(self, action_id: str) -> int:
        action = self._get_action_or_raise(action_id)
        mandate = self._get_mandate_or_raise(action.mandate_id)
        return int(mandate.bond_wei) // 10

    @gl.public.view
    def get_mandate(self, mandate_id: str) -> dict:
        m = self._get_mandate_or_raise(mandate_id)
        return {
            "id": m.id,
            "text": m.text,
            "principal": m.principal.as_hex,
            "operator": m.operator.as_hex,
            "bond_wei": int(m.bond_wei),
            "spend_ceiling_wei": int(m.spend_ceiling_wei),
            "challenge_window_seconds": int(m.challenge_window_seconds),
            "created_at": int(m.created_at),
            "bond_intact": m.bond_intact,
        }

    @gl.public.view
    def get_mandate_ids_by_operator(self, operator: str) -> list:
        return json.loads(self.mandate_ids_by_operator.get(Address(operator).as_hex) or "[]")

    @gl.public.view
    def get_action_ids_by_mandate(self, mandate_id: str) -> list:
        self._get_mandate_or_raise(mandate_id)
        return json.loads(self.action_ids_by_mandate.get(mandate_id) or "[]")

    @gl.public.view
    def get_action(self, action_id: str) -> dict:
        a = self._get_action_or_raise(action_id)
        # D10: `state` is the stored state; the "window elapsed, unchallenged"
        # transition is derived by the frontend from `challenge_closes_at` vs
        # wall clock. Views never advance stored state.
        out = {
            "id": a.id,
            "mandate_id": a.mandate_id,
            "merchant_url": a.merchant_url,
            "item": a.item,
            "price": a.price,
            "purchased_at": a.purchased_at,
            "recorded_at": int(a.recorded_at),
            "challenge_closes_at": int(a.challenge_closes_at),
            "open_challenge_id": a.open_challenge_id,
            "state": a.state,
        }
        if a.open_challenge_id != "":
            c = self._get_challenge_or_raise(a.open_challenge_id)
            out["challenge"] = {
                "id": c.id,
                "challenger": c.challenger.as_hex,
                "deposit_wei": int(c.deposit_wei),
                "opened_at": int(c.opened_at),
                "state": c.state,
            }
        return out

    @gl.public.view
    def get_challenge(self, challenge_id: str) -> dict:
        c = self._get_challenge_or_raise(challenge_id)
        return {
            "id": c.id,
            "action_id": c.action_id,
            "mandate_id": c.mandate_id,
            "challenger": c.challenger.as_hex,
            "deposit_wei": int(c.deposit_wei),
            "opened_at": int(c.opened_at),
            "state": c.state,
            "verdict_within_mandate": c.verdict_within_mandate,
            "verdict_clause_violated": c.verdict_clause_violated,
            "verdict_severity": int(c.verdict_severity),
            "verdict_reasoning": c.verdict_reasoning,
        }
