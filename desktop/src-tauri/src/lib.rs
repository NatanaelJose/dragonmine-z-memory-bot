use serde::Serialize;
use std::{
    io::{BufRead, BufReader},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
};
use tauri::{AppHandle, Emitter, Manager, State};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
unsafe extern "system" {
    fn keybd_event(virtual_key: u8, scan_code: u8, flags: u32, extra_info: usize);
}

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
#[cfg(target_os = "windows")]
const KEYEVENTF_KEYUP: u32 = 0x0002;

fn release_arrow_keys() {
    #[cfg(target_os = "windows")]
    for virtual_key in [0x25_u8, 0x26, 0x27, 0x28] {
        // Safety: keybd_event is a stateless Win32 input call. Sending KEYUP
        // for all arrows prevents a sustain from sticking if Python is killed.
        unsafe { keybd_event(virtual_key, 0, KEYEVENTF_KEYUP, 0) };
    }
}

struct BotProcess {
    child: Mutex<Option<Child>>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct LogEvent {
    stream: &'static str,
    line: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ProcessStatus {
    running: bool,
}

fn contains_bot(root: &Path) -> bool {
    root.join("main.py").is_file()
        && root
            .join("venv")
            .join("Scripts")
            .join("python.exe")
            .is_file()
}

fn find_bot_root() -> Result<PathBuf, String> {
    let current = std::env::current_dir().map_err(|error| error.to_string())?;
    for ancestor in current.ancestors().take(6) {
        if contains_bot(ancestor) {
            return Ok(ancestor.to_path_buf());
        }
    }
    Err("Could not find main.py and venv. Set DRAGONMINE_BOT_ROOT to the project directory.".into())
}

enum BotRuntime {
    Bundled {
        executable: PathBuf,
        working_dir: PathBuf,
    },
    Development {
        python: PathBuf,
        script: PathBuf,
        working_dir: PathBuf,
    },
}

fn resolve_runtime(app: &AppHandle) -> Result<BotRuntime, String> {
    // During `tauri dev`, always prefer the live Python sources. A previously
    // packaged executable may be present in target/debug/resources and would
    // otherwise hide recorder changes until PyInstaller is rebuilt.
    #[cfg(debug_assertions)]
    if let Ok(root) = std::env::var_os("DRAGONMINE_BOT_ROOT")
        .map(PathBuf::from)
        .map_or_else(find_bot_root, Ok)
    {
        if contains_bot(&root) {
            return Ok(BotRuntime::Development {
                python: root.join("venv").join("Scripts").join("python.exe"),
                script: root.join("main.py"),
                working_dir: root,
            });
        }
    }

    if let Ok(resource_dir) = app.path().resource_dir() {
        let executable = resource_dir.join("binaries").join("dragonmine-bot.exe");
        if executable.is_file() {
            return Ok(BotRuntime::Bundled {
                working_dir: resource_dir,
                executable,
            });
        }
    }

    let root = std::env::var_os("DRAGONMINE_BOT_ROOT")
        .map(PathBuf::from)
        .map_or_else(find_bot_root, Ok)?;
    if !contains_bot(&root) {
        return Err(format!("Bot runtime was not found in {}", root.display()));
    }
    Ok(BotRuntime::Development {
        python: root.join("venv").join("Scripts").join("python.exe"),
        script: root.join("main.py"),
        working_dir: root,
    })
}

fn restore_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn emit_lines<R: std::io::Read + Send + 'static>(
    reader: R,
    stream: &'static str,
    app: AppHandle,
    restore_when_done: bool,
) {
    std::thread::spawn(move || {
        for line in BufReader::new(reader).lines().map_while(Result::ok) {
            if restore_when_done && line.contains("RHYTHM_CAPTURE:SAVED") {
                restore_main_window(&app);
            }
            let _ = app.emit("bot-log", LogEvent { stream, line });
        }
        if restore_when_done {
            restore_main_window(&app);
        }
    });
}

fn refresh_child(state: &BotProcess) -> Result<bool, String> {
    let mut guard = state
        .child
        .lock()
        .map_err(|_| "Bot process lock is poisoned")?;
    if let Some(child) = guard.as_mut() {
        match child.try_wait().map_err(|error| error.to_string())? {
            Some(_) => {
                release_arrow_keys();
                *guard = None;
                Ok(false)
            }
            None => Ok(true),
        }
    } else {
        Ok(false)
    }
}

#[tauri::command]
fn get_bot_status(state: State<'_, BotProcess>) -> Result<ProcessStatus, String> {
    Ok(ProcessStatus {
        running: refresh_child(&state)?,
    })
}

#[tauri::command]
fn start_bot(
    app: AppHandle,
    state: State<'_, BotProcess>,
    game: String,
    speed: String,
    hold_time: Option<f64>,
    key_delay: Option<f64>,
    poll_interval: Option<f64>,
) -> Result<ProcessStatus, String> {
    if refresh_child(&state)? {
        return Err("The bot is already running.".into());
    }
    if !matches!(game.as_str(), "memory" | "rhythm" | "rhythm-capture") {
        return Err("Unknown game mode.".into());
    }
    if !matches!(speed.as_str(), "fast" | "safe" | "custom") {
        return Err("Unknown speed profile.".into());
    }
    if hold_time.is_some_and(|value| !(0.025..=0.2).contains(&value))
        || key_delay.is_some_and(|value| !(0.025..=0.2).contains(&value))
    {
        return Err("Custom timings must be between 0.025 and 0.2 seconds.".into());
    }
    if poll_interval.is_some_and(|value| !(0.0..=0.05).contains(&value)) {
        return Err("Capture interval must be between 0 and 0.05 seconds.".into());
    }

    let runtime = resolve_runtime(&app)?;
    let mut command = match runtime {
        BotRuntime::Bundled {
            executable,
            working_dir,
        } => {
            let mut command = Command::new(executable);
            command.current_dir(working_dir);
            command
        }
        BotRuntime::Development {
            python,
            script,
            working_dir,
        } => {
            let mut command = Command::new(python);
            command.current_dir(working_dir).arg("-u").arg(script);
            command
        }
    };
    command
        .env("PYTHONUNBUFFERED", "1")
        .arg("--game")
        .arg(&game)
        .arg("--speed")
        .arg(if speed == "custom" { "fast" } else { &speed })
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    if speed == "custom" {
        command
            .arg("--hold-time")
            .arg(hold_time.unwrap_or(0.03).to_string())
            .arg("--key-delay")
            .arg(key_delay.unwrap_or(0.03).to_string());
    }
    if game == "memory" {
        command
            .arg("--poll-interval")
            .arg(poll_interval.unwrap_or(0.05).to_string());
    }

    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);

