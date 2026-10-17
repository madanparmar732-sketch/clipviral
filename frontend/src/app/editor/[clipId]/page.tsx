"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Captions, Download, Film, Loader2, Scissors, Sparkles, Wand2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";
import {
  downloadClip, getAccount, getClip, proEditClip, updateClipMeta,
  type Account, type Clip,
} from "@/lib/api";

type Word = { start: number; end: number; word: string };

const TABS = [
  { id: "transcript", label: "📝 Transcript" },
  { id: "captions", label: "🎨 Captions" },
  { id: "frame", label: "🎬 Frame" },
  { id: "polish", label: "✨ Polish" },
  { id: "details", label: "🏷️ Details" },
] as const;

const FILLERS = ["um", "uh", "hmm", "mmm", "erm", "ah", "like", "you know", "i mean", "matlab", "yaar", "basically"];

export default function EditorPage() {
  const params = useParams<{ clipId: string }>();
  const router = useRouter();
  const clipId = params.clipId;

  const [token, setToken] = useState("");
  const [clip, setClip] = useState<Clip | null>(null);
  const [account, setAccount] = useState<Account | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("transcript");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // transcript
  const [words, setWords] = useState<Word[]>([]);
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const [duration, setDuration] = useState(30);

  // captions
  const [style, setStyle] = useState("beast");
  const [captionPos, setCaptionPos] = useState("bottom");
  const [sizeScale, setSizeScale] = useState(1.0);
  const [caps, setCaps] = useState(true);

  // frame
  const [aspect, setAspect] = useState("9:16");
  const [layout, setLayout] = useState("full");
  const [reframe, setReframe] = useState("face");
  const [enhance, setEnhance] = useState(false);

  // polish
  const [sfx, setSfx] = useState(false);
  const [volume, setVolume] = useState(1.0);
  const [brightness, setBrightness] = useState(0.0);
  const [contrast, setContrast] = useState(1.0);
  const [saturation, setSaturation] = useState(1.0);

  // trim
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(30);

  // details
  const [title, setTitle] = useState("");
  const [hook, setHook] = useState("");
  const [hashtags, setHashtags] = useState("");
  const [detailsSaved, setDetailsSaved] = useState(false);

  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const allStyles = useMemo(
    () => account?.all_styles ?? ["beast", "minimal", "bold_box", "tiktok", "neon"],
    [account]
  );

  const load = useCallback(async (t: string) => {
    try {
      const c = await getClip(t, clipId);
      setClip(c);
      setTitle(c.title ?? "");
      setHook(c.hook ?? "");
      setHashtags((c.hashtags ?? []).join(" "));
      const d = c.end_seconds ?? 30;
      setDuration(d);
      setTrimEnd(d);

      const base = (c.video_url ?? "").split("?")[0].replace(/\.mp4$/, ".words.json");
      try {
        const res = await fetch(`${base}?t=${Date.now()}`);
        if (res.ok) {
          const data = await res.json();
          setWords((data.words ?? []) as Word[]);
          if (data.clip_duration) {
            setDuration(Number(data.clip_duration));
            setTrimEnd(Number(data.clip_duration));
          }
        }
      } catch {
        /* transcript optional */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this clip.");
    } finally {
      setLoading(false);
    }
  }, [clipId]);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => {
      const t = data.session?.access_token ?? "";
      setToken(t);
      if (!t) {
        router.push(`/login?next=/editor/${clipId}`);
        return;
      }
      load(t);
      getAccount(t).then(setAccount).catch(() => {});
    });
  }, [clipId, load, router]);

  function toggleWord(i: number) {
    setRemoved((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
    setMsg(null);
  }

  function removeFillers() {
    const next = new Set(removed);
    words.forEach((w, i) => {
      const clean = w.word.toLowerCase().replace(/[^a-z ]/g, "").trim();
      if (FILLERS.includes(clean)) next.add(i);
    });
    setRemoved(next);
    setMsg("Filler words marked ✂️ — press Re-render to cut them out.");
  }

  function removedRanges(): [number, number][] {
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
    return ranges;
  }

  async function apply() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const res = await proEditClip(token, clipId, {
        style, trim_start: trimStart, trim_end: trimEnd,
        sfx, enhance, reframe,
        removed: removedRanges(),
        aspect, layout, caption_pos: captionPos, size_scale: sizeScale, caps,
        brightness, contrast, saturation, volume,
      });
      setMsg(res.message ?? "Re-rendering — press Refresh in about a minute.");
      setRemoved(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-render failed.");
    } finally {
      setBusy(false);
    }
  }

  async function saveDetails() {
    setBusy(true);
    setDetailsSaved(false);
    try {
      await updateClipMeta(token, clipId, {
        title, hook,
        hashtags: hashtags.split(/[\s,]+/).filter(Boolean),
      });
      setDetailsSaved(true);
      setMsg("Details saved ✅");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save details.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading editor…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      {/* HEADER */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="rounded-full border border-border p-2 hover:bg-black/[0.04]">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold">🎬 Clip Editor</h1>
            <p className="text-xs text-muted-foreground">{clip?.title ?? "Untitled clip"}</p>
          </div>
        </div>
        <div className="flex gap-2">
          {clip && (
            <Button size="sm" variant="outline" onClick={() => downloadClip(clip, token)}>
              <Download className="h-4 w-4" /> Download
            </Button>
          )}
          <Button size="sm" onClick={apply} disabled={busy} className="">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scissors className="h-4 w-4" />}
            Re-render
          </Button>
        </div>
      </div>

      {(msg || error) && (
        <div className={"mb-4 rounded-lg border px-4 py-2 text-sm " + (error ? "border-red-500/30 bg-red-50 text-red-700" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-700")}>
          {error ?? msg}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr,400px]">
        {/* PREVIEW */}
        <div className="space-y-4">
          <div className="overflow-hidden rounded-2xl border border-border bg-[#131211]">
            {clip?.video_url ? (
              <video
                key={clip.video_url}
                src={clip.video_url}
                poster={clip.thumbnail_url ?? undefined}
                controls
                className="mx-auto max-h-[62vh] w-full"
              />
            ) : (
              <div className="flex h-64 items-center justify-center text-muted-foreground">No preview</div>
            )}
          </div>

          {/* quick trim bar */}
          <div className="rounded-xl border border-border bg-[#f2efe9] p-4">
            <p className="mb-2 text-xs font-semibold text-muted-foreground">
              ⏱️ Trim: {trimStart.toFixed(1)}s → {trimEnd.toFixed(1)}s (of {Math.round(duration)}s)
            </p>
            <div className="flex gap-3">
              <input type="range" min={0} max={Math.max(2, trimEnd - 2)} step={0.1}
                value={trimStart} onChange={(e) => setTrimStart(Number(e.target.value))}
                className="w-1/2 accent-neutral-800" />
              <input type="range" min={Math.min(duration, trimStart + 2)} max={duration} step={0.1}
                value={trimEnd} onChange={(e) => setTrimEnd(Number(e.target.value))}
                className="w-1/2 accent-neutral-800" />
            </div>
            {removed.size > 0 && (
              <p className="mt-2 text-xs text-amber-600">✂️ {removed.size} word(s) marked for removal</p>
            )}
          </div>
        </div>

        {/* PANELS */}
        <div className="space-y-3">
          {/* TABS */}
          <div className="flex flex-wrap gap-1.5">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={
                  "rounded-full px-3 py-1.5 text-xs font-semibold transition-colors " +
                  (tab === t.id ? "bg-neutral-800 text-white" : "bg-black/[0.05] hover:bg-black/[0.09]")
                }
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="min-h-[320px] space-y-4 rounded-xl border border-border bg-[#f2efe9] p-4">
            {/* TRANSCRIPT */}
            {tab === "transcript" && (
              <>
                <p className="text-xs text-muted-foreground">
                  Tap words to strike them out ✂️ — they will be cut from the video.
                </p>
                <Button size="sm" variant="outline" className="w-full" onClick={removeFillers}>
                  <Wand2 className="h-4 w-4" /> Auto-remove filler words (um, uh…)
                </Button>
                <div className="flex max-h-[420px] flex-wrap gap-1 overflow-y-auto">
                  {words.length === 0 && <p className="text-xs text-muted-foreground">No transcript for this clip.</p>}
                  {words.map((w, i) => (
                    <button
                      key={i}
                      onClick={() => toggleWord(i)}
                      className={
                        "rounded px-1.5 py-0.5 text-xs transition-colors " +
                        (removed.has(i) ? "bg-red-100 text-red-700 line-through" : "bg-black/[0.05] hover:bg-black/[0.09]")
                      }
                    >
                      {w.word}
                    </button>
                  ))}
                </div>
              </>
            )}

            {/* CAPTIONS */}
            {tab === "captions" && (
              <>
                <div>
                  <p className="mb-1.5 text-xs font-semibold text-muted-foreground">🎨 Style (20)</p>
                  <div className="grid grid-cols-4 gap-1.5">
                    {allStyles.map((s) => (
                      <button key={s} onClick={() => setStyle(s)}
                        className={"rounded px-1.5 py-1 text-[10px] font-semibold " + (style === s ? "bg-neutral-800 text-white" : "bg-black/[0.05] hover:bg-black/[0.09]")}>
                        {s.replace("_", " ")}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-semibold text-muted-foreground">📍 Position</p>
                  <div className="flex gap-1.5">
                    {["top", "center", "bottom"].map((p) => (
                      <button key={p} onClick={() => setCaptionPos(p)}
                        className={"flex-1 rounded px-2 py-1.5 text-xs " + (captionPos === p ? "bg-neutral-800 text-white" : "bg-black/[0.04]")}>
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold text-muted-foreground">🔠 Size: {Math.round(sizeScale * 100)}%</p>
                  <input type="range" min={0.6} max={1.5} step={0.05} value={sizeScale}
                    onChange={(e) => setSizeScale(Number(e.target.value))} className="w-full accent-neutral-800" />
                </div>
                <button onClick={() => setCaps(!caps)}
                  className={"w-full rounded-full border px-3 py-1.5 text-xs " + (caps ? "border-accent/40 bg-accent/10" : "border-border text-muted-foreground")}>
                  ALL CAPS {caps ? "ON" : "OFF"}
                </button>
              </>
            )}

            {/* FRAME */}
            {tab === "frame" && (
              <>
                <div>
                  <p className="mb-1.5 text-xs font-semibold text-muted-foreground">📐 Aspect ratio</p>
                  <div className="grid grid-cols-4 gap-1.5">
                    {["9:16", "1:1", "16:9", "4:5"].map((a) => (
                      <button key={a} onClick={() => setAspect(a)}
                        className={"rounded px-2 py-2 text-xs font-semibold " + (aspect === a ? "bg-neutral-800 text-white" : "bg-black/[0.04]")}>
                        {a}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-semibold text-muted-foreground">🖼️ Layout</p>
                  <div className="flex gap-1.5">
                    {[["full", "Full frame"], ["pad", "Blur-pad"]].map(([v, l]) => (
                      <button key={v} onClick={() => setLayout(v)}
                        className={"flex-1 rounded px-2 py-1.5 text-xs " + (layout === v ? "bg-neutral-800 text-white" : "bg-black/[0.04]")}>
                        {l}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-semibold text-muted-foreground">🎯 Reframe</p>
                  <div className="flex gap-1.5">
                    {[["face", "Face track"], ["center", "Center"]].map(([v, l]) => (
                      <button key={v} onClick={() => setReframe(v)}
                        className={"flex-1 rounded px-2 py-1.5 text-xs " + (reframe === v ? "bg-neutral-800 text-white" : "bg-black/[0.04]")}>
                        {l}
                      </button>
                    ))}
                  </div>
                </div>
                <button onClick={() => setEnhance(!enhance)}
                  className={"w-full rounded-full border px-3 py-1.5 text-xs " + (enhance ? "border-accent/40 bg-accent/10" : "border-border text-muted-foreground")}>
                  ✨ Upscale / Smart Enhance {enhance ? "ON" : "OFF"}
                </button>
              </>
            )}

            {/* POLISH */}
            {tab === "polish" && (
              <>
                <button onClick={() => setSfx(!sfx)}
                  className={"w-full rounded-full border px-3 py-1.5 text-xs " + (sfx ? "border-accent/40 bg-accent/10" : "border-border text-muted-foreground")}>
                  🔊 Auto SFX {sfx ? "ON" : "OFF"}
                </button>
                {(
                  [
                    ["🔊 Volume", volume, setVolume, 0.1, 2, 0.1],
                    ["☀️ Brightness", brightness, setBrightness, -0.3, 0.3, 0.02],
                    ["🌗 Contrast", contrast, setContrast, 0.6, 1.6, 0.05],
                    ["🎨 Saturation", saturation, setSaturation, 0, 2, 0.05],
                  ] as const
                ).map(([label, val, setter, min, max, step]) => (
                  <div key={label}>
                    <p className="mb-1 text-xs font-semibold text-muted-foreground">
                      {label}: {Number(val).toFixed(2)}
                    </p>
                    <input type="range" min={min} max={max} step={step} value={val}
                      onChange={(e) => setter(Number(e.target.value))} className="w-full accent-neutral-800" />
                  </div>
                ))}
              </>
            )}

            {/* DETAILS */}
            {tab === "details" && (
              <>
                <div>
                  <p className="mb-1 text-xs font-semibold text-muted-foreground">Title</p>
                  <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={70} />
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold text-muted-foreground">Hook (opening line)</p>
                  <Input value={hook} onChange={(e) => setHook(e.target.value)} maxLength={120} />
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold text-muted-foreground">Hashtags (space-separated)</p>
                  <Input value={hashtags} onChange={(e) => setHashtags(e.target.value)} />
                </div>
                <Button size="sm" className="w-full" onClick={saveDetails} disabled={busy}>
                  {detailsSaved ? "Saved ✅" : "Save details"}
                </Button>
                <Link href="/pricing" className="block text-center text-xs text-muted-foreground underline">
                  Need no-watermark + speed? Go Pro →
                </Link>
              </>
            )}
          </div>

          <Button className="w-full" onClick={apply} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scissors className="h-4 w-4" />}
            Re-render in full quality
          </Button>
          <p className="flex items-center justify-center gap-1 text-[10px] text-muted-foreground">
            <Sparkles className="h-3 w-3" /> Renders from your ORIGINAL source — zero quality loss
          </p>
        </div>
      </div>
    </div>
  );
}
