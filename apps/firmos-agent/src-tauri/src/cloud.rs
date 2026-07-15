use std::time::{SystemTime, UNIX_EPOCH};

use base64::{engine::general_purpose::STANDARD, Engine};
use ed25519_dalek::{Signer, SigningKey};
use rand_core::OsRng;
use reqwest::{Client, Method, RequestBuilder, StatusCode};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::models::{Action, AgentConfig, PairInput, Probe, Snapshot};

fn base(url: &str) -> Result<String, String> {
    let value = url.trim().trim_end_matches('/');
    let parsed = reqwest::Url::parse(value).map_err(|_| "FirmOS address is invalid")?;
    let host = parsed.host_str().unwrap_or("");
    let local = parsed.scheme() == "http" && matches!(host, "127.0.0.1" | "localhost");
    if parsed.scheme() != "https" && !local {
        return Err("FirmOS address must use HTTPS".into());
    }
    if !parsed.username().is_empty()
        || parsed.password().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
        || !matches!(parsed.path(), "" | "/")
    {
        return Err("Use only the root FirmOS address without credentials or a path".into());
    }
    Ok(value.to_string())
}

fn key(device_id: &str) -> Result<keyring::Entry, String> {
    keyring::Entry::new("in.firmos.tally-agent.device-key", device_id).map_err(|e| e.to_string())
}

fn http() -> Result<Client, String> {
    Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|e| e.to_string())
}

pub async fn pair(input: PairInput, probe: &Probe) -> Result<AgentConfig, String> {
    let url = base(&input.cloud_url)?;
    let signing_key = SigningKey::generate(&mut OsRng);
    let payload = json!({
      "pairing_code": input.pairing_code, "device_name": input.device_name,
      "company_name": input.company_name, "company_guid": input.company_guid,
      "agent_version": env!("CARGO_PKG_VERSION"), "tally_version": probe.tally_version,
      "license_mode": probe.license_mode, "protocols": probe.protocols,
      "public_key": STANDARD.encode(signing_key.verifying_key().to_bytes()),
    });
    let response = http()?
        .post(format!("{url}/api/tally-agent/pair"))
        .json(&payload)
        .send()
        .await
        .map_err(|_| "FirmOS could not be reached".to_string())?;
    if !response.status().is_success() {
        return Err(response
            .text()
            .await
            .unwrap_or_else(|_| "Pairing failed".into()));
    }
    let body: Value = response.json().await.map_err(|e| e.to_string())?;
    let device_id = body["device_id"]
        .as_str()
        .ok_or("Pairing response had no device ID")?;
    let firm_id = body["firm_id"]
        .as_str()
        .ok_or("Pairing response had no firm ID")?;
    key(device_id)?
        .set_password(&STANDARD.encode(signing_key.to_bytes()))
        .map_err(|_| "Could not protect the device key".to_string())?;
    Ok(AgentConfig {
        cloud_url: url,
        device_id: device_id.into(),
        firm_id: firm_id.into(),
        device_name: input.device_name,
        company_name: input.company_name,
        company_guid: input.company_guid,
        port: input.port,
        write_enabled: false,
        last_read_at: 0,
        last_write_at: 0,
    })
}

fn signing_key(config: &AgentConfig) -> Result<SigningKey, String> {
    let encoded = key(&config.device_id)?
        .get_password()
        .map_err(|_| "Secure device key is unavailable".to_string())?;
    let bytes = STANDARD
        .decode(encoded)
        .map_err(|_| "Secure device key is invalid".to_string())?;
    let seed: [u8; 32] = bytes
        .try_into()
        .map_err(|_| "Secure device key is invalid".to_string())?;
    Ok(SigningKey::from_bytes(&seed))
}

fn signed(
    config: &AgentConfig,
    method: Method,
    path: &str,
    body: Vec<u8>,
) -> Result<RequestBuilder, String> {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_secs()
        .to_string();
    let nonce = uuid::Uuid::new_v4().to_string();
    let digest = format!("{:x}", Sha256::digest(&body));
    let message = format!(
        "{}\n{}\n{}\n{}\n{}",
        method.as_str(),
        path,
        timestamp,
        nonce,
        digest
    );
    let signature = STANDARD.encode(signing_key(config)?.sign(message.as_bytes()).to_bytes());
    Ok(http()?
        .request(method, format!("{}{}", config.cloud_url, path))
        .header("Content-Type", "application/json")
        .header("X-FirmOS-Device", &config.device_id)
        .header("X-FirmOS-Firm", &config.firm_id)
        .header("X-FirmOS-Timestamp", timestamp)
        .header("X-FirmOS-Nonce", nonce)
        .header("X-FirmOS-Body-SHA256", digest)
        .header("X-FirmOS-Signature", signature)
        .body(body))
}

