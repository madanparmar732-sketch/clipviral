-- ClipViral phone-worker lease columns (idempotent — safe to run twice)
alter table public.jobs add column if not exists lease_owner text;
alter table public.jobs add column if not exists lease_heartbeat timestamptz;
create index if not exists jobs_lease_idx on public.jobs (lease_owner, lease_heartbeat);
