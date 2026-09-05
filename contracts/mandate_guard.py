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
    resolved_at: u256
    payouts_json: str


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


# ── Non-deterministic adjudication helpers ────────────────────────────────────
# These run inside the non-deterministic block only. They never raise: every
# failure becomes a JSON marker {"error": "<category>"}, so both leader and
# validator can agree on "we could not adjudicate" and resolve() can revert
# with a clean UserError (D15) instead of leaving consensus in a failed state.

def _fetch_listing_or_error(url: str) -> tuple:
    """Fetch a listing page. Returns (text, "") on success or ("", "<category>")."""
    try:
        res = gl.nondet.web.get(url)
    except Exception:
        return "", "fetch_failed"
    status = int(res.status)
    body = res.body
    text = ""
    if body is not None:
        text = body.decode("utf-8", errors="replace")
    if status < 200 or status >= 300 or len(text.strip()) == 0:
        return "", "unusable_page"
    return text, ""


def _build_verdict_prompt(mandate_text: str, action_facts: dict, listing_text: str) -> str:
    return (
        "You are adjudicating whether an agent's recorded purchase stayed within a "
        "spending mandate. Judge every clause of the mandate, both numeric limits and "
        "judgment calls.\n\n"
        "MANDATE (plain English):\n" + mandate_text + "\n\n"
        "RECORDED ACTION:\n"
        "item: " + action_facts["item"] + "\n"
        "price: " + action_facts["price"] + "\n"
        "purchased at: " + action_facts["purchased_at"] + "\n"
        "listing url: " + action_facts["merchant_url"] + "\n\n"
        "LIVE LISTING CONTENT fetched from the listing url just now:\n"
        + listing_text + "\n\n"
        "If a clause was violated, quote it exactly as it appears in the mandate.\n"
        "Respond ONLY with JSON in exactly this shape:\n"
        '{"within_mandate": bool, "clause_violated": str or null, "severity": int, '
        '"reasoning": str}\n'
        "severity scale: 0 fully compliant, 1 trivial deviation, 2 clear violation of "
        "one clause, 3 egregious violation.\n"
        "It is mandatory that you respond only using the JSON format above, nothing "
        "else. Your output must be only JSON without any formatting prefix or suffix."
    )


def _coerce_verdict(result) -> dict:
    """Validate and normalise the LLM's verdict, or raise ValueError."""
    if isinstance(result, str):
        s = result.strip().replace("```json", "").replace("```", "").strip()
        start, end = s.find("{"), s.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError("no JSON object found")
        result = json.loads(s[start:end])
    if not isinstance(result, dict):
        raise ValueError("verdict is not an object")
    within = result.get("within_mandate")
    if not isinstance(within, bool):
        raise ValueError("within_mandate is not a bool")
    clause = result.get("clause_violated")
    if clause is not None and not isinstance(clause, str):
        raise ValueError("clause_violated is not a string or null")
    sev = result.get("severity")
    if isinstance(sev, bool) or not isinstance(sev, (int, float)):
        raise ValueError("severity is not a number")
    severity = int(sev)
    if severity < 0:
        severity = 0
    elif severity > 100:
        severity = 100
    reasoning = result.get("reasoning")
    if reasoning is None:
        reasoning = ""
    if not isinstance(reasoning, str):
        reasoning = str(reasoning)
    return {
        "within_mandate": within,
        "clause_violated": clause,
        "severity": severity,
        "reasoning": reasoning,
    }


def _adjudicate_leader(mandate_text: str, action_facts: dict) -> str:
    """Fetch the live listing and judge the recorded action against the mandate.

    Returns the verdict as a JSON string with sorted keys (Pattern 6), or an
    {"error": "<category>"} marker on any failure (D15): fetch_failed,
    unusable_page, or llm_invalid_output.
    """
    listing_text, fetch_error = _fetch_listing_or_error(action_facts["merchant_url"])
    if fetch_error != "":
        return json.dumps({"error": fetch_error}, sort_keys=True)
    task = _build_verdict_prompt(mandate_text, action_facts, listing_text)
    try:
        result = gl.nondet.exec_prompt(task, response_format="json")
        verdict = _coerce_verdict(result)
    except Exception:
        return json.dumps({"error": "llm_invalid_output"}, sort_keys=True)
    return json.dumps(verdict, sort_keys=True)


