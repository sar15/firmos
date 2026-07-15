"""Static catalogue of connector capabilities; connection state comes from the database."""

CONNECTOR_CATALOG = [
    {
        "title": "FEATURED",
        "caption": "Recommended for CA firms",
        "items": [
            {"id": "c1", "name": "Zoho Books", "category": "FEATURED", "description": "Sync registers; propose and approval-post bills and invoices", "status": "DISCONNECTED", "authMethod": "OAUTH", "lastSyncedAt": None},
            {"id": "c2", "name": "GSTN evidence upload", "category": "FEATURED", "description": "Upload downloaded GSTR-2B evidence; filing stays manual", "status": "DISCONNECTED", "authMethod": "CONSENT", "lastSyncedAt": None},
            {"id": "c3", "name": "Income Tax Portal", "category": "FEATURED", "description": "Planned — ITR drafting remains inside firmOS; portal filing is manual", "status": "DISCONNECTED", "authMethod": "CREDENTIALS", "lastSyncedAt": None},
            {"id": "c4", "name": "WhatsApp Business", "category": "FEATURED", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "OAUTH", "lastSyncedAt": None},
        ],
    },
    {
        "title": "ACCOUNTING & BOOKS",
        "items": [
            {"id": "c5", "name": "Tally Prime", "category": "ACCOUNTING", "description": "Bridge read/sync plus guarded purchase-voucher queueing", "status": "DISCONNECTED", "authMethod": "API_KEY", "lastSyncedAt": None},
            {"id": "c6", "name": "QuickBooks", "category": "ACCOUNTING", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "OAUTH", "lastSyncedAt": None},
            {"id": "c7", "name": "Vyapar", "category": "ACCOUNTING", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "API_KEY", "lastSyncedAt": None},
            {"id": "c8", "name": "Excel / CSV Import", "category": "ACCOUNTING", "description": "Use the document and bank-statement upload flows", "status": "DISCONNECTED", "authMethod": "CONSENT", "lastSyncedAt": None},
        ],
    },
    {
        "title": "GOVERNMENT & COMPLIANCE PORTALS",
        "items": [
            {"id": "c9", "name": "TRACES", "category": "GOVERNMENT", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "CREDENTIALS", "lastSyncedAt": None},
            {"id": "c10", "name": "MCA21", "category": "GOVERNMENT", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "CREDENTIALS", "lastSyncedAt": None},
            {"id": "c11", "name": "EPFO / ESIC", "category": "GOVERNMENT", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "CREDENTIALS", "lastSyncedAt": None},
            {"id": "c12", "name": "e-Invoice (IRP)", "category": "GOVERNMENT", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "API_KEY", "lastSyncedAt": None},
        ],
    },
    {
        "title": "BANKING & PAYMENTS",
        "items": [
            {"id": "c13", "name": "Account Aggregator", "category": "BANKING", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "CONSENT", "lastSyncedAt": None},
            {"id": "c14", "name": "ICICI / HDFC / SBI statements", "category": "BANKING", "description": "Upload supported statement files for matching and review", "status": "DISCONNECTED", "authMethod": "CREDENTIALS", "lastSyncedAt": None},
            {"id": "c15", "name": "Razorpay", "category": "BANKING", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "API_KEY", "lastSyncedAt": None},
        ],
    },
    {
        "title": "DOCUMENTS & COMMUNICATION",
        "items": [
            {"id": "c16", "name": "Gmail", "category": "DOCS", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "OAUTH", "lastSyncedAt": None},
            {"id": "c17", "name": "Google Drive", "category": "DOCS", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "OAUTH", "lastSyncedAt": None},
            {"id": "c18", "name": "Dropbox", "category": "DOCS", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "OAUTH", "lastSyncedAt": None},
        ],
    },
    {
        "title": "DEVELOPER / ADVANCED",
        "caption": "For custom workflows",
        "items": [
            {"id": "c19", "name": "MCP Server", "category": "DEVELOPER", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "API_KEY", "lastSyncedAt": None},
            {"id": "c20", "name": "Webhooks", "category": "DEVELOPER", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "API_KEY", "lastSyncedAt": None},
            {"id": "c21", "name": "REST API & Keys", "category": "DEVELOPER", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "API_KEY", "lastSyncedAt": None},
            {"id": "c22", "name": "CLI", "category": "DEVELOPER", "description": "Planned — not available yet", "status": "DISCONNECTED", "authMethod": "API_KEY", "lastSyncedAt": None},
        ],
    },
]
