#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    sync::Mutex,
    time::{Duration, Instant},
};

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

const API_HOST: &str = "127.0.0.1";
const API_PORT: u16 = 8765;
const HEALTH_TIMEOUT_SECONDS: u64 = 90;
const HEALTH_POLL_MS: u64 = 250;

struct SidecarState(Mutex<Option<CommandChild>>);

#[tauri::command]
fn pick_excel_file() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("Excel/CSV", &["xlsx", "xls", "xlsm", "csv"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[cfg(not(debug_assertions))]
fn start_bundled_sidecar(app: &tauri::AppHandle) -> Result<CommandChild, String> {
    let command = app
        .shell()
        .sidecar("lightningbid-api")
        .map_err(|e| format!("failed to resolve sidecar: {e}"))?;

    let (_rx, child) = command
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {e}"))?;

    Ok(child)
}

#[cfg(debug_assertions)]
fn start_dev_python_api(app: &tauri::AppHandle) -> Result<CommandChild, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let repo_root = manifest_dir
        .parent()
        .and_then(|p| p.parent())
        .ok_or_else(|| String::from("failed to resolve repo root from CARGO_MANIFEST_DIR"))?;

    let api_script = repo_root.join("api_local").join("run_api.py");
    if !api_script.exists() {
        return Err(format!(
            "dev api script not found at {}",
            api_script.display()
        ));
    }

    let venv_python = repo_root.join(".venv").join("Scripts").join("python.exe");
    let python_cmd = if venv_python.exists() {
        venv_python.to_string_lossy().to_string()
    } else {
        String::from("python")
    };

    let probe_status = std::process::Command::new(&python_cmd)
        .args(["-c", "import fastapi, uvicorn"])
        .status()
        .map_err(|e| format!("failed to run python dependency probe: {e}"))?;
    if !probe_status.success() {
        return Err(String::from(
            "missing FastAPI deps in .venv. Run: .venv\\Scripts\\python.exe -m pip install -r api_local\\requirements.txt",
        ));
    }

    let command = app.shell().command(python_cmd).args([api_script
        .to_string_lossy()
        .to_string()]);
    let (_rx, child) = command
        .spawn()
        .map_err(|e| format!("failed to spawn dev python api: {e}"))?;

    Ok(child)
}

fn start_sidecar(app: &tauri::AppHandle) -> Result<CommandChild, String> {
    #[cfg(debug_assertions)]
    {
        return start_dev_python_api(app);
    }

    #[cfg(not(debug_assertions))]
    {
        start_bundled_sidecar(app)
    }
}

fn check_health_once() -> bool {
    let addr: SocketAddr = format!("{API_HOST}:{API_PORT}")
        .parse()
        .expect("valid loopback address");

    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(500)) {
        Ok(s) => s,
        Err(_) => return false,
    };

    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));

    let req = b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    if stream.write_all(req).is_err() {
        return false;
    }

    let mut response = Vec::with_capacity(1024);
    let mut buf = [0_u8; 1024];
    loop {
        match stream.read(&mut buf) {
            Ok(0) => break,
            Ok(n) => response.extend_from_slice(&buf[..n]),
            Err(e)
                if e.kind() == std::io::ErrorKind::WouldBlock
                    || e.kind() == std::io::ErrorKind::TimedOut =>
            {
                break
            }
            Err(_) => return false,
        }
    }

    if response.is_empty() {
        return false;
    }

    let raw = String::from_utf8_lossy(&response);
    raw.starts_with("HTTP/1.1 200") || raw.starts_with("HTTP/1.0 200")
}

fn wait_for_health(timeout: Duration) -> Result<(), String> {
    let started = Instant::now();
    while started.elapsed() < timeout {
        if check_health_once() {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(HEALTH_POLL_MS));
    }
    Err(format!(
        "FastAPI sidecar did not become healthy within {}s",
        timeout.as_secs()
    ))
}

fn stop_sidecar(app: &tauri::AppHandle) {
    let state = app.state::<SidecarState>();
    let mut guard = match state.0.lock() {
        Ok(g) => g,
        Err(_) => return,
    };

    if let Some(child) = guard.take() {
        let _ = child.kill();
    }
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![pick_excel_file])
        .manage(SidecarState(Mutex::new(None)))
        .setup(|app| {
            let child = start_sidecar(&app.handle())?;
            {
                let state = app.state::<SidecarState>();
                let mut guard = state
                    .0
                    .lock()
                    .map_err(|_| String::from("failed to lock sidecar state"))?;
                *guard = Some(child);
            }

            if let Err(err) = wait_for_health(Duration::from_secs(HEALTH_TIMEOUT_SECONDS)) {
                stop_sidecar(&app.handle());
                return Err(err.into());
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build tauri app");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            stop_sidecar(app_handle);
        }
    });
}
