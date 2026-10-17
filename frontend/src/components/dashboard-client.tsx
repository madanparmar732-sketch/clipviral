"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Inbox, RefreshCw } from "lucide-react";

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

  return (
    <div className="space-y-8">
      <section className="rounded-2xl border border-white/10 bg-white/5 p-6 md:p-8">
        <div className="mb-6">
          <h2 className="text-xl font-semibold">Upload a new video</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Welcome back{userEmail ? `, ${userEmail}` : ""}. Drop a long video or paste a link
            (YouTube, Facebook, X, Instagram) — the AI cuts it into viral 9:16 clips with animated
            captions.
          </p>
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
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <Link href="/scheduler" className="rounded-full border border-white/10 px-3 py-1.5 hover:bg-white/5">
            📅 Scheduler & Collections
          </Link>
          <Link href="/settings/brand" className="rounded-full border border-white/10 px-3 py-1.5 hover:bg-white/5">
            🎨 Brand kit
          </Link>
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Your clips</h2>
          {account && (
            <span className={"rounded-full px-3 py-1 text-xs font-semibold " + (account.plan === "pro" ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/15 text-amber-300")}>
              {account.plan === "pro" ? "⭐ PRO" : `FREE — ${account.videos_used_this_month}/${account.videos_limit ?? "∞"} videos`}
            </span>
          )}
          {health && (
            <span
              className={
                "rounded-full px-3 py-1 text-xs font-semibold " +
                (health.ok ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300")
              }
              title={Object.entries(health.checks).map(([k, v]) => `${k}: ${v}`).join("\n")}
            >
              {health.ok ? "🟢 All systems OK" : `🔴 ${Object.entries(health.checks).filter(([, v]) => String(v).startsWith("FAIL")).map(([k]) => k).join(", ")}`}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={() => refresh()} disabled={loading}>
            <RefreshCw className="h-4 w-4" /> Refresh
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
          <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/15 py-16 text-center">
            <Inbox className="h-10 w-10 text-muted-foreground" />
            <p className="text-muted-foreground">
              No videos yet. Upload your first one above — the magic takes a few minutes.
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
