create table if not exists public.payroll_uploads (
  id uuid primary key default gen_random_uuid(),
  source_type text not null check (source_type in ('report', 'calc')),
  filename text not null,
  content_type text,
  file_size bigint not null default 0 check (file_size >= 0),
  row_count integer not null default 0 check (row_count >= 0),
  schema_version integer not null default 1,
  created_by uuid references auth.users(id) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  last_accessed_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '24 hours')
);

create table if not exists public.payroll_upload_rows (
  id bigint generated always as identity primary key,
  upload_id uuid not null references public.payroll_uploads(id) on delete cascade,
  row_index integer not null check (row_index >= 0),
  sicilno text,
  ad text,
  soyad text,
  personel text,
  firma text,
  bolum text,
  pozisyon text,
  mesaitarih date,
  row_year integer,
  row_month integer,
  ms numeric(12,2),
  nm numeric(12,2),
  fm numeric(12,2),
  izs numeric(12,2),
  yizs numeric(12,2),
  sgkizs numeric(12,2),
  uczizs numeric(12,2),
  rm numeric(12,2),
  em numeric(12,2),
  row_data jsonb not null,
  created_at timestamptz not null default now(),
  unique (upload_id, row_index)
);

create table if not exists public.payroll_chat_sessions (
  id uuid primary key default gen_random_uuid(),
  upload_id uuid not null references public.payroll_uploads(id) on delete cascade,
  title text,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.payroll_chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.payroll_chat_sessions(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  sql_text text,
  result_rows jsonb,
  created_at timestamptz not null default now()
);

create index if not exists payroll_uploads_expires_at_idx on public.payroll_uploads (expires_at);
create index if not exists payroll_upload_rows_upload_idx on public.payroll_upload_rows (upload_id, row_index);
create index if not exists payroll_upload_rows_upload_sicil_idx on public.payroll_upload_rows (upload_id, sicilno);
create index if not exists payroll_upload_rows_upload_date_idx on public.payroll_upload_rows (upload_id, mesaitarih);
create index if not exists payroll_chat_sessions_upload_idx on public.payroll_chat_sessions (upload_id, updated_at desc);
create index if not exists payroll_chat_messages_session_idx on public.payroll_chat_messages (session_id, created_at);

alter table public.payroll_uploads enable row level security;
alter table public.payroll_upload_rows enable row level security;
alter table public.payroll_chat_sessions enable row level security;
alter table public.payroll_chat_messages enable row level security;

drop policy if exists "Service role manages payroll_uploads" on public.payroll_uploads;
create policy "Service role manages payroll_uploads"
  on public.payroll_uploads
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists "Service role manages payroll_upload_rows" on public.payroll_upload_rows;
create policy "Service role manages payroll_upload_rows"
  on public.payroll_upload_rows
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists "Service role manages payroll_chat_sessions" on public.payroll_chat_sessions;
create policy "Service role manages payroll_chat_sessions"
  on public.payroll_chat_sessions
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists "Service role manages payroll_chat_messages" on public.payroll_chat_messages;
create policy "Service role manages payroll_chat_messages"
  on public.payroll_chat_messages
  for all
  to service_role
  using (true)
  with check (true);

create or replace function public.current_payroll_upload_id()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('app.current_payroll_upload_id', true), '')::uuid;
$$;

create or replace view public.payroll_query_view
with (security_invoker = true)
as
select
  r.upload_id,
  r.row_index,
  r.sicilno,
  r.ad,
  r.soyad,
  r.personel,
  r.firma,
  r.bolum,
  r.pozisyon,
  r.mesaitarih,
  r.row_year,
  r.row_month,
  r.ms,
  r.nm,
  r.fm,
  r.izs,
  r.yizs,
  r.sgkizs,
  r.uczizs,
  r.rm,
  r.em,
  r.row_data,
  u.filename,
  u.source_type,
  u.created_at,
  u.expires_at
from public.payroll_upload_rows r
join public.payroll_uploads u on u.id = r.upload_id
where r.upload_id = public.current_payroll_upload_id();

