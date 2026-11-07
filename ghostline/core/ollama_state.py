"""
Ghostline — Ollama First-Run & State Machine Subsystem.
Tracks and transitions between Ollama lifecycle states:
NOT_INSTALLED -> INSTALLED_NOT_RUNNING -> RUNNING_NO_MODEL -> READY.
Provides reliable probing, detached process management, log inspection,
and friendly guidance without opening console or PowerShell windows.
"""

import os
import sys
import json
import shutil
import logging
import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple, Callable, Dict, Any

import requests
from ghostline.core.http_client import GHOSTLINE_USER_AGENT

logger = logging.getLogger("ghostline.ollama_state")


class OllamaState(str, Enum):
    NOT_INSTALLED = "NOT_INSTALLED"
    INSTALLED_NOT_RUNNING = "INSTALLED_NOT_RUNNING"
    RUNNING_NO_MODEL = "RUNNING_NO_MODEL"
    READY = "READY"


# Global tracking for Ollama process launched by Ghostline
_GHOSTLINE_SPAWNED_PROCESS: Optional[subprocess.Popen] = None
_GHOSTLINE_STARTED_OLLAMA: bool = False


def get_default_ollama_url() -> str:
    """Respects OLLAMA_HOST environment variable, defaulting to 127.0.0.1:11434."""
    host_env = os.environ.get("OLLAMA_HOST", "").strip()
    if host_env:
        if "://" not in host_env:
            host_env = f"http://{host_env}"
        return host_env.rstrip("/")
    return "http://127.0.0.1:11434"


def probe_http_ollama(base_url: str) -> Tuple[bool, List[str]]:
    """
    Probes Ollama version and models endpoints.
    Returns: (is_running: bool, model_tags: List[str])
    """
    clean_url = (base_url or get_default_ollama_url()).rstrip("/")
    headers = {"User-Agent": GHOSTLINE_USER_AGENT}
    try:
        # Probe version endpoint (official Ollama API)
        v_resp = requests.get(f"{clean_url}/api/version", headers=headers, timeout=1.5)
        if v_resp.status_code != 200:
            return False, []

        # Probe model tags list
        t_resp = requests.get(f"{clean_url}/api/tags", headers=headers, timeout=1.5)
        if t_resp.status_code == 200:
            data = t_resp.json()
            models = []
            for item in data.get("models", []):
                name = item.get("name") or item.get("model")
                if name:
                    models.append(str(name).lower())
            return True, models

        return True, []
    except Exception:
        return False, []


def probe_installed_ollama() -> Tuple[bool, Optional[Path], Optional[Path]]:
    """
    Inspects Windows file system, PATH, and uninstall registry for Ollama.
    Returns: (is_installed: bool, cli_exe: Optional[Path], app_exe: Optional[Path])
    """
    cli_cand: Optional[Path] = None
    app_cand: Optional[Path] = None

    # 1. Check default per-user install directory (%LOCALAPPDATA%\Programs\Ollama)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        p_dir = Path(local_app_data) / "Programs" / "Ollama"
        if (p_dir / "ollama.exe").exists():
            cli_cand = p_dir / "ollama.exe"
        if (p_dir / "ollama app.exe").exists():
            app_cand = p_dir / "ollama app.exe"

    # 2. Check system-wide Program Files
    program_files = os.environ.get("ProgramFiles")
    if program_files and not cli_cand:
        pf_dir = Path(program_files) / "Ollama"
        if (pf_dir / "ollama.exe").exists():
            cli_cand = pf_dir / "ollama.exe"
        if (pf_dir / "ollama app.exe").exists():
            app_cand = pf_dir / "ollama app.exe"

    # 3. Check %LOCALAPPDATA%\Ollama
    if local_app_data and not cli_cand:
        alt_dir = Path(local_app_data) / "Ollama"
        if (alt_dir / "ollama.exe").exists():
            cli_cand = alt_dir / "ollama.exe"

    # 4. Check system PATH
    if not cli_cand:
        which_path = shutil.which("ollama") or shutil.which("ollama.exe")
        if which_path:
            cli_cand = Path(which_path)

    # 5. Check Windows Registry (Uninstall entries)
    if not cli_cand and sys.platform == "win32":
        try:
            import winreg
            keys = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hkey, subkey_path in keys:
                try:
                    with winreg.OpenKey(hkey, subkey_path) as parent:
                        idx = 0
                        while True:
                            try:
                                sub_name = winreg.EnumKey(parent, idx)
                                idx += 1
                                with winreg.OpenKey(parent, sub_name) as sub:
                                    try:
                                        disp_name, _ = winreg.QueryValueEx(sub, "DisplayName")
                                        if "ollama" in str(disp_name).lower():
                                            loc, _ = winreg.QueryValueEx(sub, "InstallLocation")
                                            if loc and Path(loc).exists():
                                                if (Path(loc) / "ollama.exe").exists():
                                                    cli_cand = Path(loc) / "ollama.exe"
                                                if (Path(loc) / "ollama app.exe").exists():
                                                    app_cand = Path(loc) / "ollama app.exe"
                                                break
                                    except Exception:
                                        pass
                            except OSError:
                                break
                except Exception:
                    pass
        except Exception:
            pass

    is_installed = bool(cli_cand is not None or app_cand is not None)
    return is_installed, cli_cand, app_cand


