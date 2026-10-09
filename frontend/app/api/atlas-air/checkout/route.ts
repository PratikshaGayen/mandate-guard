import { NextResponse } from "next/server";
import {
  FARES,
  isAddress,
  isFareKey,
  issueToken,
  merchantOrigin,
  receiptFromToken,
  receiptSha256,
} from "@/lib/merchant/atlasAir";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Buy a fare from the demo merchant.
 * Body: {"fare": "basic-saver" | "flex-economy", "purchaser": "0x…"}
 * Returns the receipt, its URL, and the SHA-256 to commit in record_action.
 */
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Body must be JSON" }, { status: 400 });
  }
  const { fare, purchaser } = (body ?? {}) as { fare?: unknown; purchaser?: unknown };
  if (!isFareKey(fare)) {
    return NextResponse.json(
      { error: "Unknown fare", fares: Object.keys(FARES) },
      { status: 400 },
    );
  }
  if (!isAddress(purchaser)) {
    return NextResponse.json(
      { error: "purchaser must be a 0x-prefixed 20-byte address" },
      { status: 400 },
    );
  }

  const origin = merchantOrigin(req.url);
  const token = issueToken(fare, purchaser, new Date());
  const receipt = receiptFromToken(token, origin);
  if (!receipt) {
    return NextResponse.json({ error: "Could not issue receipt" }, { status: 500 });
  }
  return NextResponse.json({
    receipt,
    receipt_url: origin + "/api/atlas-air/receipts/" + token,
    receipt_sha256: receiptSha256(receipt),
  });
}
