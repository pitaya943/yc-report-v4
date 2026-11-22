-- One row per sign-in attempt that was evaluated, for the per-address rate limit.

create table sign_in_attempts (
    id bigint generated always as identity primary key,
    client_address text not null,
    attempted_at timestamptz not null
);

create index sign_in_attempts_by_address on sign_in_attempts (client_address, attempted_at);
