// D1: static shell only. No commands, no plugins, no sidecar launch yet.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running Hippocampus");
}
