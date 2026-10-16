/**
 * Tiny helper library for talking to our FastAPI backend.
 * All functions need the Supabase login token so the API knows WHO you are.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Clip = {
  id: string;
  job_id: string;
  title?: string | null;
  hook?: string | null;
  score?: number;
  start_seconds?: number;
  end_seconds?: number;
  video_url?: string | null;
  thumbnail_url?: string | null;
  hashtags?: string[];
};

export type Job = {
  id: string;
  status: "queued" | "processing" | "completed" | "failed" | string;
  stage?: string | null;
  progress?: number;
  source_filename?: string | null;
  duration_seconds?: number;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  clips: Clip[];
};


/** fetch with retry — flaky mobile networks / sleeping server should never show
 *  raw "Failed to fetch" to the user. */
async function fetchWithRetry(url: string, init: RequestInit, tries = 2): Promise<Response> {
  for (let i = 0; i < tries; i++) {
    try {
      return await fetch(url, init);
    } catch {
      await new Promise((r) => setTimeout(r, 1200));
    }
  }
  throw new Error("Network problem — internet check karke dobara try karo (server 1 min me jag jayega).");
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

/** Upload a video with progress updates (uses XHR so we can show a progress bar). */
export function uploadVideo(
  file: File,
  token: string,
  onProgress: (percent: number) => void
): Promise<{ job: Job }> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/videos/upload`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText || "{}");
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(body);
        } else {
          reject(new Error(body.detail ?? `Upload failed (HTTP ${xhr.status})`));
        }
      } catch {
        reject(new Error("Upload failed: unreadable server response."));
      }
    };

    xhr.onerror = () =>
      reject(
        new Error(
          "Upload failed: cannot reach the API server. Is the backend running?"
        )
      );

    xhr.send(form);
  });
}

/** Ask the backend to fetch a video from a link (YouTube, Facebook, X, ...) and clip it. */
export async function importFromLink(url: string, token: string): Promise<{ job: Job }> {
  const res = await fetch(`${API_URL}/api/videos/from-link`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail ?? `Could not start the link job (HTTP ${res.status})`);
  }
  return body;
}

/** Tiny ping that keeps the free server from napping while the dashboard is open. */
export async function keepApiWarm(): Promise<void> {
  try {
    await fetch(`${API_URL}/api/health`, { cache: "no-store" });
  } catch {
    /* machine may be waking up — that's fine */
  }
}

/** Transcript editor: re-cut a clip with chosen time ranges removed. */
export async function reEditClip(
  clipId: string,
  removed: [number, number][],
  token: string
): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${API_URL}/api/clips/${clipId}/re-edit`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ removed }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Re-cut failed (HTTP ${res.status})`);
  return body;
}

export async function listJobs(token: string): Promise<Job[]> {
  const res = await fetch(`${API_URL}/api/jobs`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Could not load jobs (HTTP ${res.status})`);
  const body = await res.json();
  return body.jobs ?? [];
}

export async function getJob(token: string, jobId: string): Promise<Job> {
  const res = await fetch(`${API_URL}/api/jobs/${jobId}`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Could not load job (HTTP ${res.status})`);
  const body = await res.json();
  return body.job;
}

export function downloadUrl(clipId: string): string {
  return `${API_URL}/api/clips/${clipId}/download`;
}

/** Open a clip download in a new tab, carrying the login token as a one-time code in the URL is
 *  not possible with plain links, so we fetch with the token and save the blob instead. */
export async function downloadClip(clip: Clip, token: string) {
  const res = await fetch(downloadUrl(clip.id), {
    headers: authHeaders(token),
    redirect: "follow",
  });
  if (!res.ok) throw new Error(`Download failed (HTTP ${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${(clip.title ?? "clip").replace(/[^\w\- ]+/g, "").slice(0, 60).trim() || "clip"}.mp4`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

// ==================== PLANS / PRO ====================

export type Account = {
  email: string;
  plan: "free" | "pro";
  videos_used_this_month: number;
  videos_limit: number | null;
  caption_style: string;
  sfx: boolean;
  enhance: boolean;
  reframe: string;
  dub: string;
  free_styles: string[];
  all_styles: string[];
};

export async function getAccount(token: string): Promise<Account> {
  const res = await fetchWithRetry(`${API_URL}/api/account`, { headers: authHeaders(token), cache: "no-store" });
  if (!res.ok) throw new Error(`Could not load account (HTTP ${res.status})`);
  return res.json();
}

export async function savePrefs(token: string, prefs: Partial<{
  caption_style: string; sfx: boolean; enhance: boolean; reframe: string; dub: string;
}>): Promise<void> {
  const res = await fetchWithRetry(`${API_URL}/api/account/prefs`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Could not save (HTTP ${res.status})`);
}

export async function redeemCode(token: string, code: string): Promise<{ message: string }> {
  const res = await fetchWithRetry(`${API_URL}/api/account/redeem`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Could not activate (HTTP ${res.status})`);
  return body;
}

export async function proEditClip(
  token: string,
  clipId: string,
  opts: { style?: string; trim_start?: number; trim_end?: number; enhance?: boolean; sfx?: boolean; reframe?: string }
): Promise<{ ok: boolean; message: string }> {
  const res = await fetchWithRetry(`${API_URL}/api/clips/${clipId}/pro-edit`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(opts),
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Editor failed (HTTP ${res.status})`);
  return body;
}

export async function scriptToVideo(token: string, script: string, style: string): Promise<{ job: Job }> {
  const res = await fetchWithRetry(`${API_URL}/api/videos/from-script`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ script, style }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Could not start (HTTP ${res.status})`);
  return body;
}
