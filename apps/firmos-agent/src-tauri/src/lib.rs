mod cloud;
mod diagnostics;
mod models;
mod state;
mod tally;
mod tally_write;

use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{fs, path::PathBuf, time::Duration};
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager, WindowEvent,
};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};

use models::{Action, AgentConfig, AgentStatus, Company, PairInput, Period, Probe};

fn database(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.join("agent.db"))
}

fn load(app: &AppHandle) -> Result<Option<AgentConfig>, String> {
    state::load_config(&database(app)?)
}

fn now_epoch() -> Result<u64, String> {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|value| value.as_secs())
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn probe_tally(port: u16) -> Result<Probe, String> {
    tally::probe(port).await
}

#[tauri::command]
async fn pair_agent(app: AppHandle, input: PairInput) -> Result<AgentStatus, String> {
    let probe = tally::probe(input.port).await?;
    let found = probe
        .companies
        .iter()
        .any(|c| c.guid == input.company_guid && !c.guid.is_empty());
    if !found {
        return Err("The selected company GUID is no longer open in TallyPrime".into());
    }
    let config = cloud::pair(input, &probe).await?;
    state::save_config(&database(&app)?, &config)?;
    Ok(AgentStatus {
        paired: true,
        config: Some(config),
        tally: Some(probe),
    })
}

#[tauri::command]
async fn get_status(app: AppHandle) -> Result<AgentStatus, String> {
    let config = load(&app)?;
    let tally = match &config {
        Some(value) => tally::probe(value.port).await.ok(),
        None => None,
    };
    Ok(AgentStatus {
        paired: config.is_some(),
        config,
        tally,
    })
}

#[tauri::command]
async fn sync_now(app: AppHandle, period: Period) -> Result<Value, String> {
    let mut config = load(&app)?.ok_or("Pair this computer first")?;
    let probe = tally::probe(config.port).await?;
    let db = database(&app)?;
    cloud::heartbeat(&config, &probe, state::queue_depth(&db)?).await?;
    let company = Company {
        name: config.company_name.clone(),
        guid: config.company_guid.clone(),
    };
    let snapshot = tally::snapshot(config.port, &company, period).await?;
    let key = cloud::batch_key(&config, &snapshot)?;
    let payload = serde_json::to_vec(&snapshot).map_err(|e| e.to_string())?;
    state::record_batch(&db, &key, &format!("{:x}", Sha256::digest(payload)))?;
    let result = cloud::push(&config, &snapshot, &key).await?;
    state::finish_batch(&db, &key)?;
    config.last_read_at = now_epoch()?;
    state::save_config(&db, &config)?;
    Ok(result)
}

async fn process_pending(
    app: &AppHandle,
    config: &AgentConfig,
    action: Action,
) -> Result<(), String> {
    let db = database(app)?;
    cloud::renew(config, &action.action_id).await?;
    let result = match state::pending_result(&db, &action.action_id)? {
        Some(value) => value,
        None => {
            let payload = serde_json::to_vec(&action.payload).map_err(|e| e.to_string())?;
            let is_sales = action.operation == "tally.write.sales_voucher.create";
            let xml = if is_sales {
                tally_write::sales_xml(&action.payload, &action.remote_id)?
            } else {
                tally_write::purchase_xml(&action.payload, &action.remote_id)?
            };
            state::save_execution_identity(
                &db,
                &action.action_id,
                &format!("{:x}", Sha256::digest(payload)),
                &format!("{:x}", Sha256::digest(xml.as_bytes())),
                &action.remote_id,
            )?;
            let voucher = if is_sales {
                tally_write::create_sales(config.port, &action.payload, &action.remote_id).await
            } else {
                tally_write::create_purchase(config.port, &action.payload, &action.remote_id).await
            };
            let value = tally_write::action_result(voucher, &config.company_guid);
            state::save_result(&db, &action.action_id, &value)?;
            value
        }
    };
    cloud::report(config, &action.action_id, &result).await?;
    state::complete_action(&db, &action.action_id)?;
    if result["status"] == "PROVIDER_ACCEPTED" {
        let mut updated = config.clone();
        updated.last_write_at = now_epoch()?;
        state::save_config(&db, &updated)?;
    }
    Ok(())
}

#[tauri::command]
async fn poll_now(app: AppHandle) -> Result<bool, String> {
    let config = load(&app)?.ok_or("Pair this computer first")?;
    let db = database(&app)?;
    if let Some(action) = state::pending_claim(&db)? {
        process_pending(&app, &config, action).await?;
        return Ok(true);
    }
    let Some(action) = cloud::claim(&config).await? else {
        return Ok(false);
    };
    state::save_claim(&db, &action)?;
    process_pending(&app, &config, action).await?;
    Ok(true)
}

#[tauri::command]
async fn set_write_enabled(app: AppHandle, enabled: bool) -> Result<AgentStatus, String> {
    let mut config = load(&app)?.ok_or("Pair this computer first")?;
    cloud::set_write_access(&config, enabled).await?;
    config.write_enabled = enabled;
    state::save_config(&database(&app)?, &config)?;
    get_status(app).await
}

#[tauri::command]
async fn disconnect(app: AppHandle) -> Result<(), String> {
    if let Some(config) = load(&app)? {
        cloud::disconnect(&config).await?;
    }
    state::delete_config(&database(&app)?)
}

#[tauri::command]
async fn create_diagnostics(app: AppHandle) -> Result<String, String> {
    diagnostics::create(&app).await
}

async fn background(app: AppHandle) {
    loop {
        if let Ok(Some(config)) = load(&app) {
            if let Ok(probe) = tally::probe(config.port).await {
                let depth = database(&app)
                    .and_then(|p| state::queue_depth(&p))
                    .unwrap_or(0);
                let _ = cloud::heartbeat(&config, &probe, depth).await;
                let _ = poll_now(app.clone()).await;
            }
        }
        tokio::time::sleep(Duration::from_secs(60)).await;
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            app.handle().plugin(tauri_plugin_autostart::init(
                MacosLauncher::LaunchAgent,
                Some(vec!["--background"]),
            ))?;
            let _ = app.autolaunch().enable();
            let show =
                MenuItem::with_id(app, "show", "Open FirmOS Tally Agent", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            TrayIconBuilder::new()
                .icon(
                    app.default_window_icon()
                        .ok_or("Missing application icon")?
                        .clone(),
                )
                .tooltip("FirmOS Tally Agent")
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;
            tauri::async_runtime::spawn(background(app.handle().clone()));
            app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    .level(log::LevelFilter::Info)
                    .max_file_size(5_000_000)
                    .build(),
            )?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            probe_tally,
            pair_agent,
            get_status,
            sync_now,
            poll_now,
            set_write_enabled,
            create_diagnostics,
            disconnect
        ])
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("FirmOS Tally Agent failed to start");
}
