"use client";

import { useState } from "react";
import { Loader2, PenLine, Scissors } from "lucide-react";

import { Button } from "@/components/ui/button";
import { reEditClip, type Clip } from "@/lib/api";

type Word = { start: number; end: number; word: string };

/**
 * Transcript-based editor: tap words to strike them out, then re-cut the clip
 * without those parts (pauses already removed automatically).
 */
export default function ClipEditor({ clip, token }: { clip: Clip; token: string }) {
  const [open, setOpen] = useState(false);
  const [words, setWords] = useState<Word[] | null>(null);
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function toggleOpen() {
    if (!open && words === null) {
      setError(null);
      const base = (clip.video_url ?? "").split("?")[0].replace(/\.mp4$/, ".words.json");
      if (!base) {
        setError("No transcript for this clip.");
        return;
      }
      try {
        const res = await fetch(`${base}?t=${Date.now()}`);
        if (!res.ok) throw new Error("missing");
        const data = await res.json();
        setWords((data.words ?? []) as Word[]);
      } catch {
        setError("Transcript not found (this clip is from an older version).");
      }
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
    if (!words || removed.size === 0) return;
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      // Merge consecutive removed words into time ranges.
      const ranges: [number, number][] = [];
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

      const res = await reEditClip(clip.id, ranges, token);
      setMsg(res.message ?? "Re-cutting… press Refresh in about a minute.");
      setRemoved(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-cut failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <Button size="sm" variant="outline" className="w-full" onClick={toggleOpen}>
        <PenLine className="h-4 w-4" /> {open ? "Hide transcript editor" : "Edit by transcript"}
      </Button>

      {open && (
        <div className="space-y-2 rounded-lg border border-white/10 bg-white/5 p-3">
          {error && <p className="text-xs text-red-400">{error}</p>}
          {words && (
            <>
              <p className="text-[11px] text-muted-foreground">
                Tap any word to strike it out ✂️ — then press Re-cut.
              </p>
              <div className="flex flex-wrap gap-1">
                {words.map((w, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => toggleWord(i)}
                    className={
                      "rounded px-1.5 py-0.5 text-xs transition-colors " +
                      (removed.has(i)
                        ? "bg-red-500/20 text-red-300 line-through"
                        : "bg-white/10 text-white hover:bg-white/20")
                    }
                  >
                    {w.word}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <Button size="sm" className="flex-1" onClick={apply} disabled={busy || removed.size === 0}>
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scissors className="h-4 w-4" />}
                  Re-cut ({removed.size} word{removed.size === 1 ? "" : "s"} out)
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setRemoved(new Set());
                    setMsg(null);
                  }}
                  disabled={busy || removed.size === 0}
                >
                  Reset
                </Button>
              </div>
              {msg && <p className="text-xs text-emerald-400">{msg}</p>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