def get_ollama_log_tail(max_lines: int = 25) -> Tuple[str, str]:
    """
    Reads the tail of Ollama's log file (%LOCALAPPDATA%\\Ollama\\server.log)
    and diagnoses likely failure causes.
    Returns: (tail_text: str, diagnostic_summary: str)
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    candidates = []
    if local_app_data:
        candidates.append(Path(local_app_data) / "Ollama" / "server.log")
        candidates.append(Path(local_app_data) / "Ollama" / "app.log")

    log_content = ""
    for c in candidates:
        if c.exists():
            try:
                txt = c.read_text(encoding="utf-8", errors="replace")
                if txt.strip():
                    log_content = txt
                    break
            except Exception:
                pass

    if not log_content:
        return "No Ollama server logs found.", "Could not locate %LOCALAPPDATA%\\Ollama\\server.log"

    lines = log_content.strip().splitlines()
    tail = "\n".join(lines[-max_lines:])

    diag = "Ollama startup was interrupted."
    lower_tail = tail.lower()
    if "address already in use" in lower_tail or "bind: only one usage of each socket address" in lower_tail:
        diag = "Port 11434 is already in use by another instance or process."
    elif "access is denied" in lower_tail or "permission denied" in lower_tail:
        diag = "Access denied: Local security software or firewall may be restricting Ollama."
    elif "gpu" in lower_tail and "failed" in lower_tail:
        diag = "GPU initialization issue (Ollama can run in CPU fallback mode)."

    return tail, diag


def start_ollama_process(
    app_exe: Optional[Path] = None,
    cli_exe: Optional[Path] = None
) -> Tuple[bool, Optional[subprocess.Popen], str]:
    """
    Starts Ollama in the background WITHOUT PowerShell or a visible console window.
    Prefers launching the desktop tray app (as Start menu does); otherwise executes 'ollama serve'
    detached with CREATE_NO_WINDOW | DETACHED_PROCESS so it outlives Ghostline.
    Tracks process so Ghostline knows it started it.
    """
    global _GHOSTLINE_SPAWNED_PROCESS, _GHOSTLINE_STARTED_OLLAMA

    # Re-probe if paths not supplied
    if not app_exe and not cli_exe:
        _, cli_exe, app_exe = probe_installed_ollama()

    target_exe: Optional[Path] = app_exe or cli_exe
    if not target_exe or not target_exe.exists():
        return False, None, "Ollama executable not found on device."

    creationflags = 0
    if sys.platform == "win32":
        # CREATE_NO_WINDOW = 0x08000000, DETACHED_PROCESS = 0x00000008
        creationflags = 0x08000000 | 0x00000008

    try:
        cmd = [str(target_exe)]
        if target_exe == cli_exe and "app" not in target_exe.name.lower():
            cmd.append("serve")

        proc = subprocess.Popen(
            cmd,
            creationflags=creationflags,
            close_fds=(sys.platform != "win32"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        _GHOSTLINE_SPAWNED_PROCESS = proc
        _GHOSTLINE_STARTED_OLLAMA = True
        logger.info("Spawned Ollama detached process (PID: %d, cmd: %s)", proc.pid, cmd)
        return True, proc, f"Started Ollama (PID: {proc.pid})"
    except Exception as e:
        logger.error("Failed to spawn Ollama process: %s", e)
        return False, None, f"Failed to start Ollama: {e}"


def stop_ghostline_started_ollama() -> bool:
    """
    Stops Ollama process ONLY if Ghostline started it.
    Never terminates an instance started by the user or Windows startup.
    """
    global _GHOSTLINE_SPAWNED_PROCESS, _GHOSTLINE_STARTED_OLLAMA
    if not _GHOSTLINE_STARTED_OLLAMA or _GHOSTLINE_SPAWNED_PROCESS is None:
        return False

    try:
        proc = _GHOSTLINE_SPAWNED_PROCESS
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except Exception:
                proc.kill()
        _GHOSTLINE_SPAWNED_PROCESS = None
        _GHOSTLINE_STARTED_OLLAMA = False
        logger.info("Terminated Ghostline-spawned Ollama process.")
        return True
    except Exception as e:
        logger.warning("Error stopping Ghostline-spawned Ollama: %s", e)
        return False


class OllamaStateMachine:
    """
    State machine for Ollama lifecycle.
    Supports dependency injection for probes to facilitate deterministic unit testing.
    """
    def __init__(
        self,
        http_probe: Optional[Callable[[str], Tuple[bool, List[str]]]] = None,
        installed_probe: Optional[Callable[[], Tuple[bool, Optional[Path], Optional[Path]]]] = None,
        starter: Optional[Callable[[Optional[Path], Optional[Path]], Tuple[bool, Optional[subprocess.Popen], str]]] = None
    ):
        self._http_probe = http_probe or probe_http_ollama
        self._installed_probe = installed_probe or probe_installed_ollama
        self._starter = starter or start_ollama_process
        self.last_state: OllamaState = OllamaState.NOT_INSTALLED
        self.cli_exe_path: Optional[Path] = None
        self.app_exe_path: Optional[Path] = None
        self.installed_models: List[str] = []

    def evaluate(self, base_url: Optional[str] = None, target_model: str = "phi3:mini") -> OllamaState:
        """
        Evaluates current Ollama state:
        NOT_INSTALLED -> INSTALLED_NOT_RUNNING -> RUNNING_NO_MODEL -> READY
        """
        url = base_url or get_default_ollama_url()
        is_running, models = self._http_probe(url)
        self.installed_models = models

        if is_running:
            # Check if required model (e.g. phi3:mini) or variant exists
            clean_target = (target_model or "phi3:mini").lower().strip()
            # Match either exact tag (phi3:mini) or base name (phi3)
            base_target = clean_target.split(":")[0]
            has_model = any(
                clean_target == m or base_target == m or m.startswith(f"{base_target}:")
                for m in models
            )
            state = OllamaState.READY if has_model else OllamaState.RUNNING_NO_MODEL
            self.last_state = state
            return state

        # Check if Ollama is installed on the machine
        is_installed, cli_p, app_p = self._installed_probe()
        self.cli_exe_path = cli_p
        self.app_exe_path = app_p

        state = OllamaState.INSTALLED_NOT_RUNNING if is_installed else OllamaState.NOT_INSTALLED
        self.last_state = state
        return state

    def start(self) -> Tuple[bool, str]:
        """Attempts to start the installed Ollama service."""
        ok, proc, msg = self._starter(self.app_exe_path, self.cli_exe_path)
        return ok, msg


def check_free_disk_space(required_gb: float = 3.0) -> Tuple[bool, float]:
    """
    Checks free disk space where Ollama stores models (~/.ollama/models).
    Returns: (has_enough_space: bool, free_gb: float)
    """
    target_dir = Path.home() / ".ollama"
    if not target_dir.exists():
        target_dir = Path.home()
    try:
        usage = shutil.disk_usage(str(target_dir))
        free_gb = usage.free / (1024 ** 3)
        return free_gb >= required_gb, free_gb
    except Exception:
        return True, 10.0


def pull_ollama_model(
    base_url: Optional[str] = None,
    model_name: str = "phi3:mini",
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    cancel_event: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Pulls an Ollama model using Ollama's official streaming API:
    POST /api/pull with {"name": model_name, "stream": true}
    Supports progress tracking, speed estimation, cancellation, and free disk space check.
    """
    has_space, free_gb = check_free_disk_space(3.0)
    if not has_space:
        return False, f"Low disk space: {free_gb:.1f} GB available, need at least 3.0 GB."

    url = (base_url or get_default_ollama_url()).rstrip("/") + "/api/pull"
    headers = {"User-Agent": GHOSTLINE_USER_AGENT, "Content-Type": "application/json"}
    payload = {"name": model_name, "stream": True}

    try:
        with requests.post(url, json=payload, headers=headers, stream=True, timeout=10.0) as resp:
            if resp.status_code != 200:
                return False, f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}"

            for line in resp.iter_lines(decode_unicode=True):
                if cancel_event and cancel_event.is_set():
                    return False, "Download cancelled by user."
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    status = data.get("status", "")
                    total = data.get("total", 0)
                    completed = data.get("completed", 0)
                    if progress_callback:
                        progress_callback(status, completed, total)
                    if "error" in data:
                        return False, str(data["error"])
                except Exception:
                    pass

        return True, f"Model {model_name} downloaded successfully."
    except Exception as e:
        return False, f"Failed to download model: {e}"
