CREATE TABLE archive (
    id          bigserial PRIMARY KEY,
    kind        text        NOT NULL CHECK (kind IN ('daily', 'monthly')),
    period_date date        NOT NULL,
    automatic   boolean     NOT NULL,
    created_at  timestamptz NOT NULL,
    content     text
);

-- The guard: at most one automatic archive per kind and date.
CREATE UNIQUE INDEX archive_one_automatic ON archive (kind, period_date) WHERE automatic;

CREATE TABLE session (
    id         bigserial PRIMARY KEY,
    expires_at timestamptz NOT NULL
);
