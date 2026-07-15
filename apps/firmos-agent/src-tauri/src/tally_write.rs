use roxmltree::Document;
use serde_json::{json, Value};

use crate::models::{Company, Voucher};
use crate::tally::{escape, export, parse_vouchers, post};

pub fn purchase_xml(payload: &serde_json::Value, remote_id: &str) -> Result<String, String> {
    voucher_xml(payload, remote_id, "Purchase", "purchase_ledger")
}

pub fn sales_xml(payload: &serde_json::Value, remote_id: &str) -> Result<String, String> {
    voucher_xml(payload, remote_id, "Sales", "sales_ledger")
}

fn voucher_xml(
    payload: &serde_json::Value,
    remote_id: &str,
    voucher_type: &str,
    ledger_key: &str,
) -> Result<String, String> {
    let get = |key| payload.get(key).and_then(|v| v.as_str()).unwrap_or("");
    let total = payload
        .get("total_paise")
        .and_then(|v| v.as_i64())
        .unwrap_or(0);
    if total <= 0 || get("party_ledger").is_empty() || get(ledger_key).is_empty() {
        return Err(format!("Invalid {} payload", voucher_type.to_lowercase()));
    }
    let amount = format!("{}.{:02}", total / 100, total % 100);
    let entries = payload.get("entries").and_then(|v| v.as_array()).map(|lines| lines.iter().map(|line| {
        let ledger = escape(line.get("ledger_name").and_then(|v| v.as_str()).unwrap_or(""));
        let paise = line.get("amount_paise").and_then(|v| v.as_i64()).unwrap_or(0);
        let value = format!("{}{}.{:02}", if paise < 0 {"-"} else {""}, paise.abs() / 100, paise.abs() % 100);
        format!("<ALLLEDGERENTRIES.LIST><LEDGERNAME>{ledger}</LEDGERNAME><ISDEEMEDPOSITIVE>{}</ISDEEMEDPOSITIVE><AMOUNT>{value}</AMOUNT></ALLLEDGERENTRIES.LIST>", if paise < 0 {"Yes"} else {"No"})
    }).collect::<String>()).unwrap_or_else(|| format!("<ALLLEDGERENTRIES.LIST><LEDGERNAME>{}</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{amount}</AMOUNT></ALLLEDGERENTRIES.LIST><ALLLEDGERENTRIES.LIST><LEDGERNAME>{}</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-{amount}</AMOUNT></ALLLEDGERENTRIES.LIST>", escape(get("party_ledger")), escape(get(ledger_key))));
    Ok(format!("<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES><SVCURRENTCOMPANY>{}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC><REQUESTDATA><TALLYMESSAGE><VOUCHER VCHTYPE=\"{}\" ACTION=\"Create\" REMOTEID=\"{}\"><DATE>{}</DATE><VOUCHERTYPENAME>{}</VOUCHERTYPENAME><PARTYLEDGERNAME>{}</PARTYLEDGERNAME><REFERENCE>{}</REFERENCE><NARRATION>{}</NARRATION>{entries}</VOUCHER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>", escape(get("company_name")), voucher_type, escape(remote_id), escape(get("date")), voucher_type, escape(get("party_ledger")), escape(get("reference")), escape(get("narration"))))
}

#[derive(Debug, PartialEq, Eq)]
struct ImportResult {
    status: String,
    created: i64,
    altered: i64,
    combined: i64,
    ignored: i64,
    errors: i64,
    last_voucher_id: String,
    last_master_id: String,
    line_errors: Vec<String>,
}

fn parse_import_result(xml: &str) -> Result<ImportResult, String> {
    let doc = Document::parse(xml).map_err(|_| "TALLY_IMPORT_AMBIGUOUS".to_string())?;
    let count = |tag| {
        doc.descendants()
            .filter(|n| n.has_tag_name(tag))
            .filter_map(|n| n.text()?.trim().parse::<i64>().ok())
            .sum::<i64>()
    };
    let line_errors = doc
        .descendants()
        .filter(|n| n.has_tag_name("LINEERROR"))
        .filter_map(|n| n.text().map(str::to_owned))
        .collect::<Vec<_>>();
    Ok(ImportResult {
        status: doc
            .descendants()
            .find(|n| n.has_tag_name("STATUS"))
            .and_then(|n| n.text())
            .unwrap_or("")
            .trim()
            .to_string(),
        created: count("CREATED"),
        altered: count("ALTERED"),
        combined: count("COMBINED"),
        ignored: count("IGNORED"),
        errors: count("ERRORS"),
        last_voucher_id: doc
            .descendants()
            .find(|n| n.has_tag_name("LASTVCHID"))
            .and_then(|n| n.text())
            .unwrap_or("")
            .trim()
            .to_string(),
        last_master_id: doc
            .descendants()
            .find(|n| n.has_tag_name("LASTMID"))
            .and_then(|n| n.text())
            .unwrap_or("")
            .trim()
            .to_string(),
        line_errors,
    })
}

