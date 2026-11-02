import { put } from "@vercel/blob";
import { randomUUID } from "node:crypto";

// Early-access interest: stored privately (Vercel Blob, access "private"), only with consent.
// No email is sent and nothing is shared. Needs BLOB_READ_WRITE_TOKEN in the environment.
// Abuse limits: body capped at 4 KB while streaming, honeypot field, and a best-effort
// per-instance rate limit (a shared limiter would need a KV store; see site/DECISIONS.md).

const KINDS = new Set(["operator", "vendor", "research", "other"]);
const EMAIL = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,24}$/;
const MAX_BYTES = 4096;
const WINDOW_MS = 10 * 60_000;
const recent = new Map<string, number[]>();

async function readLimited(req: Request): Promise<string | null> {
  if (!req.body) return "";
  const reader = req.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BYTES) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  return new TextDecoder().decode(Buffer.concat(chunks));
}

function limited(ip: string, now: number) {
  if (recent.size > 5000) recent.clear(); // bound memory
  const hits = (recent.get(ip) ?? []).filter((t) => now - t < WINDOW_MS);
  if (hits.length >= 5) return true;
  recent.set(ip, [...hits, now]);
  return false;
}

export async function POST(req: Request) {
  const now = Date.now();
  const ip = (req.headers.get("x-real-ip") ?? req.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() || "unknown";
  if (limited(ip, now)) return Response.json({ error: "rate_limited" }, { status: 429 });

  const raw = await readLimited(req);
  if (raw === null) return Response.json({ error: "too_large" }, { status: 413 });
  let parsed: unknown;
  try { parsed = JSON.parse(raw); } catch { return Response.json({ error: "bad_json" }, { status: 400 }); }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return Response.json({ error: "bad_body" }, { status: 400 });
  }
  const body = parsed as Record<string, unknown>;

  if (typeof body.website === "string" && body.website.length > 0) return Response.json({ ok: true }); // honeypot
  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  const kind = typeof body.kind === "string" && KINDS.has(body.kind) ? body.kind : "other";
  const message = typeof body.message === "string" ? body.message.slice(0, 1200) : "";
  const locale = body.locale === "pt" ? "pt" : "en";
  if (!EMAIL.test(email)) return Response.json({ error: "invalid_email" }, { status: 400 });
  if (body.consent !== true) return Response.json({ error: "consent_required" }, { status: 400 });
  if (!process.env.BLOB_READ_WRITE_TOKEN) return Response.json({ error: "storage_unavailable" }, { status: 503 });

  const record = { email, kind, message, locale, consent: true, consent_text_version: "2026-11-02", received_at: new Date(now).toISOString() };
  try {
    await put(`interest/${record.received_at.slice(0, 10)}/${randomUUID()}.json`, JSON.stringify(record), {
      access: "private", contentType: "application/json", addRandomSuffix: false,
    });
  } catch {
    return Response.json({ error: "storage_failed" }, { status: 502 });
  }
  return Response.json({ ok: true });
}
