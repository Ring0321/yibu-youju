CREATE TABLE g0_service.runs (
    id uuid PRIMARY KEY,
    prompt text NOT NULL CHECK (length(prompt) BETWEEN 1 AND 200),
    status text NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'WAITING_INPUT', 'COMPLETED')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE g0_service.commands (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES g0_service.runs(id),
    kind text NOT NULL CHECK (kind IN ('start', 'resume')),
    payload jsonb NOT NULL,
    job_id bigint,
    processed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (run_id, kind)
);

CREATE TABLE g0_service.events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES g0_service.runs(id),
    command_id uuid NOT NULL REFERENCES g0_service.commands(id),
    kind text NOT NULL CHECK (kind IN (
        'intent_received', 'waiting_input', 'input_received', 'probe_completed'
    )),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (command_id, kind)
);

CREATE INDEX g0_events_run_id ON g0_service.events(run_id, id);