    let mut child = command
        .spawn()
        .map_err(|error| format!("Failed to start bot: {error}"))?;
    if let Some(stdout) = child.stdout.take() {
        emit_lines(stdout, "stdout", app.clone(), game == "rhythm-capture");
    }
    if let Some(stderr) = child.stderr.take() {
        emit_lines(stderr, "stderr", app.clone(), false);
    }

    *state
        .child
        .lock()
        .map_err(|_| "Bot process lock is poisoned")? = Some(child);
    if game == "rhythm-capture" {
        if let Some(window) = app.get_webview_window("main") {
            let _ = window.minimize();
        }
    }
    Ok(ProcessStatus { running: true })
}

#[tauri::command]
fn stop_bot(state: State<'_, BotProcess>) -> Result<ProcessStatus, String> {
    let mut guard = state
        .child
        .lock()
        .map_err(|_| "Bot process lock is poisoned")?;
    if let Some(child) = guard.as_mut() {
        release_arrow_keys();
        child
            .kill()
            .map_err(|error| format!("Failed to stop bot: {error}"))?;
        let _ = child.wait();
    }
    *guard = None;
    Ok(ProcessStatus { running: false })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BotProcess {
            child: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            get_bot_status,
            start_bot,
            stop_bot
        ])
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::Destroyed) {
                let state = window.state::<BotProcess>();
                if let Ok(mut guard) = state.child.lock() {
                    if let Some(child) = guard.as_mut() {
                        release_arrow_keys();
                        let _ = child.kill();
                    }
                    *guard = None;
                };
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn development_runtime_is_discoverable_from_the_tauri_crate() {
        let root = find_bot_root().expect("project bot runtime should be discoverable");
        assert!(contains_bot(&root));
    }
}