create or replace function public.execute_payroll_query(
  p_upload_id uuid,
  p_sql text,
  p_limit integer default 200
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  normalized_sql text;
  limited_sql text;
  effective_limit integer := greatest(1, least(coalesce(p_limit, 200), 200));
  payload jsonb;
begin
  if p_upload_id is null then
    raise exception 'upload_id is required';
  end if;

  normalized_sql := trim(coalesce(p_sql, ''));
  if normalized_sql = '' then
    raise exception 'sql is required';
  end if;

  normalized_sql := regexp_replace(normalized_sql, '\s+', ' ', 'g');

  if normalized_sql ~ ';' then
    raise exception 'multiple statements are not allowed';
  end if;

  if normalized_sql !~* '^(select|with) ' then
    raise exception 'only SELECT queries are allowed';
  end if;

  if normalized_sql ~* '\m(insert|update|delete|drop|alter|create|grant|revoke|truncate|call|copy|comment|vacuum|analyze|refresh|merge)\M' then
    raise exception 'forbidden keyword detected';
  end if;

  if normalized_sql !~* '\m(from|join)\M\s+(public\.)?payroll_query_view\M' then
    raise exception 'queries must target payroll_query_view';
  end if;

  perform set_config('statement_timeout', '4000', true);
  perform set_config('app.current_payroll_upload_id', p_upload_id::text, true);

  limited_sql := format(
    'with query_result as (%s) select coalesce(jsonb_agg(row_to_json(query_result)), ''[]''::jsonb) from (select * from query_result limit %s) query_result',
    normalized_sql,
    effective_limit
  );
  execute limited_sql into payload;

  return coalesce(payload, '[]'::jsonb);
end;
$$;

revoke all on function public.execute_payroll_query(uuid, text, integer) from public, anon, authenticated;
grant execute on function public.execute_payroll_query(uuid, text, integer) to service_role;

create or replace function public.cleanup_expired_payroll_uploads()
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  deleted_count integer;
begin
  delete from public.payroll_uploads
  where expires_at <= now();

  get diagnostics deleted_count = row_count;
  return deleted_count;
end;
$$;

revoke all on function public.cleanup_expired_payroll_uploads() from public, anon, authenticated;
grant execute on function public.cleanup_expired_payroll_uploads() to service_role;

-- ---------------------------------------------------------------------------
-- Monthly report snapshots (AI queries these, not raw Meyer rows)
-- ---------------------------------------------------------------------------

create table if not exists public.payroll_report_runs (
  id uuid primary key default gen_random_uuid(),
  upload_id uuid not null references public.payroll_uploads(id) on delete cascade,
  year integer not null check (year >= 2000),
  month integer not null check (month between 1 and 12),
  label text not null,
  period_start date,
  period_end date,
  employee_count integer not null default 0,
  record_count integer not null default 0,
  total_nm numeric(14,2) not null default 0,
  total_fm numeric(14,2) not null default 0,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '24 hours'),
  unique (upload_id, year, month)
);

create table if not exists public.payroll_report_rows (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.payroll_report_runs(id) on delete cascade,
  upload_id uuid not null references public.payroll_uploads(id) on delete cascade,
  dataset text not null check (dataset in ('summary', 'weekly', 'daily', 'monthly')),
  row_index integer not null check (row_index >= 0),
  sicil_no text,
  personel text,
  firma text,
  bolum text,
  pozisyon text,
  calisma_gunu integer,
  normal_calisma numeric(14,2),
  fazla_mesai numeric(14,2),
  fm_nm_aktarim numeric(14,2),
  yillik_izin_gun integer,
  ucretli_izin_gun integer,
  rapor_gun integer,
  ucretsiz_izin_gun integer,
  devamsizlik_gun integer,
  hafta_tatili_gun integer,
  pazar_kesintisi integer,
  hafta text,
  tarih date,
  kod text,
  durum_aciklamasi text,
  pazar_durumu text,
  nm_guncel numeric(14,2),
  fm_guncel numeric(14,2),
  row_data jsonb not null,
  created_at timestamptz not null default now(),
  unique (run_id, dataset, row_index)
);

