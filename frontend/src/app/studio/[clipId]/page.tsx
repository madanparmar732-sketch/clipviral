"use client";

/**
 * ClipViral STUDIO — CapCut-style live editor, 100% in the browser.
 * - Captions LIVE on the video (change style/position/size = instant!)
 * - Word-tap cuts + filler auto-cut + trim (live preview skips cut parts)
 * - Export RIGHT HERE in the browser (WebM) — zero cloud needed
 * - Or push to the server engine for a full-quality MP4 re-render
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Download, Loader2, Scissors, Sparkles, Type, Wand2, Crop, Play, Pause, Video } from "lucide-react";

import { getClip, proEditClip } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_API_URL || "https://clipviral-r5m1.onrender.com";

const ASPECTS: Record<string, { w: number; h: number; label: string }> = {
  "9:16": { w: 720, h: 1280, label: "9:16 Shorts/Reels" },
  "1:1": { w: 720, h: 720, label: "1:1 Instagram" },
  "16:9": { w: 1280, h: 720, label: "16:9 YouTube" },
  "4:5": { w: 720, h: 900, label: "4:5 Feed" },
};

type CapStyle = {
  name: string;
  color: string;
  stroke: string;
  box?: string;
  hl: string;
  font: string;
  weight: number;
};

const STYLES: CapStyle[] = [
  { name: "beast", color: "#ffffff", stroke: "#000000", box: "#ff3b30", hl: "#ffcc00", font: "Arial Black, sans-serif", weight: 900 },
  { name: "mrbeast", color: "#ffffff", stroke: "#111111", box: "#3b82f6", hl: "#ffcc00", font: "Arial Black, sans-serif", weight: 900 },
  { name: "tiktok", color: "#ffffff", stroke: "#000000", hl: "#ff0050", font: "Arial Black, sans-serif", weight: 900 },
  { name: "neon", color: "#ccff00", stroke: "#0a3d2e", hl: "#ffffff", font: "Arial Black, sans-serif", weight: 900 },
  { name: "minimal", color: "#ffffff", stroke: "#000000", hl: "#cccccc", font: "Helvetica, Arial, sans-serif", weight: 700 },
  { name: "bold_box", color: "#000000", stroke: "#000000", box: "#ffffff", hl: "#ffcc00", font: "Arial Black, sans-serif", weight: 900 },
  { name: "karaoke_bar", color: "#ffffff", stroke: "#000000", box: "#111111", hl: "#00ff88", font: "Arial Black, sans-serif", weight: 900 },
  { name: "pop_shadow", color: "#ffffff", stroke: "#222222", hl: "#ff66cc", font: "Trebuchet MS, sans-serif", weight: 800 },
  { name: "sunset", color: "#ffeaa7", stroke: "#6b2d5c", hl: "#ff7675", font: "Arial Black, sans-serif", weight: 900 },
  { name: "mint", color: "#00d2a0", stroke: "#023047", hl: "#ffffff", font: "Arial Black, sans-serif", weight: 900 },
  { name: "fire", color: "#ff9f1a", stroke: "#7c2d12", hl: "#ff3b30", font: "Impact, Arial Black, sans-serif", weight: 900 },
  { name: "royal", color: "#c9a227", stroke: "#1b1b3a", hl: "#ffffff", font: "Georgia, serif", weight: 800 },
  { name: "bubble", color: "#ff6b9d", stroke: "#ffffff", box: "#ffe4f0", hl: "#ff2e63", font: "Comic Sans MS, Arial, sans-serif", weight: 800 },
  { name: "stripe", color: "#ffffff", stroke: "#111111", box: "#e63946", hl: "#f1faee", font: "Arial Black, sans-serif", weight: 900 },
  { name: "impact", color: "#ffffff", stroke: "#000000", hl: "#ffcc00", font: "Impact, Arial Black, sans-serif", weight: 900 },
  { name: "lower_third", color: "#ffffff", stroke: "#000000", box: "#0f172a", hl: "#38bdf8", font: "Arial, sans-serif", weight: 800 },
  { name: "neon_pink", color: "#ff2e97", stroke: "#3d0024", hl: "#ffffff", font: "Arial Black, sans-serif", weight: 900 },
  { name: "ice", color: "#b8e0ff", stroke: "#0b2545", hl: "#ffffff", font: "Arial Black, sans-serif", weight: 900 },
  { name: "gold", color: "#ffd700", stroke: "#3b2f00", hl: "#ffffff", font: "Georgia, serif", weight: 800 },
  { name: "mono", color: "#e5e5e5", stroke: "#000000", hl: "#888888", font: "Courier New, monospace", weight: 800 },
];

const FILLERS = new Set([
  "um", "uh", "uhm", "hmm", "erm", "ah", "like", "you know", "actually", "basically",
  "i mean", "so yeah", "matlab", "acha", "haina", "right", "okay", "ok",
]);

type Word = { start: number; end: number; word: string };

function fmtTime(s: number) {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

/** group words into caption lines of ~3-4 words */
function toLines(words: Word[]): { words: Word[]; start: number; end: number }[] {
  const lines: { words: Word[]; start: number; end: number }[] = [];
  let cur: Word[] = [];
  for (const w of words) {
    cur.push(w);
    const text = cur.map((x) => x.word).join(" ");
    if (cur.length >= 4 || text.length >= 22 || /[.!?]$/.test(w.word)) {
      lines.push({ words: cur, start: cur[0].start, end: cur[cur.length - 1].end });
      cur = [];
    }
  }
  if (cur.length) lines.push({ words: cur, start: cur[0].start, end: cur[cur.length - 1].end });
  return lines;
}

