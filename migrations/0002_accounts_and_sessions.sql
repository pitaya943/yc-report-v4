-- People who can sign in, and their sign-ins.

create table accounts (
    id bigint generated always as identity primary key,
    display_name text not null unique,
    role text not null check (role in ('OWNER', 'ADMIN', 'USER')),
    zone text not null check (zone in ('WEST', 'SOUTH')),
    big_meter boolean not null default false,
    -- Null means not archived. A time, not a flag: payroll needs to know in
    -- which pay period the archiving happened.
    archived_at timestamptz,
    password_hash text not null,
    failed_count integer not null default 0 check (failed_count >= 0),
    last_failed_at timestamptz,
    locked_until timestamptz,
    constraint big_meter_only_on_users check (not big_meter or role = 'USER'),
    constraint owner_is_never_archived check (role <> 'OWNER' or archived_at is null)
);

create unique index accounts_only_one_owner on accounts ((true)) where role = 'OWNER';

create table sessions (
    id bigint generated always as identity primary key,
    account_id bigint not null references accounts (id),
    -- SHA-256 of the cookie's token; the token itself is never stored.
    token_hash text not null unique,
    csrf_token text not null,
    created_at timestamptz not null,
    last_used_at timestamptz not null,
    ended_at timestamptz
);
