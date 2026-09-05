# Handover — STEP 3 (Storage schema + `register_mandate`, checkpoint CP2a)

**For:** the coding agent · **From:** PM · **Date:** 2026-09-05
**Hand this file to the agent along with the repo.** It is self-contained.

CP1 is **APPROVED**. This is the first step that writes real Mandate Guard contract code.

---

## 1. Read these first, in this order

| File | What it is |
|---|---|
| `README.md` | The design. Source of truth for scope. Do not edit. |
| `DESIGN_DECISIONS.md` | **Your spec.** Approved at CP1. D1–D5, demo scenario, verdict schema. |
| `PROJECT_ROADMAP.md` | Plan of record — decision register (§4, now includes D5–D7), verified constraints (§5). |
| `AGENT_INSTRUCTIONS.md` | Standing rules + your task. **You are executing STEP 3 only.** |
| `PROGRESS.md` | History. Read the CP1 entry **and the PM review beneath it** — it contains rulings that change your task. |

Your task is the **STEP 3** block in `AGENT_INSTRUCTIONS.md`. This file adds what's been decided since.

---

## 2. What changed at CP1 review — read before designing anything

Three completions were confirmed, and one carries a consequence for you:

1. **Successful-challenge deposit returns to the challenger.** Confirmed.
2. **Spend ceiling is a principal-declared `u256` wei parameter, never parsed from the mandate prose.** Confirmed.
3. **`challenge` requires the exact deposit** — which means callers must be able to *read* the exact figure. **A `required_deposit` view method is now required** (implemented at STEP 4, but **your storage schema must make it computable**).

**New PM ruling — D7, who calls `register_mandate`.** `DESIGN_DECISIONS.md` left this implicit and you would have hit it immediately.

> **The operator calls `register_mandate` and posts the bond.** The principal's address is passed as a parameter.

Signature (locked):

```
register_mandate(
    text: str,                        # the mandate, plain English
    principal: str,                   # hex address; convert with Address(...)  (PatternTest Pattern 5)
    spend_ceiling_wei: u256,          # principal-declared, sizes the bond (D2)
    challenge_window_seconds: u256,   # default 86400; demo uses 120 (D1)
) -> str                              # returns mandate_id
```

- Decorated `@gl.public.write.payable`; the bond is `gl.message.value`.
- `gl.message.sender_address` is the **operator**. The `principal` parameter is the counterparty.
- Rationale: the bond must be the operator's — that is the entire mechanism ("the bond is the mechanism from step one, posted by the operator who wants permission to act on someone else's money", `README.md`). Since the bond arrives with this call, the caller is necessarily the operator. Keeping it a single call also preserves `README.md`'s four-method surface rather than inventing a separate `post_bond`.
- **Consequence to be aware of, not to solve now:** the operator transcribes the principal's mandate text, so the principal must verify the registered text on-chain before letting the agent act. That's a UI obligation at STEP 10, not a contract change. Do not add an acceptance handshake — that's scope.

---

## 3. Your task, precisely

**Implement:** the storage schema, `register_mandate`, read-back view methods, and direct tests.

**Do NOT implement:** `record_action`, `challenge`, or `resolve`. Those are STEP 4 and beyond. Writing them now means writing them before their design is reviewed.

**But DO design the storage schema for the whole lifecycle now.** This is the one place where looking ahead is required rather than scope creep: if you shape storage around `register_mandate` alone, STEP 4 and STEP 7 will force a refactor of a contract that already has passing tests. The schema must be able to represent, without redesign:

- **Mandates** — text, principal, operator, bond held, spend ceiling, challenge window, whether the bond is still intact.
- **Actions** — the mandate they belong to, merchant URL, item, price, timestamp, `challenge_closes_at` (D1), and current state.
- **Challenges** — the action, the challenger, the deposit held, state, and later the verdict (`within_mandate`, `clause_violated`, `severity`, `reasoning`).
- **A per-action state machine.** At minimum these situations must be distinguishable: open and still challengeable · challenge window elapsed with no challenge · challenge open and awaiting resolution · resolved in the challenger's favour · resolved in the operator's favour. Name the states as you see fit; just make sure none of the above collapse into each other.
- **Enough to compute `required_deposit`** (`bond_wei // u256(10)`, D3) for any action.
- **One open challenge per action** must be enforceable (D3).

Design it, write it down in your CP2a entry, and implement only `register_mandate` against it.

---

## 4. Use the patterns the repo already proves

`contracts/PatternTest.py` ships seven patterns, each backed by tests in `tests/direct/test_patterns.py` that currently pass. **Read it before writing storage code** — it will save you from rediscovering things the hard way. Directly relevant to you now:

