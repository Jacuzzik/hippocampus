mod sidecar;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
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
        .invoke_handler(tauri::generate_handler![sidecar::sidecar_call])
        .run(tauri::generate_context!())
        .expect("error while running Hippocampus");
}
