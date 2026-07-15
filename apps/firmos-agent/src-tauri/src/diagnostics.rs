use std::fs;

use serde_json::json;
use tauri::{AppHandle, Manager};

use crate::{database, load, state, tally};

fn safe_log(input: &str) -> String {
    const SENSITIVE: [&str; 9] = [
        "authorization",
        "private_key",
        "token",
        "payload",
        "<envelope",
        "gstin",
        "amount",
        "ledger",
        "voucher",
    ];
    input
        .lines()
        .map(|line| {
            let lower = line.to_ascii_lowercase();
            if SENSITIVE.iter().any(|word| lower.contains(word)) {
                "[REDACTED]\n".to_string()
            } else {
                format!("{line}\n")
            }
        })
        .collect()
}

pub async fn create(app: &AppHandle) -> Result<String, String> {
    let config = load(app)?;
    let probe_result = match &config {
        Some(value) => Some(tally::probe(value.port).await),
        None => None,
    };
    let probe = probe_result
        .as_ref()
        .and_then(|result| result.as_ref().ok());
    let error_code = probe_result
        .as_ref()
        .and_then(|result| result.as_ref().err())
        .map(|error| error.split(':').next().unwrap_or("TALLY_PROBE_FAILED"));
    let payload = json!({
        "agent_version": env!("CARGO_PKG_VERSION"),
        "paired": config.is_some(),
        "tally_version": probe.map(|value| &value.tally_version),
        "license_mode": probe.map(|value| &value.license_mode),
        "protocols": probe.map(|value| &value.protocols),
        "open_company_count": probe.map(|value| value.companies.len()).unwrap_or(0),
        "probe_error_code": error_code,
        "write_enabled": config.as_ref().map(|value| value.write_enabled).unwrap_or(false),
        "queue": state::diagnostic_counts(&database(app)?)?,
        "checks": {
            "secure_key_storage": "OS credential manager",
            "durable_state": "SQLite WAL",
            "company_guid_present": config.as_ref().map(|value| !value.company_guid.is_empty()).unwrap_or(false),
            "cloud_url_https": config.as_ref().map(|value| value.cloud_url.starts_with("https://")).unwrap_or(false),
        },
    });
    let root = app.path().app_log_dir().map_err(|e| e.to_string())?;
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_secs();
    let package = root.join(format!("firmos-diagnostics-{stamp}"));
    fs::create_dir_all(&package).map_err(|e| e.to_string())?;
    fs::write(
        package.join("diagnostics.json"),
        serde_json::to_vec_pretty(&payload).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    let mut logs = String::new();
    if let Ok(entries) = fs::read_dir(&root) {
        for entry in entries.flatten().take(10) {
            let path = entry.path();
            if path.extension().and_then(|value| value.to_str()) == Some("log") {
                if let Ok(content) = fs::read_to_string(path) {
                    logs.push_str(&safe_log(&content));
                }
            }
        }
    }
    fs::write(package.join("support.log"), logs).map_err(|e| e.to_string())?;
    Ok(package.to_string_lossy().into_owned())
}

#[cfg(test)]
mod tests {
    use super::safe_log;

    #[test]
    fn support_logs_remove_financial_and_secret_lines() {
        let safe = safe_log("agent started\nAuthorization: secret\nledger Acme 100.00");
        assert!(safe.contains("agent started"));
        assert!(!safe.contains("secret"));
        assert!(!safe.contains("Acme"));
    }
}
