"use client";

import { useState } from "react";
import { Download, Loader2, Sparkles, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { downloadClip, type Clip, type Job , cancelJob} from "@/lib/api";
import Link from "next/link";
import { Wand2 } from "lucide-react";
import type { Account } from "@/lib/api";
import { formatDate, formatDuration } from "@/lib/utils";

function statusBadge(status: string) {
  switch (status) {
    case "completed":
      return <Badge variant="success">Completed</Badge>;
    case "failed":
      return <Badge variant="destructive">Failed</Badge>;
    case "cancelled":
      return <Badge variant="outline">Cancelled</Badge>;
    case "processing":
      return <Badge variant="info">Processing</Badge>;
    default:
      return <Badge variant="warning">Queued</Badge>;
  }
}

function stageLabel(stage?: string | null) {
  if (!stage) return "";
  const map: Record<string, string> = {
    queued: "Waiting in line…",
    fetching_link: "Downloading video from your link…",
    link_fetched: "Video downloaded! Warming up the AI…",
    measuring_video: "Measuring your video…",
    transcribing_audio: "AI is listening & writing the transcript…",
    finding_viral_moments: "AI is hunting for viral moments…",
    making_recap: "Stitching the recap reel…",
    done: "All done!",
    failed: "Something went wrong",
  };
  if (map[stage]) return map[stage];
  if (stage.startsWith("rendering_clip")) {
    const n = stage.split("_").pop();
    return `Cutting & captioning clip #${n}…`;
  }
  return stage.replaceAll("_", " ");
}

export default function JobCard({ job, token, account }: { job: Job; token: string; account?: Account | null }) {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download(clip: Clip) {
    setError(null);
    setDownloadingId(clip.id);
    try {
      await downloadClip(clip, token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              {(job.source_filename ?? "Untitled video").split("|||")[0]}
              {statusBadge(job.status)}
              {(job.status === "queued" || job.status === "processing") && (
                <Button
                  size="sm"
                  variant="outline"
                  className="border-red-500/40 text-red-300 hover:bg-red-500/10"
                  disabled={cancelling}
                  onClick={async () => {
                    if (!window.confirm("Cancel this job? Processing will stop.")) return;
                    setCancelling(true);
                    try { await cancelJob(token, job.id); } catch {}
                    setCancelling(false);
                  }}
                >
                  <XCircle className="h-4 w-4" /> {cancelling ? "Cancelling…" : "Cancel"}
                </Button>
              )}
            </CardTitle>
            <CardDescription className="mt-1">
              {formatDate(job.created_at)}
              {job.duration_seconds ? ` · ${formatDuration(job.duration_seconds)} source` : ""}
            </CardDescription>
          </div>
          {job.status === "completed" && job.clips.length > 0 && (
            <div className="flex items-center gap-1.5 rounded-full bg-violet-500/15 px-3 py-1 text-xs font-medium text-violet-300">
              <Sparkles className="h-3.5 w-3.5" /> {job.clips.length} viral clips ready
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {(job.status === "processing" || job.status === "queued") && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin text-violet-400" />
              {stageLabel(job.stage)}
            </div>
            <Progress value={job.progress ?? 0} />
            <p className="text-right text-xs text-muted-foreground">{job.progress ?? 0}%</p>
          </div>
        )}

        {job.status === "failed" && (
          <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {job.error ?? "This job failed. Please try again."}
          </p>
        )}

        {error && (
          <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </p>
        )}

        {job.clips.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {job.clips.map((clip) => (
              <div
                key={clip.id}
                className="overflow-hidden rounded-xl border border-white/10 bg-white/5"
              >
                <div className="relative aspect-[9/16] max-h-80 w-full bg-black/40">
                  {clip.video_url ? (
                    <video
                      src={clip.video_url}
                      poster={clip.thumbnail_url ?? undefined}
                      controls
                      preload="metadata"
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                      No preview
                    </div>
                  )}
                  {clip.score ? (
                    <div className="absolute left-2 top-2 rounded-full bg-emerald-500/90 px-2 py-0.5 text-xs font-bold text-white">
                      🔥 {clip.score}
                    </div>
                  ) : null}
                </div>

                <div className="space-y-3 p-4">
                  <div>
                    <p className="line-clamp-2 text-sm font-semibold">{clip.title ?? "Untitled clip"}</p>
                    {clip.hook ? (
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">“{clip.hook}”</p>
                    ) : null}
                  </div>

                  {clip.hashtags && clip.hashtags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {clip.hashtags.map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-[10px]">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <Button
                    size="sm"
                    className="w-full"
                    onClick={() => download(clip)}
                    disabled={downloadingId === clip.id}
                  >
                    {downloadingId === clip.id ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" /> Preparing…
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4" /> Download 9:16 clip
                      </>
                    )}
                  </Button>
                  <Link href={`/editor/${clip.id}`}>
                    <Button size="sm" variant="outline" className="w-full">
                      <Wand2 className="h-4 w-4" /> Open Editor
                    </Button>
                  </Link>
                  <Link href={`/studio/${clip.id}`}>
                    <Button size="sm" variant="outline" className="w-full border-fuchsia-500/40">
                      <Sparkles className="h-4 w-4" /> 🎨 Studio (live)
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