fn require_created(result: &ImportResult) -> Result<(), String> {
    if result.errors > 0 || result.ignored > 0 || !result.line_errors.is_empty() {
        return Err(format!(
            "TALLY_IMPORT_ERROR: {} line error(s)",
            result.line_errors.len()
        ));
    }
    if result.created == 1 && result.altered == 0 && result.combined == 0 {
        return Ok(());
    }
    Err("TALLY_IMPORT_AMBIGUOUS".into())
}

pub fn action_result(voucher: Result<Voucher, String>, company_guid: &str) -> Value {
    match voucher {
        Ok(v) => {
            let guid = v.guid.clone();
            let total = v
                .entries
                .iter()
                .map(|entry| entry.amount_paise.abs())
                .max()
                .unwrap_or(0);
            json!({"status":"PROVIDER_ACCEPTED","provider_guid":guid,"error_code":"",
              "readback":{"guid":v.guid,"remote_id":v.remote_id,"voucher_number":v.voucher_number,
              "date":v.date,"voucher_type":v.voucher_type,"party_ledger":v.party_name,
              "entries":v.entries,"gst_details":v.gst_details,"total_paise":total,
              "company_guid":company_guid,"reference":v.reference,"narration":v.narration,
              "master_id":v.master_id,"alteration_id":v.alteration_id,"provider_status":v.status}})
        }
        Err(error) => {
            let definite = error.starts_with("TALLY_IMPORT_ERROR")
                || error.starts_with("Invalid purchase payload")
                || error.starts_with("TALLY_PERMISSION_DENIED");
            json!({"status":if definite {"FAILED"} else {"AMBIGUOUS"},"provider_guid":"",
              "error_code":if definite {"TALLY_WRITE_REJECTED"} else {"TALLY_WRITE_UNVERIFIED"},
              "readback":null})
        }
    }
}

pub async fn create_purchase(
    port: u16,
    payload: &serde_json::Value,
    remote_id: &str,
) -> Result<Voucher, String> {
    create_voucher(port, payload, remote_id, false).await
}

pub async fn create_sales(
    port: u16,
    payload: &serde_json::Value,
    remote_id: &str,
) -> Result<Voucher, String> {
    create_voucher(port, payload, remote_id, true).await
}

async fn create_voucher(
    port: u16,
    payload: &serde_json::Value,
    remote_id: &str,
    sales: bool,
) -> Result<Voucher, String> {
    let date = payload["date"].as_str().unwrap_or("").to_string();
    let company = Company {
        name: payload["company_name"].as_str().unwrap_or("").into(),
        guid: payload["company_guid"].as_str().unwrap_or("").into(),
    };
    let find = |xml: &str| {
        parse_vouchers(xml).map(|items| items.into_iter().find(|v| v.remote_id == remote_id))
    };
    let prior = post(
        port,
        export("Voucher Register", &company.name, Some((&date, &date))),
    )
    .await?;
    if let Some(voucher) = find(&prior)? {
        return Ok(voucher);
    }
    let response = post(
        port,
        if sales {
            sales_xml(payload, remote_id)?
        } else {
            purchase_xml(payload, remote_id)?
        },
    )
    .await?;
    require_created(&parse_import_result(&response)?)?;
    let after = post(
        port,
        export("Voucher Register", &company.name, Some((&date, &date))),
    )
    .await?;
    find(&after)?.ok_or_else(|| "TALLY_READBACK_NOT_FOUND".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn purchase_is_scoped_and_import_is_strict() {
        let payload = serde_json::json!({"company_name":"A","date":"20260715","party_ledger":"V","purchase_ledger":"P","total_paise":123});
        let xml = purchase_xml(&payload, "firmos:1").unwrap();
        assert!(xml.contains("REMOTEID=\"firmos:1\""));
        let result = parse_import_result("<R><STATUS>1</STATUS><CREATED>1</CREATED><ERRORS>0</ERRORS><LASTVCHID>7</LASTVCHID><LASTMID>9</LASTMID></R>").unwrap();
        assert_eq!(result.last_voucher_id, "7");
        assert_eq!(result.last_master_id, "9");
        assert!(require_created(&result).is_ok());
        assert!(
            require_created(&parse_import_result("<R><IGNORED>1</IGNORED></R>").unwrap()).is_err()
        );
    }
    #[test]
    fn sales_is_separately_typed_and_scoped() {
        let payload = serde_json::json!({"company_name":"A","date":"20260715","party_ledger":"C","sales_ledger":"S","total_paise":123});
        let xml = sales_xml(&payload, "firmos:sale:1").unwrap();
        assert!(xml.contains("VCHTYPE=\"Sales\""));
        assert!(xml.contains("REMOTEID=\"firmos:sale:1\""));
    }
}