create or replace view public.payroll_report_summary_view
with (security_invoker = true) as
select
  r.run_id, r.upload_id, rr.year, rr.month, rr.label as period_label,
  r.sicil_no, r.personel, r.firma, r.bolum, r.pozisyon,
  r.calisma_gunu, r.normal_calisma, r.fazla_mesai, r.fm_nm_aktarim,
  r.yillik_izin_gun, r.ucretli_izin_gun, r.rapor_gun, r.ucretsiz_izin_gun,
  r.devamsizlik_gun, r.hafta_tatili_gun, r.pazar_kesintisi, r.row_data
from public.payroll_report_rows r
join public.payroll_report_runs rr on rr.id = r.run_id
where r.dataset = 'summary'
  and r.run_id = public.current_payroll_run_id();

create or replace view public.payroll_report_weekly_view
with (security_invoker = true) as
select
  r.run_id, r.upload_id, rr.year, rr.month, rr.label as period_label,
  r.sicil_no, r.personel, r.hafta, r.normal_calisma, r.fazla_mesai,
  r.fm_nm_aktarim, r.pazar_durumu, r.row_data
from public.payroll_report_rows r
join public.payroll_report_runs rr on rr.id = r.run_id
where r.dataset = 'weekly'
  and r.run_id = public.current_payroll_run_id();

create or replace view public.payroll_report_daily_view
with (security_invoker = true) as
select
  r.run_id, r.upload_id, rr.year, rr.month, rr.label as period_label,
  r.sicil_no, r.personel, r.firma, r.bolum, r.pozisyon, r.tarih, r.kod,
  r.durum_aciklamasi, r.pazar_durumu, r.nm_guncel, r.fm_guncel, r.row_data
from public.payroll_report_rows r
join public.payroll_report_runs rr on rr.id = r.run_id
where r.dataset = 'daily'
  and r.run_id = public.current_payroll_run_id();

-- Preferred RPC signature for AI (year/month required)
create or replace function public.execute_payroll_query(
  p_upload_id uuid,
  p_sql text,
  p_limit integer default 200,
  p_year integer default null,
  p_month integer default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  normalized_sql text;
  limited_sql text;
  effective_limit integer := greatest(1, least(coalesce(p_limit, 200), 200));
  payload jsonb;
  run_uuid uuid;
begin
  if p_upload_id is null then
    raise exception 'upload_id is required';
  end if;
  if p_year is null or p_month is null then
    raise exception 'year and month are required for report queries';
  end if;

  select id into run_uuid
  from public.payroll_report_runs
  where upload_id = p_upload_id and year = p_year and month = p_month
  order by created_at desc
  limit 1;

  if run_uuid is null then
    raise exception 'report snapshot not found for upload/period';
  end if;

  normalized_sql := trim(coalesce(p_sql, ''));
  normalized_sql := regexp_replace(normalized_sql, '\s+', ' ', 'g');
  if normalized_sql ~ ';' then raise exception 'multiple statements are not allowed'; end if;
  if normalized_sql !~* '^(select|with) ' then raise exception 'only SELECT queries are allowed'; end if;
  if normalized_sql ~* '\m(insert|update|delete|drop|alter|create|grant|revoke|truncate|call|copy|comment|vacuum|analyze|refresh|merge)\M' then
    raise exception 'forbidden keyword detected';
  end if;
  if normalized_sql !~* '\m(from|join)\M\s+(public\.)?payroll_report_(summary|weekly|daily)_view\M' then
    raise exception 'queries must target payroll_report_summary_view, payroll_report_weekly_view or payroll_report_daily_view';
  end if;

  perform set_config('statement_timeout', '4000', true);
  perform set_config('app.current_payroll_run_id', run_uuid::text, true);

  limited_sql := format(
    'with query_result as (%s) select coalesce(jsonb_agg(row_to_json(query_result)), ''[]''::jsonb) from (select * from query_result limit %s) query_result',
    normalized_sql,
    effective_limit
  );
  execute limited_sql into payload;
  return coalesce(payload, '[]'::jsonb);
end;
$$;

revoke all on function public.execute_payroll_query(uuid, text, integer, integer, integer) from public, anon, authenticated;
grant execute on function public.execute_payroll_query(uuid, text, integer, integer, integer) to service_role;
