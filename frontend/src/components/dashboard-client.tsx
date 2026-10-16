"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Inbox, RefreshCw } from "lucide-react";

import JobCard from "@/components/job-card";
import LinkImport from "@/components/link-import";
import UploadDropzone from "@/components/upload-dropzone";
import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/supabase/client";
import { listJobs, keepApiWarm, type Job } from "@/lib/api";

export default function DashboardClient({ userEmail }: { userEmail: string }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [token, setToken] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async (activeToken?: string) => {
    const t = activeToken ?? token;
    if (!t) return;
    try {
      const data = await listJobs(t);
      setJobs(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load jobs.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  // 1) Get the login token once.
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => {
      const t = data.session?.access_token ?? "";
      setToken(t);
      refresh(t);
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
        <UploadDropzone compact />
        <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
          <div className="h-px flex-1 bg-white/10" />
          <span>OR</span>
          <div className="h-px flex-1 bg-white/10" />
        </div>
        <LinkImport />
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Your clips</h2>
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
              <JobCard key={job.id} job={job} token={token} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
