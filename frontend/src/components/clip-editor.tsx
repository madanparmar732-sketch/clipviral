"use client";

import { useState } from "react";
import { Loader2, Scissors, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { proEditClip, recaptionClip, type Account, type Clip } from "@/lib/api";

type Word = { start: number; end: number; word: string };

/**
 * ONE merged clip editor (FREE for everyone):
 *   • transcript words — tap to strike out ✂️
 *   • 20 caption styles 🎨
 *   • trim start/end ⏱️
 *   • polish: Auto SFX / Upscale / Reframe ✨
 * Press "Re-render" -> full-quality rebuild from the original source.
 */
export default function ClipEditor({
  clip,
  token,
  account,
}: {
  clip: Clip;
  token: string;
  account?: Account | null;
}) {
  const [open, setOpen] = useState(false);
  const [words, setWords] = useState<Word[] | null>(null);
  const [duration, setDuration] = useState<number>(clip.end_seconds ?? 30);
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const [style, setStyle] = useState(account?.caption_style ?? "karaoke");
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState<number>(clip.end_seconds ?? 30);
  const [sfx, setSfx] = useState(account?.sfx ?? false);
  const [enhance, setEnhance] = useState(account?.enhance ?? false);
  const [reframe, setReframe] = useState<string>(account?.reframe ?? "face");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const allStyles = account?.all_styles ?? ["karaoke", "clean", "yellow_pop"];

  async function toggleOpen() {
    if (!open && words === null) {
      setError(null);
      const base = (clip.video_url ?? "").split("?")[0].replace(/\.mp4$/, ".words.json");
      if (base) {
        try {
          const res = await fetch(`${base}?t=${Date.now()}`);
          if (res.ok) {
            const data = await res.json();
            const ws = (data.words ?? []) as Word[];
            setWords(ws);
            const d = Number(data.clip_duration) || (clip.end_seconds ?? 30);
            setDuration(d);
            setTrimEnd(d);
          }
        } catch {
          /* transcript optional */
        }
      }
      if (words === null && !base) setError("No transcript for this clip yet.");
    }
    setOpen(!open);
  }

  function toggleWord(i: number) {
    setRemoved((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
    setMsg(null);
  }

  async function apply() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      // merge consecutive struck words into cut ranges
      const ranges: [number, number][] = [];
      if (words) {
        let start: number | null = null;
        let end = 0;
        words.forEach((w, i) => {
          if (removed.has(i)) {
            if (start === null) start = w.start;
            end = w.end;
          } else if (start !== null) {
            ranges.push([start, end]);
            start = null;
          }
        });
        if (start !== null) ranges.push([start, end]);
      }

      const res = await proEditClip(token, clip.id, {
        style,
        trim_start: trimStart,
        trim_end: trimEnd,
        sfx,
        enhance,
        reframe,
        removed: ranges,
      });
      setMsg(res.message ?? "Re-rendering — press Refresh in about a minute.");
      setRemoved(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-render failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <Button size="sm" variant="outline" className="w-full" onClick={toggleOpen}>
        <Wand2 className="h-4 w-4" /> {open ? "Hide editor" : "✨ Edit clip"}
      </Button>

      {open && (
        <div className="space-y-4 rounded-lg border border-violet-400/25 bg-violet-500/5 p-3">
          {/* TRANSCRIPT */}
          {words && words.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold text-muted-foreground">
                ✂️ Transcript — tap words to cut them out:
              </p>
              <div className="flex max-h-32 flex-wrap gap-1 overflow-y-auto">
                {words.map((w, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => toggleWord(i)}
                    className={
                      "rounded px-1.5 py-0.5 text-xs transition-colors " +
                      (removed.has(i)
                        ? "bg-red-100 text-red-700 line-through"
                        : "bg-black/[0.05] hover:bg-black/[0.09]")
                    }
                  >
                    {w.word}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* CAPTION STYLES */}
          <div>
            <p className="mb-1.5 text-xs font-semibold text-muted-foreground">🎨 Caption style (20 CapCut templates):</p>
            <div className="grid grid-cols-4 gap-1.5">
              {allStyles.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStyle(s)}
                  className={
                    "rounded px-1.5 py-1 text-[10px] font-semibold transition-colors " +
                    (style === s ? "bg-neutral-800 text-white" : "bg-black/[0.05] hover:bg-black/[0.09]")
                  }
                >
                  {(account?.style_names?.[s] ?? s.replace("_", " "))}
                </button>
              ))}
            </div>
            <div className="mt-1.5 flex gap-1.5">
              <button
                type="button"
                onClick={() => setStyle("none")}
                className={
                  "flex-1 rounded px-1.5 py-1 text-[10px] font-semibold transition-colors " +
                  (style === "none" ? "bg-red-600 text-white" : "bg-black/[0.05] text-red-600 hover:bg-black/[0.09]")
                }
              >
                🚫 No captions
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    await recaptionClip(token, clip.id, style);
                    setMsg("Re-rendering with the new caption style — refresh in ~2 minutes.");
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Re-render failed.");
                  } finally {
                    setBusy(false);
                  }
                }}
                className="flex-1 rounded bg-neutral-800 px-1.5 py-1 text-[10px] font-semibold text-white hover:bg-neutral-700 disabled:opacity-50"
              >
                ✨ Apply to this clip
              </button>
            </div>
          </div>

          {/* TRIM */}
          <div>
            <p className="mb-1 text-xs font-semibold text-muted-foreground">
              ⏱️ Trim: {trimStart}s → {trimEnd}s (of {Math.round(duration)}s)
            </p>
            <div className="flex gap-2">
              <input
                type="range"
                min={0}
                max={Math.max(2, trimEnd - 2)}
                value={trimStart}
                onChange={(e) => setTrimStart(Number(e.target.value))}
                className="w-1/2 accent-neutral-800"
              />
              <input
                type="range"
                min={Math.min(duration, trimStart + 2)}
                max={duration}
                value={trimEnd}
                onChange={(e) => setTrimEnd(Number(e.target.value))}
                className="w-1/2 accent-neutral-800"
              />
            </div>
          </div>

          {/* POLISH */}
          <div className="flex flex-wrap gap-2 text-xs">
            <button
              type="button"
              onClick={() => setSfx(!sfx)}
              className={
                "rounded-full border px-3 py-1 " +
                (sfx ? "border-accent/40 bg-accent/10 text-foreground" : "border-border text-muted-foreground")
              }
            >
              Auto SFX 🔊
            </button>
            <button
              type="button"
              onClick={() => setEnhance(!enhance)}
              className={
                "rounded-full border px-3 py-1 " +
                (enhance ? "border-accent/40 bg-accent/10 text-foreground" : "border-border text-muted-foreground")
              }
            >
              Upscale ✨
            </button>
            <button
              type="button"
              onClick={() => setReframe(reframe === "face" ? "center" : "face")}
              className="rounded-full border border-border px-3 py-1 text-muted-foreground"
            >
              Reframe: {reframe === "face" ? "🎯 face" : "⬜ center"}
            </button>
          </div>

          <Button size="sm" className="w-full" onClick={apply} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scissors className="h-4 w-4" />}
            Re-render in full quality
          </Button>
          {msg && <p className="text-xs text-emerald-600">{msg}</p>}
          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>
      )}
    </div>
  );
}
