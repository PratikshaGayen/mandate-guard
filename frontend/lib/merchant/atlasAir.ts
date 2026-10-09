/**
 * Atlas Air — the fictional demo merchant.
 *
 * It sells the two fares on /atlas-air.html and issues a receipt for every
 * purchase. A receipt is only obtainable through checkout: its URL carries an
 * HMAC-SHA256 token over the fare, purchaser and purchase time, so the item,
 * charged amount and timestamp are set by the merchant, not by the buyer.
 * MandateGuard.record_action fetches the receipt, checks its hash, and binds the
 * purchase to it (D17).
 */
import { createHash, createHmac, timingSafeEqual } from "crypto";

export const FARES = {
  "basic-saver": { item: "Basic Saver", amount: "180.00" },
  "flex-economy": { item: "Flex Economy", amount: "220.00" },
} as const;

export type FareKey = keyof typeof FARES;

export type Receipt = Record<
  | "amount"
  | "currency"
  | "item"
  | "listing_url"
  | "merchant"
  | "purchased_at"
  | "purchaser"
  | "receipt_id",
  string
>;

type Payload = { f: FareKey; p: string; t: string };

const ADDRESS = /^0x[0-9a-fA-F]{40}$/;

export function isFareKey(value: unknown): value is FareKey {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(FARES, value);
}

export function isAddress(value: unknown): value is string {
  return typeof value === "string" && ADDRESS.test(value);
}

function secret(): string {
  const value = process.env.ATLAS_AIR_RECEIPT_SECRET;
  if (!value) {
    throw new Error("ATLAS_AIR_RECEIPT_SECRET is not configured");
  }
  return value;
}

export function merchantOrigin(requestUrl: string): string {
  return process.env.ATLAS_AIR_ORIGIN || new URL(requestUrl).origin;
}

function base64url(data: Buffer | string): string {
  return Buffer.from(data).toString("base64url");
}

function sign(encodedPayload: string): string {
  return createHmac("sha256", secret()).update(encodedPayload).digest("base64url");
}

/** Python json.dumps(..., ensure_ascii=True) escaping for one string. */
function pyJsonString(value: string): string {
  return JSON.stringify(value).replace(
    /[\u007f-￿]/g,
    (ch) => "\\u" + ch.charCodeAt(0).toString(16).padStart(4, "0"),
  );
}

/**
 * Byte-identical to Python json.dumps(obj, sort_keys=True, separators=(",", ":")),
 * the form the contract hashes. Receipts hold only string values.
 */
export function canonicalJson(obj: Record<string, string>): string {
  const keys = Object.keys(obj).sort();
  return "{" + keys.map((k) => pyJsonString(k) + ":" + pyJsonString(obj[k])).join(",") + "}";
}

export function receiptSha256(receipt: Receipt): string {
  return createHash("sha256").update(canonicalJson(receipt), "utf8").digest("hex");
}

/** Issue a receipt token for a purchase happening now. */
export function issueToken(fare: FareKey, purchaser: string, purchasedAt: Date): string {
  const payload: Payload = {
    f: fare,
    p: purchaser,
    t: purchasedAt.toISOString().replace(/\.\d{3}Z$/, "Z"),
  };
  const encoded = base64url(JSON.stringify(payload));
  return encoded + "." + sign(encoded);
}

/** Rebuild the receipt behind a token, or null if the token was not issued here. */
export function receiptFromToken(token: string, origin: string): Receipt | null {
  const [encoded, signature, extra] = token.split(".");
  if (!encoded || !signature || extra !== undefined) {
    return null;
  }
  const expected = Buffer.from(sign(encoded));
  const given = Buffer.from(signature);
  if (expected.length !== given.length || !timingSafeEqual(expected, given)) {
    return null;
  }
  let payload: Payload;
  try {
    payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
  } catch {
    return null;
  }
  if (!isFareKey(payload.f) || !isAddress(payload.p) || typeof payload.t !== "string") {
    return null;
  }
  const fare = FARES[payload.f];
  return {
    amount: fare.amount,
    currency: "USD",
    item: fare.item,
    listing_url: origin + "/atlas-air.html",
    merchant: "Atlas Air",
    purchased_at: payload.t,
    purchaser: payload.p,
    receipt_id: "AA-" + signature.slice(0, 12),
  };
}
