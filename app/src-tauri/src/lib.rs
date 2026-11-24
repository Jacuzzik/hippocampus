mod sidecar;

use tauri::{Emitter, Manager};
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

/// Whether Ctrl+Shift+Space was taken for the whole system, so the window can say where it works.
struct GlobalCapture(bool);

#[tauri::command]
fn capture_global(state: tauri::State<'_, GlobalCapture>) -> bool {
    state.0
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let ran = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            // Quick capture (N.17): Ctrl+Shift+Space anywhere brings the window up with the capture box.
            // Some desktops (most Wayland ones) do not let an app take a key for the whole system; then the
            // same key still works while the window is in front, and the window says so.
            {
                use tauri_plugin_global_shortcut::{Code, Modifiers, Shortcut, ShortcutState};
                let key = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space);
                let plugin = tauri_plugin_global_shortcut::Builder::new()
                    .with_handler(move |app, shortcut, event| {
                        if shortcut == &key && event.state() == ShortcutState::Pressed {
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.unminimize();
                                let _ = window.set_focus();
                            }
                            let _ = app.emit("quick-capture", ());
                        }
                    })
                    .build();
                if app.handle().plugin(plugin).is_ok() {
                    use tauri_plugin_global_shortcut::GlobalShortcutExt;
                    let taken = app.global_shortcut().register(key).is_ok();
                    app.manage(GlobalCapture(taken));
                } else {
                    app.manage(GlobalCapture(false));
                }
            }
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
        .invoke_handler(tauri::generate_handler![sidecar::sidecar_call, desktop_alert, capture_global])
        .run(tauri::generate_context!());
    // No panic on a failed start: say what happened and leave with an error code.
    if let Err(error) = ran {
        eprintln!("Hippocampus could not start: {error}");
        std::process::exit(1);
    }
}