def _same_clause_semantically(clause_a, clause_b) -> bool:
    """D4: `clause_violated` is compared semantically, never byte-exact.

    Two nulls agree; exactly one null disagrees; two non-null quotes are
    compared by LLM-based comparative judgment (equivalence-principle docs,
    Pattern 3). An unanswerable comparison disagrees — the safe direction.
    """
    a = clause_a or ""
    b = clause_b or ""
    if a == "" and b == "":
        return True
    if a == "" or b == "":
        return False
    task = (
        "CLAUSE-EQUIVALENCE-CHECK: two independent adjudicators each quoted the "
        "mandate clause that was violated. Decide whether the two quotes refer to "
        "the same clause of the same mandate (paraphrases of the same clause count "
        "as the same; different clauses do not).\n"
        'First quote: "' + a + '"\n'
        'Second quote: "' + b + '"\n'
        'Respond ONLY with JSON: {"same": bool}'
    )
    res = gl.nondet.exec_prompt(task, response_format="json")
    if not isinstance(res, dict) or not isinstance(res.get("same"), bool):
        return False
    return res["same"]


def _adjudicate_validator(leader_result, mandate_text: str, action_facts: dict) -> bool:
    """Independently re-fetch and re-derive, then compare per D4.

    The validator runs the same fetch-and-judge procedure the leader ran, but
    against *its own* live fetch and *its own* LLM call. It trusts the leader's
    output for nothing except comparison. Any error inside it counts as
    Disagree (run_nondet_unsafe semantics) — the safe direction: no consensus,
    no settlement.
    """
    if not isinstance(leader_result, gl.vm.Return):
        return False  # leader errored (UserError/VMError) — reject
    raw = leader_result.calldata
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        try:
            leader_verdict = json.loads(raw)
        except ValueError:
            return False
    elif isinstance(raw, dict):
        leader_verdict = raw
    else:
        return False
    derived_json = _adjudicate_leader(mandate_text, action_facts)
    derived_verdict = json.loads(derived_json)
    if "error" in leader_verdict or "error" in derived_verdict:
        # Agree on failure only if both saw exactly the same failure;
        # resolve() then reverts cleanly (D15) rather than settling.
        return leader_verdict == derived_verdict
    # D4 field comparison:
    if bool(leader_verdict.get("within_mandate")) != bool(
        derived_verdict.get("within_mandate")
    ):
        return False  # compared exactly
    return _same_clause_semantically(
        leader_verdict.get("clause_violated"), derived_verdict.get("clause_violated")
    )


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
        mandate = self._get_mandate_or_raise(action.mandate_id)
        # D16: a mandate whose bond is already slashed has nothing left to
        # secure a challenge — taking a deposit against it would be taking
        # money for a promise the contract cannot keep.
        if not mandate.bond_intact:
            raise gl.vm.UserError(
                "Bond not intact: this mandate's bond is already slashed, no new challenges (D16)"
            )
        # Note: open_challenge_id is never cleared, so in this v1 an action can
        # be challenged exactly once ever — a resolved action is adjudicated
        # and must not be re-litigated. The error text below names the weaker
        # rule; the code enforces the stronger one.
        if action.open_challenge_id != "":
            raise gl.vm.UserError(
                "Challenge exists: one open challenge per action (D3)"
            )
        now = int(datetime.now(timezone.utc).timestamp())
        if now >= int(action.challenge_closes_at):
            raise gl.vm.UserError("Window closed: the challenge window has elapsed (D1)")

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
            resolved_at=u256(0),
            payouts_json="",
        )

        action.open_challenge_id = challenge_id
        action.state = ACTION_CHALLENGED

        id_list = json.loads(self.challenge_ids_by_action.get(action_id) or "[]")
        id_list.append(challenge_id)
        self.challenge_ids_by_action[action_id] = json.dumps(id_list)

        return challenge_id

    @gl.public.write
    def resolve(self, challenge_id: str) -> dict:
        challenge = self._get_challenge_or_raise(challenge_id)
        if challenge.state != CHALLENGE_OPEN:
            raise gl.vm.UserError(
                "Already resolved: only an OPEN challenge can be resolved (D14)"
            )
        action = self._get_action_or_raise(challenge.action_id)
        mandate = self._get_mandate_or_raise(challenge.mandate_id)

        # Storage objects cannot be used inside the non-deterministic block —
        # copy the adjudication inputs out first (roadmap §5).
        mandate_text = mandate.text
        action_facts = {
            "item": action.item,
            "price": action.price,
            "purchased_at": action.purchased_at,
            "merchant_url": action.merchant_url,
        }

        def leader_fn() -> str:
            return _adjudicate_leader(mandate_text, action_facts)

        def validator_fn(leader_result) -> bool:
            return _adjudicate_validator(leader_result, mandate_text, action_facts)

        result_json = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        verdict = json.loads(result_json)
        if "error" in verdict:
            # D15: a failed fetch or unusable verdict must not settle. Nothing
            # has been mutated — the caller may retry when the page is reachable.
            raise gl.vm.UserError(
                "Resolve failed: " + verdict["error"] + "; no state changed"
            )

        # ── Settlement (D13) ─────────────────────────────────────────────
        # Payouts are external messages via the ghost contract and execute on
        # finalization, not immediately. All amounts are u256 wei; no floats.
        resolved_at = u256(int(datetime.now(timezone.utc).timestamp()))
        payouts = []

        if not bool(verdict["within_mandate"]):
            # Out of mandate: the full bond goes to the principal; the
            # challenger's deposit is returned in full. (Deliberately the full
            # bond regardless of the size of the violation — README.md's rule,
            # locked at CP3c review. severity is displayed, never scales money.)
            # D16: a challenge opened *before* a slash may still be in flight
            # when it lands. If the bond is already gone, the bond leg is
            # skipped — never paid twice — and the skip is recorded so the UI
            # tells the truth. The challenger is still made whole.
            if mandate.bond_intact and int(mandate.bond_wei) > 0:
                gl.get_contract_at(mandate.principal).emit_transfer(value=mandate.bond_wei)
                payouts.append(
                    {
                        "recipient": mandate.principal.as_hex,
                        "amount_wei": int(mandate.bond_wei),
                        "purpose": "bond_slashed_to_principal",
                    }
                )
            elif not mandate.bond_intact:
                payouts.append(
                    {
                        "recipient": mandate.principal.as_hex,
                        "amount_wei": 0,
                        "purpose": "bond_already_slashed_not_paid",
                    }
                )
            if int(challenge.deposit_wei) > 0:
                gl.get_contract_at(challenge.challenger).emit_transfer(
                    value=challenge.deposit_wei
                )
                payouts.append(
                    {
                        "recipient": challenge.challenger.as_hex,
                        "amount_wei": int(challenge.deposit_wei),
                        "purpose": "deposit_returned_to_challenger",
                    }
                )
            mandate.bond_intact = False
            action.state = ACTION_RESOLVED_OUT
            challenge.state = CHALLENGE_UPHELD
        else:
            # Within mandate: the deposit is forfeited to the operator; the
            # bond is untouched.
            if int(challenge.deposit_wei) > 0:
                gl.get_contract_at(mandate.operator).emit_transfer(value=challenge.deposit_wei)
                payouts.append(
                    {
                        "recipient": mandate.operator.as_hex,
                        "amount_wei": int(challenge.deposit_wei),
                        "purpose": "deposit_forfeited_to_operator",
                    }
                )
            action.state = ACTION_RESOLVED_IN
            challenge.state = CHALLENGE_REJECTED

        # D12: record the outcome in storage — the UI cannot show a slash that
        # only exists in an external message that already left.
        challenge.verdict_within_mandate = bool(verdict["within_mandate"])
        challenge.verdict_clause_violated = str(verdict.get("clause_violated") or "")
        challenge.verdict_severity = u256(int(verdict.get("severity") or 0))
        challenge.verdict_reasoning = str(verdict.get("reasoning") or "")
        challenge.resolved_at = resolved_at
        challenge.payouts_json = json.dumps(payouts, sort_keys=True)

        return {"verdict": verdict, "payouts": payouts, "resolved_at": int(resolved_at)}

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
        payouts = json.loads(c.payouts_json) if c.payouts_json != "" else []
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
            "resolved_at": int(c.resolved_at),
            "payouts": payouts,
        }