async fn post(
    config: &AgentConfig,
    path: &str,
    value: &Value,
) -> Result<reqwest::Response, String> {
    let body = serde_json::to_vec(value).map_err(|e| e.to_string())?;
    signed(config, Method::POST, path, body)?
        .send()
        .await
        .map_err(|e| e.to_string())
}

pub async fn heartbeat(
    config: &AgentConfig,
    probe: &Probe,
    queue_depth: u32,
) -> Result<(), String> {
    let response = post(
        config,
        "/api/tally-agent/heartbeat",
        &json!({
          "agent_version": env!("CARGO_PKG_VERSION"), "tally_version": probe.tally_version,
          "license_mode": probe.license_mode, "protocols": probe.protocols,
          "local_queue_depth": queue_depth,
          "last_read_at": if config.last_read_at == 0 {None} else {Some(config.last_read_at)},
          "last_write_at": if config.last_write_at == 0 {None} else {Some(config.last_write_at)},
        }),
    )
    .await?;
    if response.status().is_success() {
        Ok(())
    } else {
        Err(response.text().await.unwrap_or_default())
    }
}

pub fn batch_key(config: &AgentConfig, snapshot: &Snapshot) -> Result<String, String> {
    let payload = serde_json::to_vec(snapshot).map_err(|e| e.to_string())?;
    let payload_hash = format!("{:x}", Sha256::digest(payload));
    let identity = format!(
        "{}:{}:vouchers:{}:{}:{}",
        config.device_id,
        config.company_guid,
        snapshot.period.from_date,
        snapshot.period.to_date,
        payload_hash
    );
    Ok(format!("{:x}", Sha256::digest(identity.as_bytes())))
}

pub async fn push(
    config: &AgentConfig,
    snapshot: &Snapshot,
    idempotency_key: &str,
) -> Result<Value, String> {
    let body = serde_json::to_vec(snapshot).map_err(|e| e.to_string())?;
    let response = signed(config, Method::POST, "/api/tally-agent/snapshot", body)?
        .header("X-Idempotency-Key", idempotency_key)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    if response.status().is_success() {
        response.json().await.map_err(|e| e.to_string())
    } else {
        Err(response.text().await.unwrap_or_default())
    }
}

pub async fn claim(config: &AgentConfig) -> Result<Option<Action>, String> {
    let response = post(config, "/api/tally-agent/actions/claim", &json!({})).await?;
    if response.status() == StatusCode::NO_CONTENT {
        return Ok(None);
    }
    if !response.status().is_success() {
        return Err(response.text().await.unwrap_or_default());
    }
    response.json().await.map(Some).map_err(|e| e.to_string())
}

pub async fn renew(config: &AgentConfig, action_id: &str) -> Result<(), String> {
    let response = post(
        config,
        &format!("/api/tally-agent/actions/{action_id}/lease"),
        &json!({}),
    )
    .await?;
    if response.status().is_success() {
        Ok(())
    } else {
        Err(response.text().await.unwrap_or_default())
    }
}

pub async fn report(config: &AgentConfig, action_id: &str, result: &Value) -> Result<(), String> {
    let response = post(
        config,
        &format!("/api/tally-agent/actions/{action_id}/result"),
        result,
    )
    .await?;
    if response.status().is_success() {
        Ok(())
    } else {
        Err(response.text().await.unwrap_or_default())
    }
}

pub async fn set_write_access(config: &AgentConfig, enabled: bool) -> Result<(), String> {
    let response = post(
        config,
        "/api/tally-agent/write-access",
        &json!({"enabled": enabled}),
    )
    .await?;
    if response.status().is_success() {
        Ok(())
    } else {
        Err(response.text().await.unwrap_or_default())
    }
}

pub async fn disconnect(config: &AgentConfig) -> Result<(), String> {
    let response = post(config, "/api/tally-agent/disconnect", &json!({})).await?;
    if !response.status().is_success() && response.status() != StatusCode::UNAUTHORIZED {
        return Err(response.text().await.unwrap_or_default());
    }
    key(&config.device_id)?
        .delete_credential()
        .map_err(|e| e.to_string())
}
