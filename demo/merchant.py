"""Client for the Atlas Air demo merchant (D17).

An agent buys a fare through the merchant's checkout and gets back a receipt URL.
`record_action` commits that URL plus the receipt's SHA-256; validators fetch the
receipt and check it. The hash is recomputed here from the fetched receipt rather
than taken from the merchant's response, so a mismatch is caught before any gas
is spent.
"""

import hashlib
import json
import os
import urllib.error
import urllib.request

MERCHANT_ORIGIN = os.environ.get("ATLAS_AIR_ORIGIN", "https://mandate-guard-five.vercel.app")
LISTING_URL = MERCHANT_ORIGIN + "/atlas-air.html"
COMPLIANT_FARE = "flex-economy"  # Flex Economy, $220.00, fully refundable
DRIFTING_FARE = "basic-saver"  # Basic Saver, $180.00, non-refundable


def canonical_json(obj) -> str:
    """The form MandateGuard hashes: sorted keys, compact separators, ASCII."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def receipt_sha256(receipt: dict) -> str:
    return hashlib.sha256(canonical_json(receipt).encode("utf-8")).hexdigest()


def _request(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{url} -> HTTP {exc.code}: {exc.read()[:200]!r}") from exc


def buy(fare: str, purchaser: str) -> tuple[str, str, dict]:
    """Buy `fare` as `purchaser`. Returns (receipt_url, receipt_sha256, receipt)."""
    order = _request(MERCHANT_ORIGIN + "/api/atlas-air/checkout", {"fare": fare, "purchaser": purchaser})
    receipt = _request(order["receipt_url"])
    sha = receipt_sha256(receipt)
    if sha != order["receipt_sha256"]:
        raise RuntimeError("merchant receipt hash disagrees with the served receipt")
    return order["receipt_url"], sha, receipt
