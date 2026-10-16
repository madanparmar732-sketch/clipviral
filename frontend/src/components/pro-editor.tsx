"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, Lock, Scissors, Sparkles, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { proEditClip, type Account, type Clip } from "@/lib/api";

/**
 * Pro Editor v1: pick one of 20 caption styles, trim, and toggle polish
 * (SFX, Enhance, Reframe) — then re-renders the clip in FULL quality.
 */
export default function ProEditor({
  clip,
  token,
  account,
}: {
  clip: Clip;
  token: string;
  account: Account | null;
}) {
  const [open, setOpen] = useState(false);
  const [style, setStyle] = useState(account?.caption_style ?? "beast");
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(Math.round(clip.end_seconds ?? 30));
  const [sfx, setSfx] = useState(account?.sfx ?? false);
  const [enhance, setEnhance] = useState(account?.enhance ?? false);
  const [reframe, setReframe] = useState(account?.reframe ?? "face");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isPro = account?.plan === "pro";
  const allStyles = account?.all_styles ?? ["beast", "minimal", "bold_box"];
  const freeStyles = new Set(account?.free_styles ?? ["beast", "minimal", "bold_box"]);

  async function apply() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const res = await proEditClip(token, clip.id, {
        style,
        trim_start: trimStart,
        trim_end: trimEnd,
        sfx,
        enhance,
        reframe,
      });
      setMsg(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Editor failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <Button size="sm" variant="outline" className="w-full" onClick={() => setOpen(!open)}>
        <Wand2 className="h-4 w-4" /> {open ? "Hide Pro Editor" : "✨ Pro Editor"}
        {!isPro && <Lock className="ml-1 h-3 w-3" />}
      </Button>

      {open && (
        <div className="space-y-4 rounded-lg border border-violet-400/25 bg-violet-500/5 p-3">
          {!isPro && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-300">
              This is the Pro Editor. <Link className="underline" href="/pricing">Upgrade — ₹299/mo</Link> to
              unlock all styles, 1080p, SFX and no watermark. (Free preview: 3 styles.)
            </div>
          )}

          {/* CAPTION STYLES */}
          <div>
            <p className="mb-1.5 text-xs font-semibold text-muted-foreground">Caption style (20):</p>
            <div className="grid grid-cols-4 gap-1.5">
              {allStyles.map((s) => {
                const locked = !isPro && !freeStyles.has(s);
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => (locked ? null : setStyle(s))}
                    className={
                      "rounded px-1.5 py-1 text-[10px] font-semibold transition-colors " +
                      (style === s
                        ? "bg-violet-500 text-white"
                        : locked
                        ? "bg-white/5 text-muted-foreground line-through"
                        : "bg-white/10 hover:bg-white/20")
                    }
                  >
                    {locked ? "🔒 " : ""}
                    {s.replace("_", " ")}
                  </button>
                );
              })}
            </div>
          </div>

          {/* TRIM */}
          <div>
            <p className="mb-1 text-xs font-semibold text-muted-foreground">
              Trim: {trimStart}s → {trimEnd}s
            </p>
            <div className="flex gap-2">
              <input
                type="range"
                min={0}
                max={Math.max(2, trimEnd - 2)}
                value={trimStart}
                onChange={(e) => setTrimStart(Number(e.target.value))}
                className="w-1/2 accent-violet-500"
              />
              <input
                type="range"
                min={Math.min((clip.end_seconds ?? 30) as number, trimStart + 2)}
                max={(clip.end_seconds ?? 30) as number}
                value={trimEnd}
                onChange={(e) => setTrimEnd(Number(e.target.value))}
                className="w-1/2 accent-violet-500"
              />
            </div>
          </div>

          {/* POLISH */}
          <div className="flex flex-wrap gap-2 text-xs">
            {(
              [
                ["Auto SFX 🔊", sfx, setSfx],
                ["Upscale ✨", enhance, setEnhance],
              ] as const
            ).map(([label, value, setter]) => (
              <button
                key={label}
                type="button"
                onClick={() => (isPro ? setter(!value) : null)}
                className={
                  "rounded-full border px-3 py-1 " +
                  (value ? "border-violet-400 bg-violet-500/25 text-white" : "border-white/15 text-muted-foreground")
                }
              >
                {label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => (isPro ? setReframe(reframe === "face" ? "center" : "face") : null)}
              className="rounded-full border border-white/15 px-3 py-1 text-muted-foreground"
            >
              Reframe: {reframe === "face" ? "🎯 face" : "⬜ center"}
            </button>
          </div>

          <Button size="sm" className="w-full" onClick={apply} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scissors className="h-4 w-4" />}
            {isPro ? "Re-render in full quality" : "Preview (upgrade to apply)"}
          </Button>
          {msg && <p className="text-xs text-emerald-400">{msg}</p>}
          {error && <p className="text-xs text-red-400">{error}</p>}
          <p className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Sparkles className="h-3 w-3" /> Re-render uses your ORIGINAL source copy — no quality loss.
          </p>
        </div>
      )}
    </div>
  );
}
