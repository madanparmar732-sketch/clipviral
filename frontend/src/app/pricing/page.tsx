"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, BadgeCheck, Check, Crown, Loader2, Sparkles, X, Zap } from "lucide-react";

import Navbar from "@/components/navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";
import { getAccount, redeemCode, type Account } from "@/lib/api";

const FREE_FEATURES = [
  "Unlimited videos & unlimited clips",
  "HyperFinder™ AI moment detection",
  "0–99 Virality Score on every clip (Hook · Flow · Value · Trend)",
  "Face-aware 9:16 / 1:1 / 16:9 reframe",
  "20 animated caption styles — all of them",
  "Full Studio editor: transcript trim, inline word fixes, styling",
  "Auto filler-word & dead-air cutting",
  "AI thumbnails with clickbait titles",
  "Translate + burn captions (10+ languages)",
  "Collections, share links, brand kits",
  "Social export packs + scheduler (.ics)",
  "SRT / VTT subtitle export",
];

const FREE_EXCLUSIVES = ["Ads between actions", "Small ClipViral watermark", "Standard render queue"];

const PRO_FEATURES = [
  "Zero ads anywhere",
  "No watermark — fully clean exports",
  "Speed boost: jump to the front of the render queue",
  "Priority support",
  "Everything else stays exactly the same — you already own it",
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
    <div className="min-h-screen">
      <Navbar />
      <main className="hero-glow container max-w-5xl px-4 py-16 md:py-20">
        {/* header */}
        <div className="mx-auto max-w-2xl text-center">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-indigo-400/25 bg-indigo-500/10 px-4 py-1.5 text-xs font-semibold text-indigo-200">
            <Sparkles className="h-3.5 w-3.5" /> The whole product is free. Really.
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight md:text-5xl">
            Pricing that respects <span className="gradient-text">creators, not whales</span>
          </h1>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            ClipViral charges nothing for clipping, captions, scores or exports — no credit meter,
            no trial timer. Pro exists for people who want a spotless, faster workflow.
          </p>
          {account && (
            <p className="mt-4 text-sm text-muted-foreground">
              Your account:{" "}
              <span className={`font-bold ${account.plan === "pro" ? "text-amber-300" : "text-emerald-400"}`}>
                {account.plan === "pro" ? "PRO ⚡" : "FREE — all features unlocked"}
              </span>
            </p>
          )}
        </div>

        {/* cards */}
        <div className="mt-12 grid items-start gap-6 md:grid-cols-2">
          {/* FREE */}
          <div className="card-lift rounded-3xl border border-white/[0.09] bg-white/[0.03] p-8">
            <p className="eyebrow">Starter</p>
            <h2 className="mt-2 text-2xl font-bold">Free forever</h2>
            <p className="mt-3 flex items-baseline gap-2">
              <span className="text-5xl font-black tracking-tight">₹0</span>
              <span className="text-sm text-muted-foreground">/ no card needed</span>
            </p>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Every AI feature, unlimited videos. This is what 99% of creators will ever need.
            </p>
            <ul className="mt-6 space-y-2.5">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" /> <span className="text-white/85">{f}</span>
                </li>
              ))}
            </ul>
            <p className="mt-6 text-xs text-muted-foreground">The only trade-offs:</p>
            <ul className="mt-1.5 flex flex-wrap gap-2">
              {FREE_EXCLUSIVES.map((f) => (
                <li key={f} className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-white/55">
                  <X className="h-3 w-3 text-white/35" /> {f}
                </li>
              ))}
            </ul>
            <Link href="/dashboard">
              <Button variant="outline" size="lg" className="mt-7 w-full">
                Start free <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>

          {/* PRO */}
          <div className="relative rounded-3xl border border-amber-300/25 bg-gradient-to-b from-amber-400/[0.08] via-violet-500/[0.06] to-transparent p-8 shadow-2xl shadow-amber-500/5">
            <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-amber-400 to-orange-400 px-4 py-1 text-[11px] font-black uppercase tracking-widest text-black shadow-lg shadow-amber-500/30">
              Clean + Fast
            </div>
            <p className="eyebrow text-amber-300/90">Pro</p>
            <h2 className="mt-2 flex items-center gap-2 text-2xl font-bold">
              <Crown className="h-6 w-6 text-amber-300" /> ClipViral Pro
            </h2>
            <p className="mt-3 flex items-baseline gap-2">
              <span className="text-5xl font-black tracking-tight">₹299</span>
              <span className="text-sm text-muted-foreground">/month · cancel anytime</span>
            </p>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Same product, zero friction: no ads, no watermark, front of the render line.
            </p>
            <ul className="mt-6 space-y-2.5">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm">
                  <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" /> <span className="text-white/85">{f}</span>
                </li>
              ))}
            </ul>

            <div className="mt-7 rounded-2xl border border-white/10 bg-black/25 p-5">
              {account?.plan === "pro" ? (
                <p className="text-center text-sm font-semibold text-emerald-400">
                  ✅ Pro is active on this account. Thank you for keeping the servers free for everyone else.
                </p>
              ) : (
                <>
                  <p className="text-sm font-semibold">Have a Pro code? Activate it here.</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    Pay ₹299 via UPI to the number shown on the next screen you get from support, then paste
                    the code you receive — it unlocks instantly on this account.
                  </p>
                  <div className="mt-4 flex gap-2">
                    <Input
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      placeholder="Paste your Pro code"
                      className="uppercase"
                      disabled={busy}
                    />
                    <Button onClick={redeem} disabled={busy || !code.trim()} className="bg-gradient-to-r from-amber-400 to-orange-400 font-bold text-black hover:opacity-90">
                      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                      Activate
                    </Button>
                  </div>
                  {msg && <p className="mt-2 text-xs text-emerald-400">✅ {msg}</p>}
                  {error && <p className="mt-2 text-xs text-red-400">❌ {error}</p>}
                </>
              )}
            </div>
          </div>
        </div>

        {/* why */}
        <div className="mt-14 grid gap-4 text-center sm:grid-cols-3">
          {[
            ["No credit math", "Uploads, clips, exports — none of it costs 'credits'. A 10-hour stream gets the same treatment as a 10-minute talk."],
            ["No feature ransom", "Caption styles, reframing, scoring — tools that are paywalled elsewhere ship free here, permanently."],
            ["Pro just removes friction", "Ads and the watermark are what keep the GPUs running. Pro pays them off for you."],
          ].map(([t, d]) => (
            <div key={t} className="glass rounded-2xl p-6">
              <p className="font-semibold">{t}</p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{d}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
