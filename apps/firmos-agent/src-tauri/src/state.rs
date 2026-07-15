use std::path::Path;

use rusqlite::{params, Connection, OptionalExtension};
use serde_json::Value;

use crate::models::{Action, AgentConfig};

fn open(path: &Path) -> Result<Connection, String> {
    let conn = Connection::open(path).map_err(|e| e.to_string())?;
    conn.execute_batch(
        "PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;
         CREATE TABLE IF NOT EXISTS configuration(key TEXT PRIMARY KEY,value TEXT NOT NULL);
         CREATE TABLE IF NOT EXISTS company_mappings(company_guid TEXT PRIMARY KEY,company_name TEXT NOT NULL,device_id TEXT NOT NULL);
         CREATE TABLE IF NOT EXISTS sync_batches(batch_key TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,uploaded_at TEXT);
         CREATE TABLE IF NOT EXISTS claimed_actions(action_id TEXT PRIMARY KEY,action_json TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
         CREATE TABLE IF NOT EXISTS action_attempts(id INTEGER PRIMARY KEY,action_id TEXT NOT NULL,state TEXT NOT NULL,error_code TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
         CREATE TABLE IF NOT EXISTS action_payloads(action_id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,xml_hash TEXT NOT NULL,remote_id TEXT NOT NULL);
         CREATE TABLE IF NOT EXISTS unsent_results(action_id TEXT PRIMARY KEY,result_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
         CREATE TABLE IF NOT EXISTS cursor_state(scope TEXT PRIMARY KEY,cursor TEXT NOT NULL,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);",
    ).map_err(|e| e.to_string())?;
    Ok(conn)
}

pub fn load_config(path: &Path) -> Result<Option<AgentConfig>, String> {
    let value: Option<String> = open(path)?
        .query_row(
            "SELECT value FROM configuration WHERE key='agent'",
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    value
        .map(|v| serde_json::from_str(&v).map_err(|e| e.to_string()))
        .transpose()
}

pub fn save_config(path: &Path, config: &AgentConfig) -> Result<(), String> {
    let conn = open(path)?;
    conn.execute(
        "INSERT INTO configuration(key,value) VALUES('agent',?1) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        [serde_json::to_string(config).map_err(|e| e.to_string())?],
    ).map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT INTO company_mappings(company_guid,company_name,device_id) VALUES(?1,?2,?3)
         ON CONFLICT(company_guid) DO UPDATE SET company_name=excluded.company_name,device_id=excluded.device_id",
        params![config.company_guid, config.company_name, config.device_id],
    ).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn delete_config(path: &Path) -> Result<(), String> {
    open(path)?
        .execute_batch("DELETE FROM configuration; DELETE FROM company_mappings;")
        .map_err(|e| e.to_string())
}

pub fn record_batch(path: &Path, key: &str, payload_hash: &str) -> Result<(), String> {
    open(path)?.execute(
        "INSERT OR IGNORE INTO sync_batches(batch_key,payload_hash,status) VALUES(?1,?2,'PENDING')",
        params![key, payload_hash],
    ).map(|_| ()).map_err(|e| e.to_string())
}

pub fn finish_batch(path: &Path, key: &str) -> Result<(), String> {
    open(path)?.execute(
        "UPDATE sync_batches SET status='UPLOADED',uploaded_at=CURRENT_TIMESTAMP WHERE batch_key=?1", [key],
    ).map(|_| ()).map_err(|e| e.to_string())
}

pub fn save_claim(path: &Path, action: &Action) -> Result<(), String> {
    let value = serde_json::to_string(action).map_err(|e| e.to_string())?;
    let conn = open(path)?;
    conn.execute(
        "INSERT OR IGNORE INTO claimed_actions(action_id,action_json,state) VALUES(?1,?2,'CLAIMED')",
        params![action.action_id, value],
    ).map_err(|e| e.to_string())?;
    attempt(&conn, &action.action_id, "CLAIMED", "")
}

pub fn pending_claim(path: &Path) -> Result<Option<Action>, String> {
    let value: Option<String> = open(path)?
        .query_row(
            "SELECT action_json FROM claimed_actions ORDER BY created_at LIMIT 1",
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    value
        .map(|v| serde_json::from_str(&v).map_err(|e| e.to_string()))
        .transpose()
}

pub fn save_result(path: &Path, action_id: &str, result: &Value) -> Result<(), String> {
    let conn = open(path)?;
    conn.execute(
        "INSERT INTO unsent_results(action_id,result_json) VALUES(?1,?2)
         ON CONFLICT(action_id) DO UPDATE SET result_json=excluded.result_json",
        params![action_id, result.to_string()],
    )
    .map_err(|e| e.to_string())?;
    attempt(&conn, action_id, "EXECUTED", "")
}

pub fn save_execution_identity(
    path: &Path,
    action_id: &str,
    payload_hash: &str,
    xml_hash: &str,
    remote_id: &str,
) -> Result<(), String> {
    open(path)?.execute(
        "INSERT OR IGNORE INTO action_payloads(action_id,payload_hash,xml_hash,remote_id) VALUES(?1,?2,?3,?4)",
        params![action_id, payload_hash, xml_hash, remote_id],
    ).map(|_| ()).map_err(|e| e.to_string())
}

pub fn pending_result(path: &Path, action_id: &str) -> Result<Option<Value>, String> {
    let value: Option<String> = open(path)?
        .query_row(
            "SELECT result_json FROM unsent_results WHERE action_id=?1",
            [action_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    value
        .map(|v| serde_json::from_str(&v).map_err(|e| e.to_string()))
        .transpose()
}

pub fn complete_action(path: &Path, action_id: &str) -> Result<(), String> {
    let mut conn = open(path)?;
    let tx = conn.transaction().map_err(|e| e.to_string())?;
    attempt(&tx, action_id, "REPORTED", "")?;
    tx.execute("DELETE FROM unsent_results WHERE action_id=?1", [action_id])
        .map_err(|e| e.to_string())?;
    tx.execute(
        "DELETE FROM claimed_actions WHERE action_id=?1",
        [action_id],
    )
    .map_err(|e| e.to_string())?;
    tx.execute(
        "DELETE FROM action_payloads WHERE action_id=?1",
        [action_id],
    )
    .map_err(|e| e.to_string())?;
    tx.commit().map_err(|e| e.to_string())
}

pub fn queue_depth(path: &Path) -> Result<u32, String> {
    open(path)?
        .query_row("SELECT count(*) FROM claimed_actions", [], |row| row.get(0))
        .map_err(|e| e.to_string())
}

pub fn diagnostic_counts(path: &Path) -> Result<Value, String> {
    let conn = open(path)?;
    let count = |sql| {
        conn.query_row(sql, [], |row| row.get::<_, i64>(0))
            .map_err(|e| e.to_string())
    };
    let mut errors = conn.prepare(
        "SELECT DISTINCT error_code FROM action_attempts WHERE error_code IS NOT NULL ORDER BY id DESC LIMIT 10",
    ).map_err(|e| e.to_string())?;
    let error_codes = errors
        .query_map([], |row| row.get::<_, String>(0))
        .map_err(|e| e.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;
    Ok(serde_json::json!({
        "pending_sync_batches": count("SELECT count(*) FROM sync_batches WHERE status!='UPLOADED'")?,
        "claimed_actions": count("SELECT count(*) FROM claimed_actions")?,
        "unsent_results": count("SELECT count(*) FROM unsent_results")?,
        "action_attempts": count("SELECT count(*) FROM action_attempts")?,
        "recent_error_codes": error_codes,
    }))
}

fn attempt(conn: &Connection, action_id: &str, state: &str, error: &str) -> Result<(), String> {
    conn.execute(
        "INSERT INTO action_attempts(action_id,state,error_code) VALUES(?1,?2,NULLIF(?3,''))",
        params![action_id, state, error],
    )
    .map(|_| ())
    .map_err(|e| e.to_string())
}
