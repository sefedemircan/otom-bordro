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
