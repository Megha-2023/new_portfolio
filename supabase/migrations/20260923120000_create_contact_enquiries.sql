create extension if not exists pgcrypto with schema extensions;
create extension if not exists pg_cron with schema pg_catalog;

create table public.contact_enquiries (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  name text not null check (char_length(name) between 2 and 100),
  email text not null check (char_length(email) between 3 and 254),
  enquiry_type text not null check (enquiry_type in ('development', 'teaching', 'other')),
  message text not null check (char_length(message) between 10 and 5000),
  language text not null check (language in ('en', 'fr')),
  privacy_acknowledged_at timestamptz not null,
  notification_sent boolean not null default false,
  notification_error text
);

create index contact_enquiries_created_at_idx
  on public.contact_enquiries (created_at);
create index contact_enquiries_unsent_idx
  on public.contact_enquiries (created_at)
  where notification_sent = false;

alter table public.contact_enquiries enable row level security;
revoke all on table public.contact_enquiries from anon, authenticated;

create table public.contact_rate_limits (
  id bigint generated always as identity primary key,
  ip_hash text not null check (char_length(ip_hash) = 64),
  created_at timestamptz not null default now()
);

create index contact_rate_limits_lookup_idx
  on public.contact_rate_limits (ip_hash, created_at);

alter table public.contact_rate_limits enable row level security;
revoke all on table public.contact_rate_limits from anon, authenticated;

create or replace function public.consume_contact_rate_limit(p_ip_hash text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $function$
declare
  recent_count integer;
begin
  if char_length(p_ip_hash) <> 64 then
    raise exception 'Invalid IP hash';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext(p_ip_hash));

  delete from public.contact_rate_limits
  where ip_hash = p_ip_hash
    and created_at < now() - interval '1 hour';

  select count(*)
  into recent_count
  from public.contact_rate_limits
  where ip_hash = p_ip_hash
    and created_at >= now() - interval '1 hour';

  if recent_count >= 5 then
    return false;
  end if;

  insert into public.contact_rate_limits (ip_hash)
  values (p_ip_hash);

  return true;
end;
$function$;

revoke all on function public.consume_contact_rate_limit(text) from public, anon, authenticated;
grant execute on function public.consume_contact_rate_limit(text) to service_role;

select cron.schedule(
  'delete-expired-contact-data',
  '17 3 * * *',
  $cleanup$
    delete from public.contact_enquiries
    where created_at < now() - interval '12 months';

    delete from public.contact_rate_limits
    where created_at < now() - interval '2 hours';
  $cleanup$
);

