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

    @gl.public.view
    def get_mandate(self, mandate_id: str) -> dict:
        m = self.mandates[mandate_id]
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
