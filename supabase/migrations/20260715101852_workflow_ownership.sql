-- AG-001: workflow checkpoints are addressable only through an owned run.
CREATE TABLE workflow_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id varchar(255) NOT NULL,
    created_by uuid NOT NULL,
    workflow_id varchar(20) NOT NULL,
    thread_id varchar(255) NOT NULL,
    storage_thread_id varchar(600) NOT NULL UNIQUE,
    client_id varchar(50),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (firm_id, thread_id)
);

CREATE INDEX workflow_runs_owner_idx
    ON workflow_runs (firm_id, created_by, updated_at DESC);

ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY workflow_runs_owner ON workflow_runs FOR ALL
    USING (
        firm_id = current_firm_id()
        AND created_by::text = current_user_id()
    )
    WITH CHECK (
        firm_id = current_firm_id()
        AND created_by::text = current_user_id()
    );
