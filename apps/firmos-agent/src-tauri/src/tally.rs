use reqwest::Client;
use roxmltree::{Document, Node};

use crate::models::{Company, Entry, GstDetail, Ledger, Period, Probe, Snapshot, Voucher};

fn text(node: Node<'_, '_>, tag: &str) -> String {
    node.descendants()
        .find(|n| n.has_tag_name(tag))
        .and_then(|n| n.text())
        .unwrap_or("")
        .trim()
        .to_string()
}

pub(crate) fn escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

pub fn paise(value: &str) -> i64 {
    let clean = value.replace(',', "").trim().to_string();
    let debit = clean.ends_with("Dr");
    let credit = clean.ends_with("Cr");
    let number = clean.trim_end_matches("Dr").trim_end_matches("Cr").trim();
    let negative = number.starts_with('-') || credit;
    let absolute = number.trim_start_matches('-');
    let mut parts = absolute.split('.');
    let rupees = parts
        .next()
        .and_then(|v| v.parse::<i64>().ok())
        .unwrap_or(0);
    let raw = parts.next().unwrap_or("0");
    let fraction = match raw.len() {
        0 => 0,
        1 => raw.parse::<i64>().unwrap_or(0) * 10,
        _ => raw[..2].parse::<i64>().unwrap_or(0),
    };
    let amount = rupees * 100 + fraction;
    if negative && !debit {
        -amount
    } else {
        amount
    }
}

pub(crate) async fn post(port: u16, xml: String) -> Result<String, String> {
    let response = Client::builder()
        .timeout(std::time::Duration::from_secs(20))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|e| e.to_string())?
        .post(format!("http://127.0.0.1:{port}"))
        .header("Content-Type", "application/xml")
        .body(xml)
        .send()
        .await
        .map_err(|_| tally_unreachable())?;
    if matches!(response.status().as_u16(), 401 | 403) {
        return Err("TALLY_PERMISSION_DENIED: Tally refused the local request".into());
    }
    let response = response.error_for_status().map_err(|e| e.to_string())?;
    let bytes = response.bytes().await.map_err(|e| e.to_string())?;
    if bytes.len() > 64 * 1024 * 1024 {
        return Err("Tally response exceeds the 64 MB safety limit".into());
    }
    String::from_utf8(bytes.to_vec()).map_err(|_| "Tally response is not valid UTF-8".into())
}

pub(crate) fn export(report: &str, company: &str, dates: Option<(&str, &str)>) -> String {
    let range = dates
        .map(|(from, to)| format!("<SVFROMDATE>{from}</SVFROMDATE><SVTODATE>{to}</SVTODATE>"))
        .unwrap_or_default();
    let account_type = if report == "List of Accounts" {
        "<ACCOUNTTYPE>Ledgers</ACCOUNTTYPE>"
    } else {
        ""
    };
    format!("<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>{report}</REPORTNAME><STATICVARIABLES><SVCURRENTCOMPANY>{}</SVCURRENTCOMPANY>{range}{account_type}<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>", escape(company))
}

fn function_xml(id: &str, parameter: Option<&str>) -> String {
    let params = parameter
        .map(|value| format!("<FUNCPARAMLIST><PARAM>{value}</PARAM></FUNCPARAMLIST>"))
        .unwrap_or_default();
    format!("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>FUNCTION</TYPE><ID>{id}</ID></HEADER><BODY><DESC>{params}</DESC></BODY></ENVELOPE>")
}

async fn function(port: u16, id: &str, parameter: Option<&str>) -> String {
    let Ok(xml) = post(port, function_xml(id, parameter)).await else {
        return "Unknown".into();
    };
    let Ok(doc) = Document::parse(&xml) else {
        return "Unknown".into();
    };
    doc.descendants()
        .find(|n| n.has_tag_name("RESULT"))
        .and_then(|n| n.text())
        .unwrap_or("Unknown")
        .trim()
        .to_string()
}

pub async fn probe(port: u16) -> Result<Probe, String> {
    let xml = post(port, export("List of Companies", "", None)).await?;
    let doc = Document::parse(&xml).map_err(|_| "Tally returned invalid XML".to_string())?;
    let companies = doc
        .descendants()
        .filter(|n| n.has_tag_name("COMPANY"))
        .filter_map(|n| {
            let name = text(n, "NAME");
            if name.is_empty() {
                None
            } else {
                Some(Company {
                    name,
                    guid: text(n, "GUID"),
                })
            }
        })
        .collect();
    let version = function(port, "$$Version", None).await;
    let educational = function(port, "$$LicenseInfo", Some("IsEducationalMode")).await;
    let licensed = function(port, "$$LicenseInfo", Some("IsLicensedMode")).await;
    let license_mode = if educational.eq_ignore_ascii_case("yes") {
        "Educational"
    } else if licensed.eq_ignore_ascii_case("yes") {
        "Licensed"
    } else {
        "Unknown"
    };
    Ok(Probe {
        healthy: true,
        tally_version: version,
        license_mode: license_mode.into(),
        protocols: vec!["XML".into()],
        companies,
    })
}