export default function StudioPage() {
  const params = useParams<{ clipId: string }>();
  const [token, setToken] = useState("");
  const clipId = params.clipId;

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token ?? "");
    });
  }, []);

  const videoRef = useRef<HTMLVideoElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const [clip, setClip] = useState<any>(null);
  const [words, setWords] = useState<Word[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  // live controls
  const [styleName, setStyleName] = useState("beast");
  const [pos, setPos] = useState<"bottom" | "center" | "top">("bottom");
  const [sizeScale, setSizeScale] = useState(1);
  const [caps, setCaps] = useState(true);
  const [aspect, setAspect] = useState("9:16");
  const [layout, setLayout] = useState<"full" | "pad">("full");
  const [reframe, setReframe] = useState<"center" | "left" | "right">("center");
  const [removed, setRemoved] = useState<[number, number][]>([]);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [activeLine, setActiveLine] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [exportMsg, setExportMsg] = useState("");
  const [cloudMsg, setCloudMsg] = useState("");

  const style = useMemo(() => STYLES.find((s) => s.name === styleName) ?? STYLES[0], [styleName]);
  const lines = useMemo(() => toLines(words), [words]);
  const removedRef = useRef(removed);
  const trimRef = useRef([0, 0]);
  removedRef.current = removed;
  trimRef.current = [trimStart, trimEnd || 99999];

  // ---------- load ----------
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if (!token) return;
        const c = await getClip(token, clipId);
        if (!alive) return;
        setClip(c);
        try {
          const wordsUrl = String((c as any).video_url || "").replace(/\.mp4(\?.*)?$/, ".words.json");
          const res = await fetch(wordsUrl);
          if (res.ok) {
            const data = await res.json();
            const ws: Word[] = (data.words || data.segments || []).map((w: any) => ({
              start: Number(w.start), end: Number(w.end), word: String(w.word ?? ""),
            }));
            if (alive) setWords(ws.filter((w) => w.word && isFinite(w.start)));
          }
        } catch {}
        setTrimEnd(0);
      } catch (e: any) {
        if (alive) setErr(e.message || "Failed to load clip");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [clipId, token]);

  const videoSrc = clip ? `${API}/api/proxy?url=${encodeURIComponent((clip as any).video_url || "")}` : "";

  const onLoadedMeta = () => {
    const v = videoRef.current;
    if (!v) return;
    setTrimStart(0);
    setTrimEnd(v.duration || 0);
  };

  // ---------- live playback engine (skip cuts + trim loop + caption sync) ----------
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const v = videoRef.current;
      if (v && !v.paused) {
        const t = v.currentTime;
        const [ts, te] = trimRef.current;
        const rem = removedRef.current;
        const hit = rem.find((w) => t >= w[0] && t < w[1] - 0.02);
        if (hit) {
          v.currentTime = Math.min(hit[1], te);
        } else if (t > te) {
          v.currentTime = ts;
        } else if (t < ts - 0.05) {
          v.currentTime = ts;
        }
        const li = lines.findIndex((l) => t >= l.start - 0.08 && t <= l.end + 0.35);
        setActiveLine((prev) => (li !== prev ? li : prev));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [lines]);

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) {
      if (v.currentTime < trimStart - 0.05 || v.currentTime > (trimEnd || 1e9)) v.currentTime = trimStart;
      v.play();
      setPlaying(true);
    } else {
      v.pause();
      setPlaying(false);
    }
  };

  // ---------- word cut toggles ----------
  const toggleWordCut = (idx: number) => {
    const w = words[idx];
    if (!w) return;
    const pad = 0.06;
    const win: [number, number] = [Math.max(0, w.start - pad), w.end + pad];
    setRemoved((prev) => {
      const exists = prev.find((r) => Math.abs(r[0] - win[0]) < 0.12 && Math.abs(r[1] - win[1]) < 0.12);
      if (exists) return prev.filter((r) => r !== exists);
      return [...prev, win].sort((a, b) => a[0] - b[0]);
    });
  };

  const isWordCut = (idx: number) => {
    const w = words[idx];
    return removed.some((r) => w.start >= r[0] - 0.12 && w.end <= r[1] + 0.12);
  };

  const autoCutFillers = () => {
    const wins: [number, number][] = [];
    for (const w of words) {
      const clean = w.word.toLowerCase().replace(/[^a-z ]/g, "").trim();
      if (FILLERS.has(clean)) wins.push([Math.max(0, w.start - 0.06), w.end + 0.06]);
    }
    if (!wins.length) {
      setCloudMsg("No filler words found in this clip ✅");
      return;
    }
    setRemoved((prev) => [...prev, ...wins].sort((a, b) => a[0] - b[0]));
    setCloudMsg(`Removed ${wins.length} filler word${wins.length > 1 ? "s" : ""} ✂️`);
  };

  // ---------- EXPORT IN BROWSER (no cloud!) ----------
  const exportInBrowser = useCallback(async () => {
    const v = videoRef.current;
    if (!v || !clip) return;
    setExporting(true);
    setExportMsg("Preparing…");
    try {
      const { w: cw, h: ch } = ASPECTS[aspect];
      const canvas = document.createElement("canvas");
      canvas.width = cw;
      canvas.height = ch;
      const ctx = canvas.getContext("2d")!;

      // audio: route element audio to recorder only (silent playback while exporting)
      if (!audioCtxRef.current) {
        const AC: typeof AudioContext = (window as any).AudioContext || (window as any).webkitAudioContext;
        audioCtxRef.current = new AC();
        const srcNode = audioCtxRef.current!.createMediaElementSource(v);
        const dest = audioCtxRef.current!.createMediaStreamDestination();
        srcNode.connect(dest);
        (audioCtxRef.current as any).__dest = dest;
      }
      await audioCtxRef.current!.resume();
      const dest: MediaStreamAudioDestinationNode = (audioCtxRef.current as any).__dest;

      const stream = canvas.captureStream(30);
      const at = dest.stream.getAudioTracks()[0];
      if (at) stream.addTrack(at);

      const mimes = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm", "video/mp4"];
      const mime = mimes.find((m) => (window as any).MediaRecorder && MediaRecorder.isTypeSupported(m)) || "";
      const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 6_000_000 });
      const chunks: BlobPart[] = [];
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);

      const done = new Promise<Blob>((resolve) => {
        rec.onstop = () => resolve(new Blob(chunks, { type: mime || "video/webm" }));
      });

      v.pause();
      v.currentTime = trimStart;
      await new Promise((r) => setTimeout(r, 350));
      rec.start(200);
      await v.play();
      setExportMsg("Rendering in your browser… keep this tab open ⚡");

      await new Promise<void>((resolve) => {
        const draw = () => {
          const t = v.currentTime;
          const [ts, te] = trimRef.current;
          const rem = removedRef.current;
          const hit = rem.find((w) => t >= w[0] && t < w[1] - 0.02);
          if (hit) v.currentTime = Math.min(hit[1], te);

          // draw video frame (cover / pad + reframe focus)
          const vw = v.videoWidth || 1280, vh = v.videoHeight || 720;
          if (layout === "pad") {
            ctx.filter = "blur(18px)";
            const sBg = Math.max(cw / vw, ch / vh);
            ctx.drawImage(v, (cw - vw * sBg) / 2, (ch - vh * sBg) / 2, vw * sBg, vh * sBg);
            ctx.filter = "none";
            const sFg = Math.min(cw / vw, ch / vh);
            ctx.drawImage(v, (cw - vw * sFg) / 2, (ch - vh * sFg) / 2, vw * sFg, vh * sFg);
          } else {
            const s = Math.max(cw / vw, ch / vh);
            const dw = vw * s, dh = vh * s;
            const focus = reframe === "left" ? 0.25 : reframe === "right" ? 0.75 : 0.5;
            const dx = (cw - dw) * focus;
            const dy = (ch - dh) / 2;
            ctx.drawImage(v, dx, dy, dw, dh);
          }

          // draw caption line
          const li = lines.findIndex((l) => t >= l.start - 0.08 && t <= l.end + 0.35);
          if (li >= 0) {
            const line = lines[li];
            const text = line.words.map((w) => w.word).join(" ");
            const finalText = caps ? text.toUpperCase() : text;
            const fontSize = Math.round(ch * 0.045 * sizeScale);
            ctx.font = `${style.weight} ${fontSize}px ${style.font}`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            const ty = pos === "top" ? ch * 0.14 : pos === "center" ? ch * 0.5 : ch * 0.84;

            if (style.box) {
              const m = ctx.measureText(finalText);
              const padX = fontSize * 0.5, padY = fontSize * 0.28;
              ctx.fillStyle = style.box;
              ctx.beginPath();
              (ctx as any).roundRect ? (ctx as any).roundRect(cw / 2 - m.width / 2 - padX, ty - fontSize * 0.62 - padY, m.width + padX * 2, fontSize * 1.24 + padY * 2, 12) : ctx.rect(cw / 2 - m.width / 2 - padX, ty - fontSize * 0.62 - padY, m.width + padX * 2, fontSize * 1.24 + padY * 2);
              ctx.fill();
            }
            ctx.lineWidth = Math.max(3, fontSize * 0.12);
            ctx.strokeStyle = style.stroke;
            ctx.strokeText(finalText, cw / 2, ty);
            ctx.fillStyle = style.color;
            ctx.fillText(finalText, cw / 2, ty);
          }

          if (t >= te || v.ended) {
            resolve();
            return;
          }
          requestAnimationFrame(draw);
        };
        requestAnimationFrame(draw);
      });

      v.pause();
      rec.stop();
      const blob = await done;
      const ext = (mime || "").includes("mp4") ? "mp4" : "webm";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `clipviral-studio.${ext}`;
      a.click();
      setExportMsg(`✅ Done! Downloaded .${ext} — 100% in your browser, no cloud used!`);
    } catch (e: any) {
      setExportMsg(`⚠️ ${e.message || "Export failed — try the Server Render button."}`);
    } finally {
      setExporting(false);
    }
  }, [clip, aspect, layout, reframe, lines, caps, sizeScale, style, pos, trimStart]);

  // ---------- CLOUD re-render (full quality MP4) ----------
  const serverRender = async () => {
    if (!token || !clip) return;
    setCloudMsg("Sending to the render engine…");
    try {
      const ws = words.filter((w) => !isWordCut(words.indexOf(w)));
      await proEditClip(token, clip.id, {
        style: styleName,
        trim_start: trimStart,
        trim_end: trimEnd,
        aspect,
        layout,
        caption_pos: pos,
        size_scale: sizeScale,
        caps,
        reframe,
        removed: removed.length ? removed : undefined,
        words_override: ws.map((w) => ({ start: w.start, end: w.end, word: w.word })),
      } as any);
      setCloudMsg("☁️ Queued! The cloud engine re-renders in full MP4 quality — check Dashboard in a minute.");
    } catch (e: any) {
      setCloudMsg(`⚠️ ${e.message}`);
    }
  };

  // ---------- render ----------
  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#07070c] text-white">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading studio…
      </main>
    );
  }
  if (err || !clip) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#07070c] text-white">
        <p className="text-white/60">{err || "Clip not found"}</p>
        <Link href="/dashboard"><Button variant="outline">Back to Dashboard</Button></Link>
      </main>
    );
  }

  const curLine = lines[activeLine];
  const captionText = curLine ? (caps ? curLine.words.map((w) => w.word).join(" ").toUpperCase() : curLine.words.map((w) => w.word).join(" ")) : "";
  const stageRatio = ASPECTS[aspect].w / ASPECTS[aspect].h;

  return (
    <main className="min-h-screen bg-[#07070c] text-white">
      <div className="mx-auto max-w-7xl px-4 py-5">
        {/* top bar */}
        <div className="mb-4 flex items-center gap-3">
          <Link href="/dashboard"><Button variant="ghost" size="sm"><ArrowLeft className="h-4 w-4" /> Dashboard</Button></Link>
          <h1 className="text-lg font-black">
            <span className="bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">Studio</span>
            <span className="ml-2 text-sm font-normal text-white/50">live captions • browser editing</span>
          </h1>
          <div className="ml-auto flex gap-2">
            <Button variant="outline" size="sm" onClick={serverRender}><Video className="h-4 w-4" /> ☁️ Server render (MP4)</Button>
            <Button size="sm" onClick={exportInBrowser} disabled={exporting}>
              {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Export here (no cloud)
            </Button>
          </div>
        </div>
        {(exportMsg || cloudMsg) && (
          <div className="mb-3 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80">
            {exportMsg || cloudMsg}
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_400px]">
          {/* ============ LEFT: live stage ============ */}
          <div className="flex flex-col items-center gap-3">
            <div
              ref={stageRef}
              className="relative overflow-hidden rounded-2xl border border-white/10 bg-black shadow-2xl"
              style={{ width: "100%", maxWidth: stageRatio >= 1 ? 720 : 405, aspectRatio: `${ASPECTS[aspect].w} / ${ASPECTS[aspect].h}` }}
              onClick={togglePlay}
            >
              <video
                ref={videoRef}
                src={videoSrc}
                crossOrigin="anonymous"
                playsInline
                onLoadedMetadata={onLoadedMeta}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                className="absolute inset-0 h-full w-full object-cover"
                style={{
                  objectPosition: reframe === "left" ? "25% center" : reframe === "right" ? "75% center" : "center",
                  filter: layout === "pad" ? "none" : undefined,
                }}
              />

              {/* LIVE caption overlay */}
              {captionText && (
                <div
                  className="pointer-events-none absolute left-1/2 -translate-x-1/2 text-center"
                  style={{
                    top: pos === "top" ? "10%" : pos === "center" ? "42%" : "auto",
                    bottom: pos === "bottom" ? "10%" : "auto",
                    width: "88%",
                  }}
                >
                  <span
                    className="inline-block px-3 py-1 leading-tight"
                    style={{
                      fontFamily: style.font,
                      fontWeight: style.weight,
                      fontSize: `clamp(16px, ${3.2 * sizeScale}vw, ${34 * sizeScale}px)`,
                      color: style.color,
                      WebkitTextStroke: `1.5px ${style.stroke}`,
                      background: style.box ?? "transparent",
                      borderRadius: style.box ? 10 : 0,
                      textShadow: style.box ? "none" : `2px 2px 0 ${style.stroke}`,
                    }}
                  >
                    {captionText}
                  </span>
                </div>
              )}

              {/* play button */}
              {!playing && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/20">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                    <Play className="h-8 w-8 text-white" />
                  </div>
                </div>
              )}

              {/* trim bar */}
              <div className="absolute inset-x-0 top-0 flex items-center gap-2 bg-black/50 px-3 py-1 text-[11px] text-white/80">
                <Scissors className="h-3 w-3" />
                <span>{fmtTime(trimStart)} – {fmtTime(trimEnd)}</span>
                <span className="ml-auto text-white/50">{words.filter((_, i) => isWordCut(i)).length} words cut</span>
              </div>
            </div>

            {/* playback + trim controls */}
            <div className="flex w-full max-w-[720px] items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
              <Button variant="ghost" size="sm" onClick={togglePlay}>
                {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
              </Button>
              <div className="flex flex-1 flex-col gap-1 text-xs text-white/60">
                <label className="flex items-center gap-2">Start
                  <input type="range" min={0} max={Math.max(1, trimEnd)} step={0.1} value={trimStart}
                    onChange={(e) => setTrimStart(Math.min(Number(e.target.value), trimEnd - 1))}
                    className="flex-1 accent-violet-500" />
                  <span className="w-10 text-right">{fmtTime(trimStart)}</span>
                </label>
                <label className="flex items-center gap-2">End
                  <input type="range" min={trimStart + 1} max={videoRef.current?.duration || 60} step={0.1} value={trimEnd}
                    onChange={(e) => setTrimEnd(Number(e.target.value))}
                    className="flex-1 accent-violet-500" />
                  <span className="w-10 text-right">{fmtTime(trimEnd)}</span>
                </label>
              </div>
            </div>

            {/* transcript word chips */}
            <div className="w-full max-w-[720px] rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <div className="mb-3 flex items-center gap-2">
                <Type className="h-4 w-4 text-violet-400" />
                <h3 className="text-sm font-bold">Transcript — tap a word to cut it</h3>
                <Button variant="outline" size="sm" className="ml-auto" onClick={autoCutFillers}>
                  <Sparkles className="h-3 w-3" /> Auto-cut fillers
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setRemoved([])}>Reset cuts</Button>
              </div>
              <div className="max-h-44 overflow-y-auto leading-8">
                {words.length === 0 && <p className="text-white/40">No transcript found for this clip.</p>}
                {words.map((w, i) => (
                  <button
                    key={i}
                    onClick={() => toggleWordCut(i)}
                    className={`mr-1 rounded px-1 text-[15px] transition ${
                      isWordCut(i)
                        ? "bg-red-500/25 text-red-300 line-through opacity-60"
                        : "bg-white/5 text-white/90 hover:bg-violet-500/30"
                    }`}
                  >
                    {w.word}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* ============ RIGHT: controls ============ */}
          <div className="flex flex-col gap-4">
            {/* styles */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <h3 className="mb-3 text-sm font-bold">🎨 Caption style — tap = INSTANT change</h3>
              <div className="grid grid-cols-4 gap-2">
                {STYLES.map((s) => (
                  <button
                    key={s.name}
                    onClick={() => setStyleName(s.name)}
                    className={`rounded-lg border px-2 py-2 text-[10px] font-bold uppercase tracking-wide transition ${
                      s.name === styleName ? "border-violet-500 bg-violet-500/20 text-white" : "border-white/10 bg-white/5 text-white/60 hover:bg-white/10"
                    }`}
                    style={{ color: s.name === styleName ? s.color : undefined, WebkitTextStroke: s.name === styleName ? `0.6px ${s.stroke}` : undefined }}
                  >
                    {s.name.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            {/* text controls */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <h3 className="mb-3 text-sm font-bold">🔤 Text</h3>
              <div className="space-y-3 text-sm">
                <div>
                  <p className="mb-1 text-white/50">Position</p>
                  <div className="flex gap-2">
                    {(["top", "center", "bottom"] as const).map((p) => (
                      <Button key={p} variant={pos === p ? "default" : "outline"} size="sm" className="flex-1 capitalize" onClick={() => setPos(p)}>{p}</Button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1 text-white/50">Size — {Math.round(sizeScale * 100)}%</p>
                  <input type="range" min={0.6} max={1.5} step={0.05} value={sizeScale}
                    onChange={(e) => setSizeScale(Number(e.target.value))} className="w-full accent-violet-500" />
                </div>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={caps} onChange={(e) => setCaps(e.target.checked)} className="accent-violet-500" />
                  ALL CAPS
                </label>
              </div>
            </div>

            {/* frame controls */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <h3 className="mb-3 text-sm font-bold"><Crop className="mr-1 inline h-4 w-4" /> Frame</h3>
              <div className="space-y-3 text-sm">
                <div>
                  <p className="mb-1 text-white/50">Aspect ratio</p>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.keys(ASPECTS).map((a) => (
                      <Button key={a} variant={aspect === a ? "default" : "outline"} size="sm" onClick={() => setAspect(a)}>
                        {ASPECTS[a].label}
                      </Button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1 text-white/50">Layout</p>
                  <div className="flex gap-2">
                    <Button variant={layout === "full" ? "default" : "outline"} size="sm" className="flex-1" onClick={() => setLayout("full")}>Full frame</Button>
                    <Button variant={layout === "pad" ? "default" : "outline"} size="sm" className="flex-1" onClick={() => setLayout("pad")}>Blur pad</Button>
                  </div>
                </div>
                <div>
                  <p className="mb-1 text-white/50">Reframe</p>
                  <div className="flex gap-2">
                    {(["left", "center", "right"] as const).map((r) => (
                      <Button key={r} variant={reframe === r ? "default" : "outline"} size="sm" className="flex-1 capitalize" onClick={() => setReframe(r)}>{r}</Button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* export panel */}
            <div className="rounded-2xl border border-violet-500/30 bg-violet-500/10 p-4">
              <h3 className="mb-2 text-sm font-bold"><Wand2 className="mr-1 inline h-4 w-4" /> Export</h3>
              <p className="mb-3 text-xs text-white/70">
                <b>Export here</b> = fastest, 100% in your browser (WebM), zero cloud. <b>Server render</b> = full MP4
                quality with exact styles (takes ~1 min).
              </p>
              <div className="flex flex-col gap-2">
                <Button onClick={exportInBrowser} disabled={exporting}>
                  {exporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                  ⚡ Export in browser (no cloud)
                </Button>
                <Button variant="outline" onClick={serverRender}>☁️ Server render (MP4 quality)</Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
