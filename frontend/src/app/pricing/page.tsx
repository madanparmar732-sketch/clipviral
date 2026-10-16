"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BadgeCheck, Loader2, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";
import { getAccount, redeemCode, type Account } from "@/lib/api";

const FREE_FEATURES = [
  "♾️ Unlimited videos",
  "🎨 ALL 20 caption styles",
  "✂️ Full clip editor (transcript + style + trim + polish)",
  "🔇 Auto SFX + Auto pause-removal",
  "🎯 AI Reframe (face tracking)",
  "✨ Upscale / Smart Enhance",
  "🎬 Script-to-Video",
  "📱 Long-to-shorts + AI captions",
  "💧 Small ClipViral watermark",
  "📺 Ads on",
  "🚶 Normal speed",
];

const PRO_FEATURES = [
  "🚫 ZERO ads",
  "🚫 NO watermark — clean videos",
  "⚡ SPEED BOOST — jump the processing queue",
  "🎯 That's it. Everything else is FREE forever.",
];

export default function PricingPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [account, setAccount] = useState<Account | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(async ({ data }) => {
      const t = data.session?.access_token ?? "";
      setToken(t);
      if (t) {
        try {
          setAccount(await getAccount(t));
        } catch {
          /* not fatal */
        }
      }
    });
  }, []);

  async function redeem() {
    if (!token) {
      router.push("/login?next=/pricing");
      return;
    }
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const res = await redeemCode(token, code.trim());
      setMsg(res.message);
      setAccount(await getAccount(token));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not activate.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <div className="text-center">
        <h1 className="text-4xl font-extrabold">Simple pricing — everything FREE 💸</h1>
        <p className="mt-2 text-muted-foreground">
          Saare features FREE hain. Pro sirf 2 cheezein deta hai: no ads + speed boost.
        </p>
        {account && (
          <p className="mt-3 text-sm">
            You are on the{" "}
            <span className={account.plan === "pro" ? "font-bold text-emerald-400" : "font-bold text-amber-400"}>
              {account.plan.toUpperCase()}
            </span>{" "}
            plan.
          </p>
        )}
      </div>

      <div className="mt-10 grid gap-6 md:grid-cols-2">
        {/* FREE */}
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
          <h2 className="text-xl font-bold">Free — sab kuch! 🎉</h2>
          <p className="mt-1 text-3xl font-extrabold">
            ₹0<span className="text-base font-normal text-muted-foreground">/forever</span>
          </p>
          <ul className="mt-5 space-y-2 text-sm">
            {FREE_FEATURES.map((f) => (
              <li key={f} className="flex items-center gap-2">
                <BadgeCheck className="h-4 w-4 shrink-0 text-emerald-400" /> {f}
              </li>
            ))}
          </ul>
          <Link href="/dashboard">
            <Button variant="outline" className="mt-6 w-full">
              Start free
            </Button>
          </Link>
        </div>

        {/* PRO */}
        <div className="relative rounded-2xl border border-violet-400/40 bg-gradient-to-b from-violet-500/15 to-fuchsia-500/5 p-6">
          <div className="absolute -top-3 right-6 rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 px-3 py-1 text-xs font-bold">
            CLEAN + FAST ⚡
          </div>
          <h2 className="text-xl font-bold">Pro</h2>
          <p className="mt-1 text-3xl font-extrabold">
            ₹299<span className="text-base font-normal text-muted-foreground">/month</span>
          </p>
          <ul className="mt-5 space-y-2 text-sm">
            {PRO_FEATURES.map((f) => (
              <li key={f} className="flex items-center gap-2">
                <BadgeCheck className="h-4 w-4 shrink-0 text-violet-400" /> {f}
              </li>
            ))}
          </ul>

          <div className="mt-6 space-y-3 rounded-xl border border-white/10 bg-black/20 p-4">
            <p className="text-sm font-semibold">Activate Pro (2 steps):</p>
            <ol className="list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
              <li>
                Pay <b className="text-white">₹299</b> via UPI (owner ka UPI ID chat me maango)
              </li>
              <li>Pro code yahan paste karo ✅</li>
            </ol>
            <div className="flex gap-2">
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Paste your Pro code"
                className="uppercase"
                disabled={busy || account?.plan === "pro"}
              />
              <Button onClick={redeem} disabled={busy || !code.trim() || account?.plan === "pro"}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                Activate
              </Button>
            </div>
            {msg && <p className="text-xs text-emerald-400">✅ {msg}</p>}
            {error && <p className="text-xs text-red-400">❌ {error}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
