//! The Python sidecar: `python -m core serve`. One JSON request per line on its stdin, one
//! answer per line on its stdout. Lines with an "event" key are pushed to the UI as
//! "sidecar-event". Localhost-free: no port, no token.
//!
//! Start and restart happen on a background thread, and a reader thread routes each answer
//! to the call that asked, so a slow call never blocks a stop.

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::mpsc::{channel, Sender};
use std::sync::{Arc, Condvar, Mutex, MutexGuard};
use std::thread;

use serde_json::{json, Map, Value};
use tauri::{AppHandle, Emitter, State};

type Waiting = Arc<Mutex<HashMap<u64, Sender<Value>>>>;

struct Link {
    child: Child,
    stdin: ChildStdin,
    next_id: u64,
    waiting: Waiting,
}

impl Drop for Link {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

enum ConnState {
    Starting,
    Running(Link),
    Down(String),
}

enum CallError {
    /// The sidecar with this process id stopped answering.
    Dead(u32),
    Failed(String),
}

/// The running sidecar, shared by the Tauri commands.
#[derive(Clone)]
pub struct Sidecar {
    state: Arc<(Mutex<ConnState>, Condvar)>,
    app: AppHandle,
}

impl Sidecar {
    pub fn new(app: AppHandle) -> Self {
        Self {
            state: Arc::new((Mutex::new(ConnState::Starting), Condvar::new())),
            app,
        }
    }

    /// Start the sidecar, which opens the vault named in config/settings.toml.
    pub fn start(&self) -> Result<(), String> {
        self.set(ConnState::Starting)?;
        self.spawn_and_publish()
    }

    fn spawn_and_publish(&self) -> Result<(), String> {
        match spawn(&self.app) {
            Ok(link) => self.set(ConnState::Running(link)),
            Err(error) => {
                self.set(ConnState::Down(error.clone()))?;
                Err(error)
            }
        }
    }

    /// Send one request and return its `result`, or the sidecar's `error` message.
    /// A sidecar that stopped is restarted once, and the call is retried.
    pub fn call(&self, method: &str, params: Map<String, Value>) -> Result<Value, String> {
        self.wait_running()?;
        match self.try_call(method, params.clone()) {
            Ok(value) => Ok(value),
            Err(CallError::Failed(message)) => Err(message),
            Err(CallError::Dead(pid)) => {
                eprintln!("Hippocampus: the sidecar stopped; restarting it once");
                self.restart_if_still(pid)?;
                self.wait_running()?;
                self.try_call(method, params).map_err(|error| match error {
                    CallError::Dead(_) => "the sidecar stopped again".to_string(),
                    CallError::Failed(message) => message,
                })
            }
        }
    }

    fn try_call(&self, method: &str, params: Map<String, Value>) -> Result<Value, CallError> {
        let (answer_rx, pid) = {
            let mut guard = lock(&self.state.0).map_err(CallError::Failed)?;
            let ConnState::Running(link) = &mut *guard else {
                return Err(CallError::Failed("the sidecar is not running".into()));
            };
            let pid = link.child.id();
            link.next_id += 1;
            let id = link.next_id;
            let (tx, rx) = channel();
            lock(&link.waiting)
                .map_err(CallError::Failed)?
                .insert(id, tx);
            let mut request = params;
            request.insert("id".into(), json!(id));
            request.insert("method".into(), json!(method));
            let written =
                writeln!(link.stdin, "{}", Value::Object(request)).and_then(|_| link.stdin.flush());
            if written.is_err() {
                lock(&link.waiting).map_err(CallError::Failed)?.remove(&id);
                return Err(CallError::Dead(pid));
            }
            (rx, pid)
        };
        // The state lock is released while waiting, so a stop request can get through.
        let answer = answer_rx.recv().map_err(|_| CallError::Dead(pid))?;
        if let Some(error) = answer.get("error") {
            return Err(CallError::Failed(
                error.as_str().unwrap_or("sidecar error").to_string(),
            ));
        }
        Ok(answer.get("result").cloned().unwrap_or(Value::Null))
    }

    /// Restart only if the sidecar that failed is still the current one.
    fn restart_if_still(&self, pid: u32) -> Result<(), String> {
        {
            let mut guard = lock(&self.state.0)?;
            match &*guard {
                ConnState::Running(link) if link.child.id() == pid => {}
                _ => return Ok(()),
            }
            *guard = ConnState::Starting;
        }
        self.state.1.notify_all();
        self.spawn_and_publish()
    }

    fn set(&self, next: ConnState) -> Result<(), String> {
        *lock(&self.state.0)? = next;
        self.state.1.notify_all();
        Ok(())
    }

    /// Wait while the sidecar is starting; fail if it is down.
    fn wait_running(&self) -> Result<(), String> {
        let (mutex, condvar) = &*self.state;
        let mut guard = lock(mutex)?;
        while matches!(*guard, ConnState::Starting) {
            guard = condvar
                .wait(guard)
                .map_err(|_| "sidecar lock poisoned".to_string())?;
        }
        match &*guard {
            ConnState::Down(error) => Err(error.clone()),
            _ => Ok(()),
        }
    }
}

fn lock<T>(mutex: &Mutex<T>) -> Result<MutexGuard<'_, T>, String> {
    mutex
        .lock()
        .map_err(|_| "sidecar lock poisoned".to_string())
}

fn spawn(app: &AppHandle) -> Result<Link, String> {
    let root = project_root();
    let python = python_for(&root);
    let mut child = Command::new(&python)
        .args(["-m", "core", "serve"])
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
        return Err("the sidecar did not start; check config/settings.toml and the .venv".into());
    }
    let waiting: Waiting = Arc::default();
    let reader_app = app.clone();
    let reader_waiting = waiting.clone();
    thread::spawn(move || read_answers(stdout, reader_app, reader_waiting));
    Ok(Link {
        child,
        stdin,
        next_id: 0,
        waiting,
    })
}

/// Route every line the sidecar prints: events to the UI, answers to the call that asked.
fn read_answers(stdout: BufReader<ChildStdout>, app: AppHandle, waiting: Waiting) {
    for line in stdout.lines() {
        let Ok(line) = line else { break };
        let Ok(value) = serde_json::from_str::<Value>(&line) else {
            eprintln!("Hippocampus: the sidecar sent a line that is not JSON: {line}");
            continue;
        };
        if value.get("event").is_some() {
            if let Err(error) = app.emit("sidecar-event", value) {
                eprintln!("Hippocampus: could not send a sidecar event to the UI: {error}");
            }
            continue;
        }
        let sender = value
            .get("id")
            .and_then(Value::as_u64)
            .and_then(|id| lock(&waiting).ok()?.remove(&id));
        match sender {
            // A caller that gave up has dropped its receiver; the answer is no longer wanted.
            Some(sender) => {
                let _ = sender.send(value);
            }
            None => eprintln!("Hippocampus: the sidecar sent an answer nobody is waiting for"),
        }
    }
    // The sidecar is gone: drop every waiting sender so each waiting call fails over.
    if let Ok(mut waiting) = waiting.lock() {
        waiting.clear();
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
