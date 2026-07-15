CREATE INDEX accounting_drafts_document_id_idx ON accounting_drafts (document_id);
CREATE INDEX accounting_drafts_action_id_idx ON accounting_drafts (action_id);

DROP POLICY "Firms can read own accounting drafts" ON accounting_drafts;
DROP POLICY "Firms can insert own accounting drafts" ON accounting_drafts;
DROP POLICY "Firms can update own accounting drafts" ON accounting_drafts;

CREATE POLICY "Firms can read own accounting drafts" ON accounting_drafts
    FOR SELECT USING (firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true)));

CREATE POLICY "Firms can insert own accounting drafts" ON accounting_drafts
    FOR INSERT WITH CHECK (firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true)));

CREATE POLICY "Firms can update own accounting drafts" ON accounting_drafts
    FOR UPDATE USING (firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true)))
    WITH CHECK (firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true)));
