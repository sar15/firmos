use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Company {
    pub name: String,
    pub guid: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Probe {
    pub healthy: bool,
    pub tally_version: String,
    pub license_mode: String,
    pub protocols: Vec<String>,
    pub companies: Vec<Company>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Ledger {
    pub guid: String,
    pub name: String,
    pub parent_group: String,
    pub opening_paise: i64,
    pub closing_paise: i64,
    pub is_revenue: bool,
    pub active: bool,
    pub gstin: String,
    pub tax_type: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Entry {
    pub ledger_name: String,
    pub amount_paise: i64,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct GstDetail {
    pub ledger_name: String,
    pub tax_type: String,
    pub amount_paise: i64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Voucher {
    pub guid: String,
    pub remote_id: String,
    pub voucher_number: String,
    pub date: String,
    pub voucher_type: String,
    pub party_name: String,
    #[serde(default)]
    pub party_gstin: String,
    #[serde(default)]
    pub place_of_supply: String,
    pub narration: String,
    pub reference: String,
    pub entries: Vec<Entry>,
    pub altered: bool,
    pub cancelled: bool,
    pub master_id: String,
    pub alteration_id: String,
    pub status: String,
    pub gst_details: Vec<GstDetail>,
    #[serde(default)]
    pub e_invoice: serde_json::Value,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Period {
    pub from_date: String,
    pub to_date: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Snapshot {
    pub company_guid: String,
    pub period: Period,
    pub completeness: String,
    pub ledgers: Vec<Ledger>,
    pub vouchers: Vec<Voucher>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct PairInput {
    pub cloud_url: String,
    pub pairing_code: String,
    pub device_name: String,
    pub company_name: String,
    pub company_guid: String,
    pub port: u16,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AgentConfig {
    pub cloud_url: String,
    pub device_id: String,
    pub firm_id: String,
    pub device_name: String,
    pub company_name: String,
    pub company_guid: String,
    pub port: u16,
    #[serde(default)]
    pub write_enabled: bool,
    #[serde(default)]
    pub last_read_at: u64,
    #[serde(default)]
    pub last_write_at: u64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AgentStatus {
    pub paired: bool,
    pub config: Option<AgentConfig>,
    pub tally: Option<Probe>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Action {
    pub action_id: String,
    #[serde(default = "purchase_operation")]
    pub operation: String,
    pub remote_id: String,
    pub payload: serde_json::Value,
}

fn purchase_operation() -> String {
    "tally.write.purchase_voucher.create".into()
}
