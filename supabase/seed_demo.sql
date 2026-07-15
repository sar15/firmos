-- Seed data for dev-firm-1
INSERT INTO clients (id, firm_id, legal_name, pan, gstin, entity_type, state, books_provider, compliance_status) VALUES
('cl-demo-1', 'dev-firm-1', 'Acme Corp', 'ABCDE1234F', '27ABCDE1234F1Z5', 'PRIVATE_LIMITED', 'Maharashtra', 'ZOHO_BOOKS', 'ON_TRACK'),
('cl-demo-2', 'dev-firm-1', 'Global Tech LLP', 'XYZDE5678F', '27XYZDE5678F1Z5', 'LLP', 'Maharashtra', 'QUICKBOOKS', 'DUE_SOON'),
('cl-demo-3', 'dev-firm-1', 'Local Traders', 'DEFGH9012F', '29DEFGH9012F1Z5', 'PROPRIETOR', 'Karnataka', 'TALLY', 'OVERDUE')
ON CONFLICT DO NOTHING;

INSERT INTO decisions (id, firm_id, client_id, document_id, document_url, vendor_name, amount, flag, urgency, status, recommendation, context_data, evidence, draft_response) VALUES
('dec-demo-1', 'dev-firm-1', 'cl-demo-1', 'GSTR-3B-OCT', 'https://example.com/gstr3b.pdf', 'Govt of India', 15400000, 'GSTR-3B Liability', 'medium', 'needs_review', 'Approve filing of GSTR-3B for October. ITC matched successfully.', '{"period": "Oct 2026", "itc": 50000}', '{"matched_invoices": 42}', 'Drafted return ready for submission.'),
('dec-demo-2', 'dev-firm-1', 'cl-demo-2', 'TDS-NOTICE-23', 'https://example.com/tds.pdf', 'Income Tax Dept', 450000, 'TDS Default Notice', 'high', 'needs_review', 'Respond to notice with challan proof. Interest calculated at 1.5%.', '{"section": "194J", "delay_days": 15}', '{"challan_no": "CH-12345"}', 'Drafted response letter acknowledging the delay and providing challan details.')
ON CONFLICT DO NOTHING;

INSERT INTO documents (id, firm_id, client_id, client_name, file_url, file_type, doc_kind, status, vendor_name, fields, line_items, total) VALUES
('doc-demo-1', 'dev-firm-1', 'cl-demo-1', 'Acme Corp', 'https://example.com/bill1.pdf', 'pdf', 'VENDOR_BILL', 'PENDING_REVIEW', 'Tech Supplies Inc', '[{"key": "invoice_number", "label": "Invoice No", "value": "INV-100", "confidence": 0.98, "level": "HIGH"}]'::jsonb, '[{"desc": "Laptops", "qty": 5, "rate": 50000, "amount": 250000}]'::jsonb, 25000000)
ON CONFLICT DO NOTHING;
