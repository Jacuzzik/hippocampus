mod sidecar;

use tauri::Manager;
use tauri_plugin_notification::NotificationExt;

/// Desktop alerts (M.20): one system notification. The window sends one only when the user has
/// turned alerts on in Settings and the window is not in front, so nothing shows by default.
#[tauri::command]
fn desktop_alert(app: tauri::AppHandle, title: String, body: String) -> Result<(), String> {
    let title: String = title.chars().take(120).collect();
    let body: String = body.chars().take(400).collect();
    app.notification()
        .builder()
        .title(title)
        .body(body)
        .show()
        .map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let ran = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            let sidecar = sidecar::Sidecar::new(app.handle().clone());
            app.manage(sidecar.clone());
            // Opening the vault can take a while, so it starts off the UI thread.
            std::thread::spawn(move || {
                if let Err(error) = sidecar.start() {
                    eprintln!("Hippocampus: {error}");
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar::sidecar_call, desktop_alert])
        .run(tauri::generate_context!());
    // No panic on a failed start: say what happened and leave with an error code.
    if let Err(error) = ran {
        eprintln!("Hippocampus could not start: {error}");
        std::process::exit(1);
    }
}
