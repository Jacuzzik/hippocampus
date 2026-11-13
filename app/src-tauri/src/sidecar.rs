//! The Python sidecar: `python -m core serve`. One JSON request per line on its stdin, one
//! answer per line on its stdout. Lines with an "event" key are pushed to the UI as
//! "sidecar-event". Localhost-free: no port, no token.
//!
//! Start and restart happen on a background thread, and a reader thread routes each answer
//! to the call that asked, so a slow call never blocks a stop.

use std::collections::HashMap;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::mpsc::{channel, Sender};
use std::sync::{Arc, Condvar, Mutex, MutexGuard};
use std::thread;

use serde_json::{json, Map, Value};
use tauri::{AppHandle, Emitter, Manager, State};

/// The settings a packaged app starts from; the repo's file, copied in on first run.
const DEFAULT_SETTINGS: &str = include_str!("../../../config/settings.toml");
/// The bundled sidecar's name next to the app executable (Tauri drops the target triple).
const SIDECAR_NAME: &str = "hippocampus-sidecar";

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
                    CallError::Dead(_) => "the backend stopped again".to_string(),
                    CallError::Failed(message) => message,
                })
            }
        }
    }

    fn try_call(&self, method: &str, params: Map<String, Value>) -> Result<Value, CallError> {
        let (answer_rx, pid) = {
            let mut guard = lock(&self.state.0).map_err(CallError::Failed)?;
            let ConnState::Running(link) = &mut *guard else {
                return Err(CallError::Failed("the backend is not running".into()));
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
            let message = error.as_str().unwrap_or("backend error");
            // The backend adds the next step when it knows one; the window shows both.
            return Err(CallError::Failed(
                match answer.get("hint").and_then(Value::as_str) {
                    Some(hint) => format!("{message} {hint}"),
                    None => message.to_string(),
                },
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
                .map_err(|_| "backend lock poisoned".to_string())?;
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
        .map_err(|_| "backend lock poisoned".to_string())
}

fn spawn(app: &AppHandle) -> Result<Link, String> {
    let mut command = sidecar_command(app)?;
    let mut child = command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .map_err(|e| format!("could not start {:?}: {e}", command.get_program()))?;
    let stdin = child.stdin.take().ok_or("backend has no stdin")?;
    let mut stdout = BufReader::new(child.stdout.take().ok_or("backend has no stdout")?);
    let mut ready = String::new();
    let read = stdout.read_line(&mut ready).map_err(|e| e.to_string())?;
    let status = serde_json::from_str::<Value>(&ready).ok();
    if read == 0 || status.as_ref().and_then(|s| s["status"].as_str()) != Some("ready") {
        let _ = child.kill();
        let _ = child.wait();
        return Err(
            "the backend did not start; check config/settings.toml and the vault folder".into(),
        );
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

/// Dev runs the repo's Python. A packaged app runs the bundled sidecar, and its settings and
/// vault live in the user data folder, so the app works with no repo or .venv present.
fn sidecar_command(app: &AppHandle) -> Result<Command, String> {
    if tauri::is_dev() {
        let root = project_root();
        prepare_vault(&root)?;
        let mut command = Command::new(python_for(&root));
        command.args(["-m", "core", "serve"]).current_dir(&root);
        return Ok(command);
    }
    let data = app.path().app_data_dir().map_err(|e| e.to_string())?;
    prepare_data(&data)?;
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let sidecar = exe
        .parent()
        .ok_or("the app has no folder")?
        .join(SIDECAR_NAME);
    let mut command = Command::new(sidecar);
    command
        .arg("serve")
        .arg("--settings")
        .arg(data.join("config/settings.toml"))
        .arg("--storage")
        .arg(data.join("storage"))
        .current_dir(&data);
    Ok(command)
}

/// First run: write the default settings and make the default vault folder. Keeps existing files.
fn prepare_data(data: &Path) -> Result<(), String> {
    let settings = data.join("config/settings.toml");
    if !settings.exists() {
        fs::create_dir_all(data.join("config")).map_err(|e| e.to_string())?;
        fs::write(&settings, DEFAULT_SETTINGS).map_err(|e| e.to_string())?;
    }
    prepare_vault(data)
}

/// Makes the default vault brains/Hippocampus under `base` (recreated if deleted) and its daily backup.
fn prepare_vault(base: &Path) -> Result<(), String> {
    let vault = base.join("brains/Hippocampus");
    fs::create_dir_all(&vault).map_err(|e| e.to_string())?;
    let welcome = vault.join("Welcome.md");
    if !welcome.exists() {
        fs::write(&welcome, WELCOME_NOTE).map_err(|e| e.to_string())?;
    }
    write_hubs(&vault)?;
    backup_daily(&vault, &base.join("backups"))
}

/// The MAIN hub and its six groups. Missing notes are re-created on every start; edits are kept.
fn write_hubs(vault: &Path) -> Result<(), String> {
    // (name, colour as an RGB number). MAIN is white.
    const GROUPS: [(&str, u32); 6] = [
        ("Projects", 0xA855F7),
        ("Summaries", 0xEF4444),
        ("Agent Lists", 0x84CC16),
        ("Contacts", 0x7DD3FC),
        ("Socials", 0xF97316),
        ("About User", 0xFACC15),
    ];
    const MAIN: (&str, u32) = ("MAIN", 0xFFFFFF);
    let links: String = GROUPS
        .iter()
        .map(|(name, _)| format!("- [[{name}]]\n"))
        .collect();
    let main = format!(
        "# MAIN\n\nInstructions for all agents. Read this first.\n\n- Work in your own folder and the vault. Do not change other agents' notes.\n- Before you compact, save your notes and a summary to your own note.\n- If you do not know something, search the vault before you ask.\n- Only the user deletes a note linked to a group.\n\nGroups:\n\n{links}"
    );
    let mut notes = vec![(MAIN.0.to_string(), main)];
    for (name, _) in GROUPS {
        let body = match name {
            "Projects" => "Active projects: the goal, the status, and links to the notes for it. One note per project, linked here.",
            "Summaries" => "Daily summaries that each agent saves before it compacts: what it did, what it decided, what is still open. One note per day, linked here.",
            "Agent Lists" => "Every agent in the app: what it does, its status (active, archived or deleted) and where its memory is kept. One note per agent, linked here. Only the user can edit, delete or remove these notes.",
            "Contacts" => "People the user works with. Each contact has a name, a phone number (if they have one), an optional label, and a line on who they are. A phone number always needs a name: if you do not have one, ask the user for it. One note per person, linked here.",
            "Socials" => "The user's accounts on every platform: platform, account name or handle, profile link, and purpose. Never store passwords, logins or keys here.",
            _ => "Facts about the user that agents need: role, preferences and how they like replies. Change it only when the user says so.",
        };
        notes.push((name.to_string(), format!("# {name}\n\n{body}\n")));
    }
    for (name, body) in notes {
        let path = vault.join(format!("{name}.md"));
        if !path.exists() {
            fs::write(&path, body).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

/// Copies the vault into backups/YYYY-MM-DD once per day, keeping the newest 30 copies.
fn backup_daily(vault: &Path, backups: &Path) -> Result<(), String> {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_secs() as i64;
    let (y, m, d) = civil_date(secs.div_euclid(86_400));
    let target = backups.join(format!("{y:04}-{m:02}-{d:02}"));
    if target.exists() {
        return Ok(());
    }
    fs::create_dir_all(backups).map_err(|e| e.to_string())?;
    copy_dir(vault, &target)?;
    let mut days: Vec<PathBuf> = fs::read_dir(backups)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.is_dir())
        .collect();
    days.sort();
    let extra = days.len().saturating_sub(30);
    for old in &days[..extra] {
        fs::remove_dir_all(old).map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn copy_dir(from: &Path, to: &Path) -> Result<(), String> {
    fs::create_dir_all(to).map_err(|e| e.to_string())?;
    for entry in fs::read_dir(from).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let target = to.join(entry.file_name());
        if entry.path().is_dir() {
            copy_dir(&entry.path(), &target)?;
        } else {
            fs::copy(entry.path(), &target).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

/// Calendar date (year, month, day) for a count of days since 1970-01-01 (Howard Hinnant's algorithm).
fn civil_date(days: i64) -> (i64, u32, u32) {
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = (if mp < 10 { mp + 3 } else { mp - 9 }) as u32;
    (yoe + era * 400 + i64::from(m <= 2), m, d)
}

/// The starter note in a new default vault. Any folder of Markdown can be opened as a vault instead.
const WELCOME_NOTE: &str = "# Welcome to Hippocampus\n\nThis is your default vault: a folder of Markdown notes.\nLink notes with [[double brackets]]. To use another folder, open it in Settings.\n";

/// Repo root, found at build time. Dev only: a packaged app never reads it.
fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

/// The repo's .venv Python. Dev only: a packaged app runs the bundled sidecar.
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
