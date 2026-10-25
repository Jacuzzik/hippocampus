mod sidecar;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let sidecar = sidecar::Sidecar::default();
    let started = sidecar.clone();
    tauri::Builder::default()
        .manage(sidecar)
        .setup(move |_app| {
            let vault = sidecar::default_vault(&sidecar::project_root());
            // Blocks until the sidecar is ready; a failure is logged and the UI shows it.
            if let Err(error) = started.start(&vault) {
                eprintln!("Hippocampus: {error}");
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar::sidecar_call])
        .run(tauri::generate_context!())
        .expect("error while running Hippocampus");
}
