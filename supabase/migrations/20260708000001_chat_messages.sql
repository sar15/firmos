CREATE TABLE IF NOT EXISTS public.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50),
    role VARCHAR(20) NOT NULL,  -- user | agent
    text TEXT NOT NULL,
    attached_workflow_id VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can insert their firm's chat messages"
    ON public.chat_messages
    FOR INSERT
    WITH CHECK (firm_id = current_setting('request.jwt.claims', true)::json->>'firm_id');

CREATE POLICY "Users can read their firm's chat messages"
    ON public.chat_messages
    FOR SELECT
    USING (firm_id = current_setting('request.jwt.claims', true)::json->>'firm_id');
