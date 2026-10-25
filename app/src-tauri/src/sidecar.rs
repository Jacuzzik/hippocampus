//! The Python sidecar: `python -m core serve <vault>`. One JSON request per line on its
//! stdin, one answer per line on its stdout. Localhost-free: no port, no token.

use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::{Arc, Mutex};

use serde_json::{json, Map, Value};
use tauri::State;

struct Link {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    next_id: u64,
}

impl Drop for Link {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// The running sidecar, shared by the Tauri commands. Requests run one at a time.
#[derive(Clone, Default)]
pub struct Sidecar(Arc<Mutex<Option<Link>>>);

impl Sidecar {
    /// Start the sidecar on `vault` and wait for its ready line.
    pub fn start(&self, vault: &Path) -> Result<(), String> {
        let root = project_root();
        let python = python_for(&root);
        let mut child = Command::new(&python)
            .args(["-m", "core", "serve"])
            .arg(vault)
            .current_dir(&root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .map_err(|e| format!("could not start {}: {e}", python.display()))?;
        let stdin = child.stdin.take().ok_or("sidecar has no stdin")?;
        let mut stdout = BufReader::new(child.stdout.take().ok_or("sidecar has no stdout")?);
        let mut ready = String::new();
        let read = stdout.read_line(&mut ready).map_err(|e| e.to_string())?;
        let status = serde_json::from_str::<Value>(&ready).ok();
        if read == 0 || status.as_ref().and_then(|s| s["status"].as_str()) != Some("ready") {
            let _ = child.kill();
            let _ = child.wait();
            return Err(format!("the sidecar did not start for {}", vault.display()));
        }
        let link = Link {
            child,
            stdin,
            stdout,
            next_id: 0,
        };
        *self.0.lock().map_err(|_| "sidecar lock poisoned")? = Some(link);
        Ok(())
    }

    /// Send one request and return its `result`, or the sidecar's `error` message.
    pub fn call(&self, method: &str, params: Map<String, Value>) -> Result<Value, String> {
        let mut guard = self.0.lock().map_err(|_| "sidecar lock poisoned")?;
        let link = guard.as_mut().ok_or("the sidecar is not running")?;
        link.next_id += 1;
        let mut request = params;
        request.insert("id".into(), json!(link.next_id));
        request.insert("method".into(), json!(method));
        writeln!(link.stdin, "{}", Value::Object(request))
            .and_then(|_| link.stdin.flush())
            .map_err(|e| format!("sidecar write failed: {e}"))?;
        let mut line = String::new();
        if link
            .stdout
            .read_line(&mut line)
            .map_err(|e| e.to_string())?
            == 0
        {
            return Err("the sidecar closed".into());
        }
        let answer: Value =
            serde_json::from_str(&line).map_err(|e| format!("bad answer from the sidecar: {e}"))?;
        if let Some(error) = answer.get("error") {
            return Err(error.as_str().unwrap_or("sidecar error").to_string());
        }
        Ok(answer.get("result").cloned().unwrap_or(Value::Null))
    }
}

/// Repo root, found at build time. shortcut: dev builds only; a packaged app needs a bundled Python.
pub fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

/// The repo's .venv Python. shortcut: no bundled runtime yet, so the app needs `uv sync` first.
fn python_for(root: &Path) -> PathBuf {
    if cfg!(windows) {
        root.join(".venv/Scripts/python.exe")
    } else {
        root.join(".venv/bin/python")
    }
}

/// HIPPOCAMPUS_VAULT, else brains/sample. shortcut: config/settings.toml is not read yet.
pub fn default_vault(root: &Path) -> PathBuf {
    std::env::var_os("HIPPOCAMPUS_VAULT")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("brains/sample"))
}

#[tauri::command]
pub async fn sidecar_call(
    sidecar: State<'_, Sidecar>,
    method: String,
    params: Option<Map<String, Value>>,
) -> Result<Value, String> {
    let shared = sidecar.inner().clone();
    tauri::async_runtime::spawn_blocking(move || shared.call(&method, params.unwrap_or_default()))
        .await
        .map_err(|e| e.to_string())?
}
