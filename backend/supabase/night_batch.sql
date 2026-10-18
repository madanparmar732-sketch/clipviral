-- ClipViral NIGHT BATCH queue — run ONCE in Supabase SQL editor.
-- Safe to re-run (IF NOT EXISTS everywhere).
create table if not exists public.render_assets (
  id uuid primary key,
  job_id uuid not null,
  clip_id uuid not null,
  user_id uuid,
  clip_index int not null default 1,
  mode text not null default 'night',          -- 'night' | 'now'
  status text not null default 'queued',        -- 'queued' | 'processing' | 'done' | 'failed'
  payload jsonb not null default '{}'::jsonb,
  attempts int not null default 0,
  error text,
  heartbeat timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists render_assets_claim_idx
  on public.render_assets (status, created_at);
create index if not exists render_assets_job_idx
  on public.render_assets (job_id);

-- If your project enforces RLS on new tables by default, this table is
-- service-role only (the browser never touches it) — no policies needed.
