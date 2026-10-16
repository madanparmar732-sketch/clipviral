-- ============================================================
-- OpusClip Clone — Supabase database schema
-- HOW TO USE: open Supabase dashboard -> SQL Editor -> New query
-- -> paste this whole file -> press "Run". That's it.
-- ============================================================

-- 1) Jobs table: one row per uploaded video
create table if not exists public.jobs (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid references auth.users (id) on delete cascade,
    status           text not null default 'queued',   -- queued | processing | completed | failed
    stage            text default 'queued',            -- human-readable pipeline stage
    progress         integer not null default 0,       -- 0..100
    source_filename  text,
    source_size_bytes bigint default 0,
    duration_seconds double precision default 0,
    error            text,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

-- 2) Clips table: one row per finished short clip
create table if not exists public.clips (
    id             uuid primary key default gen_random_uuid(),
    job_id         uuid not null references public.jobs (id) on delete cascade,
    user_id        uuid references auth.users (id) on delete cascade,
    title          text,
    hook           text,
    score          integer default 0,
    start_seconds  double precision default 0,
    end_seconds    double precision default 0,
    video_url      text,
    thumbnail_url  text,
    storage_path   text,
    hashtags       text[] default '{}',
    created_at     timestamptz not null default now()
);

create index if not exists idx_jobs_user on public.jobs (user_id, created_at desc);
create index if not exists idx_clips_job on public.clips (job_id);
create index if not exists idx_clips_user on public.clips (user_id);

-- 3) Security rules (Row Level Security)
--    Users can only READ their own jobs/clips from the browser.
--    Writing is done by our backend using the "service role key",
--    which bypasses these rules on purpose.
alter table public.jobs enable row level security;
alter table public.clips enable row level security;

drop policy if exists "users read own jobs" on public.jobs;
create policy "users read own jobs"
    on public.jobs for select
    using (auth.uid() = user_id);

drop policy if exists "users read own clips" on public.clips;
create policy "users read own clips"
    on public.clips for select
    using (auth.uid() = user_id);

-- 4) Storage bucket for finished clips (public read so videos play in <video> tags)
insert into storage.buckets (id, name, public)
values ('clips', 'clips', true)
on conflict (id) do nothing;

drop policy if exists "public read clips bucket" on storage.objects;
create policy "public read clips bucket"
    on storage.objects for select
    using (bucket_id = 'clips');

drop policy if exists "authenticated upload clips" on storage.objects;
create policy "authenticated upload clips"
    on storage.objects for insert
    with check (bucket_id = 'clips');
