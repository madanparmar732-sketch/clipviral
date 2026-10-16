"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BadgeCheck, Loader2, Sparkles, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";
import { getAccount, redeemCode, type Account } from "@/lib/api";

const FREE_FEATURES = [
  "3 videos / month",
  "3 caption styles",
  "720p output",
  "ClipViral watermark",
  "Ads on dashboard",
  "Transcript editor (basic)",
];

const PRO_FEATURES = [
  "♾️ Unlimited videos",
  "🎨 ALL 20 caption styles",
  "✨ 1080p + Smart Enhance (Upscale)",
  "🚫 No watermark",
  "⚡ Priority speed (jump the queue!)",
  "🔇 Auto SFX + Auto pause-removal",
  "✂️ Pro Editor: trim + style + polish",
  "🎯 AI Reframe (face tracking)",
  "🎬 Script-to-Video (Beta)",
  "🗣️ Voice dubbing (Beta soon)",
  "📺 Zero ads",
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
        <h1 className="text-4xl font-extrabold">Simple, honest pricing 💸</h1>
        <p className="mt-2 text-muted-foreground">
          Free forever for light use. Pro when you&apos;re ready to go viral daily.
        </p>
        {account && (
          <p className="mt-3 text-sm">
            You are on the{" "}
            <span className={account.plan === "pro" ? "font-bold text-emerald-400" : "font-bold text-amber-400"}>
              {account.plan.toUpperCase()}
            </span>{" "}
            plan
            {account.videos_limit
              ? ` — ${account.videos_used_this_month}/${account.videos_limit} videos used this month`
              : " — unlimited videos"}
            .
          </p>
        )}
      </div>

      <div className="mt-10 grid gap-6 md:grid-cols-2">
        {/* FREE */}
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
          <h2 className="text-xl font-bold">Free</h2>
          <p className="mt-1 text-3xl font-extrabold">
            ₹0<span className="text-base font-normal text-muted-foreground">/month</span>
          </p>
          <ul className="mt-5 space-y-2 text-sm">
            {FREE_FEATURES.map((f) => (
              <li key={f} className="flex items-center gap-2">
                <span className="text-muted-foreground">•</span> {f}
              </li>
            ))}
          </ul>
          <Link href="/dashboard">
            <Button variant="outline" className="mt-6 w-full">
              Stay Free
            </Button>
          </Link>
        </div>

        {/* PRO */}
        <div className="relative rounded-2xl border border-violet-400/40 bg-gradient-to-b from-violet-500/15 to-fuchsia-500/5 p-6">
          <div className="absolute -top-3 right-6 rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 px-3 py-1 text-xs font-bold">
            MOST POPULAR 🔥
          </div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Sparkles className="h-5 w-5 text-violet-400" /> Pro
          </h2>
          <p className="mt-1 text-3xl font-extrabold">
            ₹299<span className="text-base font-normal text-muted-foreground">/month</span>
          </p>
          <ul className="mt-5 space-y-2 text-sm">
            {PRO_FEATURES.map((f) => (
              <li key={f} className="flex items-center gap-2">
                <BadgeCheck className="h-4 w-4 shrink-0 text-emerald-400" /> {f}
              </li>
            ))}
          </ul>

          <div className="mt-6 space-y-3 rounded-xl border border-white/10 bg-black/20 p-4">
            <p className="text-sm font-semibold">Activate Pro (2 steps):</p>
            <ol className="list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
              <li>
                Pay <b className="text-white">₹299</b> via UPI to the owner&apos;s UPI ID (ask in chat / on the
                contact page)
              </li>
              <li>Receive your unique Pro code → paste it below ✅</li>
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

      <p className="mt-10 text-center text-xs text-muted-foreground">
        Payments are handled person-to-person via UPI for now (zero fees 🇮🇳). Online card/UPI checkout
        (Razorpay) is coming soon.
      </p>
    </div>
  );
}
