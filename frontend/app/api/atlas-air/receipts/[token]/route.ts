import { canonicalJson, merchantOrigin, receiptFromToken } from "@/lib/merchant/atlasAir";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * The receipt for one purchase, as canonical JSON. Deterministic: every fetch of
 * the same URL returns the same bytes, which is what validators hash-check.
 */
export async function GET(req: Request, ctx: { params: Promise<{ token: string }> }) {
  const { token } = await ctx.params;
  const receipt = receiptFromToken(token, merchantOrigin(req.url));
  if (!receipt) {
    return new Response(JSON.stringify({ error: "Unknown receipt" }), {
      status: 404,
      headers: { "content-type": "application/json" },
    });
  }
  return new Response(canonicalJson(receipt), {
    status: 200,
    headers: {
      "content-type": "application/json",
      "cache-control": "public, max-age=31536000, immutable",
    },
  });
}