pub async fn snapshot(port: u16, company: &Company, period: Period) -> Result<Snapshot, String> {
    let ledgers_xml = post(port, export("List of Accounts", &company.name, None)).await?;
    let vouchers_xml = post(
        port,
        export(
            "Voucher Register",
            &company.name,
            Some((&period.from_date, &period.to_date)),
        ),
    )
    .await?;
    Ok(Snapshot {
        company_guid: company.guid.clone(),
        period,
        completeness: "COMPLETE".into(),
        ledgers: parse_ledgers(&ledgers_xml)?,
        vouchers: parse_vouchers(&vouchers_xml)?,
    })
}

fn parse_ledgers(xml: &str) -> Result<Vec<Ledger>, String> {
    let doc = Document::parse(xml).map_err(|_| "Invalid ledger XML".to_string())?;
    Ok(doc
        .descendants()
        .filter(|n| n.has_tag_name("LEDGER"))
        .filter_map(|n| {
            let name = text(n, "NAME");
            if name.is_empty() {
                return None;
            }
            let parent = text(n, "PARENT");
            Some(Ledger {
                guid: text(n, "GUID"),
                name,
                parent_group: parent.clone(),
                opening_paise: paise(&text(n, "OPENINGBALANCE")),
                closing_paise: paise(&text(n, "CLOSINGBALANCE")),
                is_revenue: ["sales", "income", "purchase", "expense", "tax", "gst"]
                    .iter()
                    .any(|word| parent.to_lowercase().contains(word)),
                active: true,
                gstin: text(n, "PARTYGSTIN"),
                tax_type: text(n, "TAXTYPE"),
            })
        })
        .collect())
}

pub(crate) fn parse_vouchers(xml: &str) -> Result<Vec<Voucher>, String> {
    let doc = Document::parse(xml).map_err(|_| "Invalid voucher XML".to_string())?;
    Ok(doc
        .descendants()
        .filter(|n| n.has_tag_name("VOUCHER"))
        .map(|n| Voucher {
            status: if text(n, "ISCANCELLED").eq_ignore_ascii_case("yes") {
                "CANCELLED".into()
            } else if !text(n, "ALTERID").is_empty() {
                "ALTERED".into()
            } else {
                "ACTIVE".into()
            },
            guid: text(n, "GUID"),
            remote_id: n
                .attribute("REMOTEID")
                .map(str::to_string)
                .unwrap_or_else(|| text(n, "REMOTEID")),
            voucher_number: text(n, "VOUCHERNUMBER"),
            date: text(n, "DATE"),
            voucher_type: text(n, "VOUCHERTYPENAME"),
            party_name: text(n, "PARTYLEDGERNAME"),
            party_gstin: text(n, "PARTYGSTIN"),
            place_of_supply: text(n, "PLACEOFSUPPLY"),
            narration: text(n, "NARRATION"),
            reference: text(n, "REFERENCE"),
            altered: text(n, "ALTERID") != "",
            cancelled: text(n, "ISCANCELLED") == "Yes",
            master_id: text(n, "MASTERID"),
            alteration_id: text(n, "ALTERID"),
            gst_details: n
                .descendants()
                .filter(|e| e.has_tag_name("ALLLEDGERENTRIES.LIST"))
                .filter_map(|e| {
                    let tax_type = {
                        let duty = text(e, "GSTRATEDUTYHEAD");
                        if duty.is_empty() {
                            text(e, "TAXTYPE")
                        } else {
                            duty
                        }
                    };
                    (!tax_type.is_empty()).then(|| GstDetail {
                        ledger_name: text(e, "LEDGERNAME"),
                        amount_paise: paise(&text(e, "AMOUNT")),
                        tax_type,
                    })
                })
                .collect(),
            e_invoice: serde_json::json!({
                "irn": text(n, "IRN"), "ack_no": text(n, "ACKNO"),
                "ack_date": text(n, "ACKDATE"), "ewaybill_number": text(n, "EWAYBILLNO")
            }),
            entries: n
                .descendants()
                .filter(|e| e.has_tag_name("ALLLEDGERENTRIES.LIST"))
                .map(|e| Entry {
                    ledger_name: text(e, "LEDGERNAME"),
                    amount_paise: paise(&text(e, "AMOUNT")),
                })
                .collect(),
        })
        .collect())
}

fn tally_unreachable() -> String {
    #[cfg(target_os = "windows")]
    {
        let running = std::process::Command::new("tasklist")
            .output()
            .ok()
            .map(|o| {
                String::from_utf8_lossy(&o.stdout)
                    .to_ascii_lowercase()
                    .contains("tallyprime")
            })
            .unwrap_or(false);
        if running {
            return "TALLY_PORT_DISABLED: TallyPrime is open but its HTTP port is unavailable"
                .into();
        }
        return "TALLY_CLOSED: Open TallyPrime and retry".into();
    }
    #[cfg(not(target_os = "windows"))]
    "TALLY_UNREACHABLE: TallyPrime is closed or its HTTP port is disabled".into()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn amounts_use_paise() {
        assert_eq!(paise("1,234.50"), 123450);
        assert_eq!(paise("22.10 Cr"), -2210);
    }
}
