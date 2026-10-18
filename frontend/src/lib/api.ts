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
  throw new Error("Network hiccup — the server may be waking up. Retrying usually fixes it in a few seconds.");
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
    try {
      form.append("options", JSON.stringify(getCreateOptions()));
    } catch {
      form.append("options", "{}");
    }

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
  let options = {};
  try {
    options = getCreateOptions();
  } catch {
    options = {};
  }
  const res = await fetch(`${API_URL}/api/videos/from-link`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ url, options }),
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
  style_names?: Record<string, string>;
};

export async function renderClipNow(token: string, clipId: string): Promise<void> {
  const res = await fetchWithRetry(`${API_URL}/api/clips/${clipId}/render-now`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok && res.status !== 409) throw new Error(`Could not queue render (HTTP ${res.status})`);
}

export async function recaptionClip(token: string, clipId: string, style: string): Promise<void> {
  const res = await fetchWithRetry(`${API_URL}/api/clips/${clipId}/recaption`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ style }),
  });
  if (!res.ok) throw new Error(`Could not re-render (HTTP ${res.status})`);
}

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
  opts: { style?: string; trim_start?: number; trim_end?: number; enhance?: boolean; sfx?: boolean; reframe?: string; removed?: [number, number][]; aspect?: string; layout?: string; caption_pos?: string; size_scale?: number; caps?: boolean; brightness?: number; contrast?: number; saturation?: number; volume?: number; words_override?: { start: number; end: number; word: string }[] }
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

export async function getClip(token: string, clipId: string): Promise<Clip> {
  const res = await fetchWithRetry(`${API_URL}/api/clips/${clipId}`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Could not load clip (HTTP ${res.status})`);
  const body = await res.json();
  return body.clip;
}

export async function updateClipMeta(
  token: string,
  clipId: string,
  meta: { title?: string; hook?: string; hashtags?: string[] }
): Promise<void> {
  const res = await fetchWithRetry(`${API_URL}/api/clips/${clipId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(meta),
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Could not save (HTTP ${res.status})`);
}


export async function cancelJob(token: string, jobId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://clipviral-r5m1.onrender.com"}/api/jobs/${jobId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Cancel failed");
  return res.json();
}

/* ============================ OPUSCLIP-PARITY API ============================ */

export type CreateOptions = {
  genre?: string;
  topic_keywords?: string[];
  custom_prompt?: string;
  clip_durations?: [number, number][];
  range?: { startSec?: number; endSec?: number };
  aspect?: string;
  remove_fillers?: boolean;
  auto_censor?: boolean;
  source_lang?: string;
  webhook_url?: string;
  caption_style?: string;
  brand_kit_id?: string;
};

const OPTS_KEY = "clipviral_options";

export function getCreateOptions(): CreateOptions {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(OPTS_KEY) || "{}");
  } catch {
    return {};
  }
}

export function saveCreateOptions(opts: CreateOptions): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(OPTS_KEY, JSON.stringify(opts));
}

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetchWithRetry(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...authHeaders(token),
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.detail || "Request failed — please try again.");
  return body as T;
}

export type Collection = { id: string; name: string; clip_ids: string[] };

export const listCollections = (t: string) => api<{ collections: Collection[] }>("/api/collections", t);
export const createCollection = (t: string, name: string) =>
  api<{ collection: Collection }>("/api/collections", t, { method: "POST", body: JSON.stringify({ name }) });
export const deleteCollection = (t: string, id: string) =>
  api<{ ok: boolean }>(`/api/collections/${id}`, t, { method: "DELETE" });
export const collectionItem = (t: string, id: string, clipId: string, remove = false) =>
  api<{ collection: Collection }>(`/api/collections/${id}/items`, t, {
    method: "POST",
    body: JSON.stringify({ clip_id: clipId, remove }),
  });

export const duplicateClip = (t: string, clipId: string) =>
  api<{ clip: Clip }>(`/api/clips/${clipId}/duplicate`, t, { method: "POST", body: "{}" });
export const shareClip = (t: string, clipId: string) =>
  api<{ share_id: string; share_url: string }>(`/api/clips/${clipId}/share`, t, {
    method: "POST",
    body: JSON.stringify({ enabled: true }),
  });
export const shareJob = (t: string, jobId: string) =>
  api<{ share_id: string }>(`/api/jobs/${jobId}/share`, t, {
    method: "POST",
    body: JSON.stringify({ enabled: true }),
  });
export const getShare = (shareId: string) =>
  fetch(`${API_URL}/api/share/${shareId}`).then((r) => (r.ok ? r.json() : Promise.reject(new Error("not found"))));

export function subtitlesUrl(clipId: string, kind: "srt" | "vtt", token: string): string {
  // downloaded via fetch blob so the auth header is attached
  return `${API_URL}/api/clips/${clipId}/subtitles.${kind}?token=${encodeURIComponent(token)}`;
}

export async function downloadSubtitles(clip: Clip, kind: "srt" | "vtt", token: string) {
  const res = await fetchWithRetry(`${API_URL}/api/clips/${clip.id}/subtitles.${kind}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Could not build subtitles.");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${(clip.title || "clip").replace(/[^\w\- ]+/g, "").slice(0, 40) || "clip"}.${kind}`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export const makeThumbnails = (t: string, clipId: string, prompt = "") =>
  api<{ ok: boolean; message: string }>(`/api/clips/${clipId}/thumbnails`, t, {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
export const censorClip = (t: string, clipId: string, beep = true) =>
  api<{ ok: boolean; message: string }>(`/api/clips/${clipId}/censor`, t, {
    method: "POST",
    body: JSON.stringify({ beep }),
  });
export const translateClip = (t: string, clipId: string, lang: string, burn = true) =>
  api<{ ok: boolean; message: string }>(`/api/clips/${clipId}/translate`, t, {
    method: "POST",
    body: JSON.stringify({ lang, burn }),
  });

export type SocialPack = Record<string, { title: string; description: string; hashtags: string[] }>;
export const getSocialPack = (t: string, clipId: string) =>
  api<{ pack: SocialPack; platforms: string[] }>(`/api/clips/${clipId}/social-pack`, t);
export const buildSocialPack = (t: string, clipId: string, prompt = "", lang = "en") =>
  api<{ pack: SocialPack }>(`/api/clips/${clipId}/social-pack`, t, {
    method: "POST",
    body: JSON.stringify({ prompt, lang }),
  });

export type Schedule = {
  id: string; clip_id: string; platform: string; publish_at: string;
  title?: string; description?: string; status?: string;
};
export const listSchedules = (t: string) => api<{ schedules: Schedule[] }>("/api/schedules", t);
export const createSchedule = (t: string, s: Omit<Schedule, "id" | "status">) =>
  api<{ schedule: Schedule }>("/api/schedules", t, { method: "POST", body: JSON.stringify(s) });
export const deleteSchedule = (t: string, id: string) =>
  api<{ ok: boolean }>(`/api/schedules/${id}`, t, { method: "DELETE" });

export type BrandKit = {
  id: string; name: string; logo_url?: string; caption_style?: string; accent?: string;
};
export const listBrandKits = (t: string) => api<{ brand_kits: BrandKit[] }>("/api/brand-kits", t);
export const saveBrandKit = (t: string, kit: Partial<BrandKit> & { logo_data_url?: string }) =>
  api<{ brand_kit: BrandKit }>("/api/brand-kits", t, { method: "PUT", body: JSON.stringify(kit) });
