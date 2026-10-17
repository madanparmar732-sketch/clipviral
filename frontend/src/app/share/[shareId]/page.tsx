"use client";

/**
 * Public share page — anyone with the link can watch the shared clips.
 * Data comes from the public Supabase share JSON (no login needed).
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type SharedClip = {
  id: string;
  title?: string;
  hook?: string;
  score?: number;
  video_url?: string;
  thumbnail_url?: string;
  hashtags?: string[];
};

const BUCKET_BASE =
  "https://dkavqwoolwomouajmcsy.supabase.co/storage/v1/object/public/clips";

export default function SharePage() {
  const params = useParams<{ shareId: string }>();
  const shareId = params?.shareId ?? "";
  const [data, setData] = useState<{ title?: string; clips: SharedClip[] } | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!shareId) return;
    fetch(`${BUCKET_BASE}/shares/${shareId}.json`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("404"))))
      .then((d) => setData(d))
      .catch(() => setError(true));
  }, [shareId]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-8 text-center">
        <p className="text-3xl font-bold">⚡ ClipViral</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Shared clips — <a href="/" className="text-violet-400 hover:underline">make your own free</a>
        </p>
      </div>

      {error && (
        <p className="rounded-xl border border-white/10 p-8 text-center text-sm text-muted-foreground">
          Ye share link kaam nahi karta (ya expire ho gaya).
        </p>
      )}
      {!data && !error && (
        <p className="p-8 text-center text-sm text-muted-foreground">Loading clips…</p>
      )}

      {data && (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {(data.clips || []).map((c) => (
            <div key={c.id} className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
              <div className="relative aspect-[9/16] max-h-96 bg-black/40">
                {c.video_url ? (
                  <video src={c.video_url} poster={c.thumbnail_url || undefined} controls
                    preload="metadata" className="h-full w-full object-contain" />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No video</div>
                )}
                {c.score ? (
                  <div className="absolute left-2 top-2 rounded-full bg-emerald-500/90 px-2 py-0.5 text-xs font-bold text-white">
                    🔥 {c.score}
                  </div>
                ) : null}
              </div>
              <div className="space-y-2 p-4">
                <p className="line-clamp-2 text-sm font-semibold">{c.title || "Untitled clip"}</p>
                {c.hook ? <p className="line-clamp-2 text-xs text-muted-foreground">“{c.hook}”</p> : null}
                {c.hashtags && c.hashtags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {c.hashtags.slice(0, 5).map((t) => (
                      <span key={t} className="rounded-full bg-white/10 px-2 py-0.5 text-[10px]">{t}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
