-- The audit trail. Rows are only ever added: the trigger refuses every
-- UPDATE, DELETE and TRUNCATE, whatever role runs them.

create table audit_log (
    id bigint generated always as identity primary key,
    at timestamptz not null,
    actor_account_id bigint,
    actor_name text not null,
    type text not null,
    description text not null
);

create function audit_log_is_append_only() returns trigger
language plpgsql as $$
begin
    raise exception 'audit_log is append-only: % is not allowed', tg_op;
end;
$$;

create trigger audit_log_append_only
    before update or delete or truncate on audit_log
    for each statement execute function audit_log_is_append_only();
