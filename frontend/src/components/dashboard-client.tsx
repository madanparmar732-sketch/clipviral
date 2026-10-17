"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Inbox, RefreshCw, Sparkles } from "lucide-react";

import JobCard from "@/components/job-card";
import LinkImport from "@/components/link-import";
import UploadDropzone from "@/components/upload-dropzone";
import CreateOptions from "@/components/create-options";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/supabase/client";
import { getAccount, listJobs, keepApiWarm, type Account, type Job } from "@/lib/api";
import AdSlot from "@/components/ad-slot";

export default function DashboardClient({ userEmail }: { userEmail: string }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [health, setHealth] = useState<{ ok: boolean; checks: Record<string, string>; fixed_now: string[] } | null>(null);
  const [token, setToken] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [account, setAccount] = useState<Account | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async (activeToken?: string) => {
    const t = activeToken ?? token;
    if (!t) return;
    try {
      const data = await listJobs(t);
      const rank = (st: string) => (st === "processing" || st === "queued" ? 0 : 1);
      setJobs([...data].sort((a, b) => rank(a.status) - rank(b.status)));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load jobs.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  // 1) Get the login token once.
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL || "https://clipviral-r5m1.onrender.com";
    const loadHealth = () =>
      fetch(`${base}/api/health`)
        .then((r) => r.json())
        .then(setHealth)
        .catch(() => {});
    loadHealth();
    const t = setInterval(loadHealth, 120000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => {
      const t = data.session?.access_token ?? "";
      setToken(t);
      refresh(t);
      if (t) getAccount(t).then(setAccount).catch(() => {});
    });
  }, [refresh]);

  // Keep the tiny server awake while the dashboard is open (Render naps after 15 min idle).
  useEffect(() => {
    keepApiWarm();
    const warm = setInterval(keepApiWarm, 4 * 60 * 1000);
    return () => clearInterval(warm);
  }, []);

  // 2) While any job is still cooking, refresh every 5 seconds.
  useEffect(() => {
    const hasActive = jobs.some((j) => j.status === "queued" || j.status === "processing");
    if (hasActive && token) {
      timerRef.current = setInterval(() => refresh(), 5000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [jobs, token, refresh]);

  const allClips = jobs.flatMap((j) => j.clips ?? []);
  const scores = allClips.map((c) => c.score).filter((s): s is number => typeof s === "number" && s > 0);
  const avgScore = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
  const best = scores.length ? Math.max(...scores) : null;
  const activeJobs = jobs.filter((j) => j.status === "queued" || j.status === "processing").length;
  const totalSourceSecs = jobs.reduce((a, j) => a + (j.duration_seconds ?? 0), 0);

  return (
    <div className="space-y-8">
      {/* -------- header -------- */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow mb-2">Workspace</p>
          <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">
            {activeJobs > 0 ? (
              <>AI is cutting <span className="gradient-text">{activeJobs} video{activeJobs > 1 ? "s" : ""}</span>…</>
            ) : (
              <>Your <span className="gradient-text">clip studio</span></>
            )}
          </h1>
          <p className="mt-1.5 max-w-xl text-sm text-muted-foreground">
            {userEmail ? `Signed in as ${userEmail} · ` : ""}
            Drop a long video or paste a link — the AI returns virality-scored 9:16 clips with animated captions.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Link href="/scheduler" className="glass card-lift rounded-full px-3.5 py-1.5 font-medium text-white/80 hover:text-white">
            📅 Scheduler & Collections
          </Link>
          <Link href="/settings/brand" className="glass card-lift rounded-full px-3.5 py-1.5 font-medium text-white/80 hover:text-white">
            🎨 Brand kit
          </Link>
          {health && (
            <span
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 font-medium ${
                health.ok ? "bg-emerald-500/10 text-emerald-300/90" : "bg-red-500/10 text-red-300"
              }`}
              title={Object.entries(health.checks).map(([k, v]) => `${k}: ${v}`).join("\n")}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${health.ok ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
              {health.ok ? "All systems OK" : "Degraded — auto-fixing"}
            </span>
          )}
        </div>
      </div>

      {/* -------- stats -------- */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ["Videos processed", String(jobs.length), totalSourceSecs > 0 ? `${Math.round(totalSourceSecs / 60)} min of footage` : "your uploads"],
          ["Clips created", String(allClips.length), "ready to download"],
          ["Avg virality", avgScore !== null ? String(avgScore) : "—", best !== null ? `best ${best}/99` : "scores land here"],
          ["Plan", account?.plan === "pro" ? "PRO ⚡" : "FREE", account?.plan === "pro" ? "no ads · no watermark · fast lane" : "every feature unlocked"],
        ].map(([label, value, sub]) => (
          <div key={label} className="glass rounded-2xl px-5 py-4">
            <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground/70">{label}</p>
            <p className="mt-1 text-2xl font-black tabular-nums">{value}</p>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">{sub}</p>
          </div>
        ))}
      </div>

      {/* -------- create -------- */}
      <section className="glass rounded-3xl p-6 md:p-8">
        <div className="mb-6 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold">Make a new batch</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">Upload a file or import from any platform.</p>
          </div>
          <span className="hidden items-center gap-1.5 rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-200 sm:flex">
            <Sparkles className="h-3.5 w-3.5" /> No credits · unlimited
          </span>
        </div>
        <CreateOptions />
        <UploadDropzone compact />
        {account?.plan !== "pro" && <AdSlot compact slot="dashboard-top" />}
        <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
          <div className="h-px flex-1 bg-white/10" />
          <span>OR</span>
          <div className="h-px flex-1 bg-white/10" />
        </div>
        <LinkImport />
      </section>

      {/* -------- jobs -------- */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold">Your clips {jobs.length > 0 && <span className="ml-1 text-sm font-normal text-muted-foreground">({jobs.length})</span>}</h2>
          <Button variant="outline" size="sm" onClick={() => refresh()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>

        {error && (
          <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </p>
        )}

        {loading ? (
          <div className="flex items-center justify-center rounded-2xl border border-white/10 py-16 text-muted-foreground">
            <RefreshCw className="mr-2 h-5 w-5 animate-spin" /> Loading your jobs…
          </div>
        ) : jobs.length === 0 ? (
          <div className="dot-grid flex flex-col items-center justify-center gap-3 rounded-3xl border border-dashed border-white/15 px-6 py-20 text-center">
            <div className="mb-1 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/25 to-violet-500/15 ring-1 ring-inset ring-indigo-400/25">
              <Inbox className="h-7 w-7 text-indigo-300" />
            </div>
            <p className="font-semibold">Nothing here yet — and that's the fun part</p>
            <p className="max-w-md text-sm text-muted-foreground">
              Paste a link or drop a video above. A 1-hour podcast usually comes back as 6–12 scored
              clips; you can close this tab, they'll be waiting here.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} token={token} account={account} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