- **Pattern 4** — `u256` storage and arithmetic. Your bond, ceiling, window, and deposit are all `u256`.
- **Pattern 5** — the `Address` constructor, including the trap that `str` of raw bytes fails. You need this for the `principal` parameter.
- **Pattern 7** — the **nested-`TreeMap` workaround** (a list stored as a JSON string). `TreeMap[K, TreeMap[...]]` is awkward and calldata only supports `str` keys — you will likely need this for the mandate→actions index.
- **Pattern 6** — `json.dumps(..., sort_keys=True)` for stable output. Not needed this step; essential at STEP 5–6.
- **Patterns 1 & 2** — `gl.vm.Return` type check and partial field matching. That is exactly D4's mechanism. Not this step, but read them so STEP 6 isn't a surprise.

**Runner version header — PM ruling:** start your contract file with the identical header the rest of this repo uses:

```
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

`genvm-lint` will note that a newer runner exists. **Ignore it.** This exact hash is proven working on studionet — both the boilerplate and the STEP 2 probe contract deployed with it. Never use a `latest` or test alias. Chasing a newer runner mid-project trades a known-good dependency for an unknown one, days from a deadline.

---

## 5. Hard storage constraints — where this step actually goes wrong

From `PROJECT_ROADMAP.md` §5, verified against the docs. These are the failure modes for this specific step:

- Persistent fields must be declared **in the class body with type annotations**. A field created as `self.x = ...` that isn't declared there is **silently discarded** after execution — no error, just missing data later.
- `list[T]` → `DynArray[T]`; `dict[K,V]` → `TreeMap[K,V]`; **`int` is forbidden** — use `u256`.
- Only fully instantiated generics: `TreeMap[str, u256]`, never bare `TreeMap`.
- Custom structs need `@allow_storage` + `@dataclass`.
- **Calldata mappings support `str` keys only.** This shapes your ID scheme — prefer `str` IDs.
- Raise `gl.vm.UserError("message")`, **never** a bare `Exception`. The linter flags bare exceptions and they break GenVM error handling. (The boilerplate's own `football_bets.py` violates this in three places — do not copy that habit.)
- Values are wei-denominated `u256`. No floats anywhere on the value path.

---

## 6. Environment — unchanged from STEP 2, repeated because it bites

- **Always** prefix lint/test commands with `PYTHONIOENCODING=utf-8`, or `genvm-lint` crashes with `UnicodeEncodeError` *after passing*:
  ```
  PYTHONIOENCODING=utf-8 genvm-lint check contracts/<your_file>.py
  PYTHONIOENCODING=utf-8 pytest tests/direct/ -v
  ```
- **Do not remove `_patch_windows_stdin_injection()` from `tests/direct/conftest.py`.** It looks like odd dead code; it is load-bearing. Without it every direct test fails with `WinError 32`. With it, 43/43 pass.
- Network is `studionet` (`https://studio.genlayer.com/api`). Local Studio is broken on this machine — don't go near it (`PROGRESS.md` CP0-C).
- Venv: `source .venv/Scripts/activate`. Git baseline: `0a66549`, tree clean. Commit in logical units.
- Ignore the vendor's broken `tests/integration/` suite. Not ours, being deleted.

---

## 7. Tests required

In `tests/direct/`, covering at minimum:

- Successful registration, then read back every stored field and assert it matches what went in.
- Bond **below** `spend_ceiling_wei` → rejected.
- Bond **exactly equal** to the ceiling → accepted (the ruling is `>=`, so the boundary must be proven, not assumed).
- Zero-value registration → rejected.
- Zero `spend_ceiling_wei` → rejected.
- Two mandates registered by different operators don't collide, and their IDs are distinct.

Use `gl.vm.UserError` and assert on the rejection, not just that "something raised".

---

## 8. Definition of done

- Contract file exists in `contracts/` with the pinned runner header.
- Storage schema covers the full lifecycle (§3) even though only `register_mandate` is implemented.
- `PYTHONIOENCODING=utf-8 genvm-lint check contracts/<file>.py` → passes, **no warnings of our own** (the vendor's pre-existing warnings in `football_bets.py` are not yours).
- `PYTHONIOENCODING=utf-8 pytest tests/direct/ -v` → all green, including the 43 that already pass. **Do not break existing tests.**
- A `CP2a` entry appended to `PROGRESS.md` using that file's template, including **the final storage schema written out** and real test output (`N passed in Xs`, not "tests pass").
- **Then stop and wait for PM review.** Do not begin STEP 4.

Stop immediately and write a `BLOCKED` entry if you hit a blocker, an ambiguity, or anything needing a deviation. Deadline **17 Sep 15:30 UTC**; day 3 of 15. Being blocked for an hour is cheap; discovering it on 16 Sep is not.
