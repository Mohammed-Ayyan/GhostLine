import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict, model_validator

class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # AI Provider & BYOK Configuration
    ai_provider: str = Field(default="ollama", description="Active AI provider: 'ollama', 'gemini', 'groq', 'openrouter', 'openai', 'anthropic', 'xai'")
    model_name: str = Field(default="phi3:mini", description="Ollama model to use for reasoning (or fallback model)")
    ollama_url: str = Field(default="http://127.0.0.1:11434", description="Local Ollama daemon REST endpoint")
    provider_models: Dict[str, str] = Field(
        default_factory=lambda: {
            "ollama": "phi3:mini",
            "gemini": "gemini-1.5-flash",
            "groq": "llama-3.3-70b-versatile",
            "openrouter": "meta-llama/llama-3.3-70b-instruct",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-haiku-20241022",
            "xai": "grok-2-1212"
        },
        description="Per-provider selected model names"
    )
    provider_base_urls: Dict[str, str] = Field(
        default_factory=lambda: {
            "ollama": "http://127.0.0.1:11434",
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "openai": "https://api.openai.com/v1",
            "xai": "https://api.x.ai/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "gemini": "https://generativelanguage.googleapis.com"
        },
        description="Per-provider base URL endpoints"
    )
    fallback_to_ollama: bool = Field(default=True, description="Fallback to local Ollama if cloud provider request fails")
    # Screen Capture & Diagnostic Configuration
    capture_mode: str = Field(default="cursor", description="Capture mode: 'cursor', 'full_screen', 'active_window', 'cursor_monitor', or 'primary_monitor'")
    capture_width: int = Field(default=1400, description="Bounding box capture width in pixels (for cursor mode)")
    capture_height: int = Field(default=900, description="Bounding box capture height in pixels (for cursor mode)")
    diagnostic_mode: bool = Field(default=False, description="Enable diagnostic preview dumps and telemetry artifacts")
    debug_dump_enabled: bool = Field(default=False, description="Enable dumping every stage of solve to %APPDATA%/Ghostline/debug/<timestamp>/ (diagnostics only)")
    save_history: bool = Field(default=True, description="Enable interaction history recording across screen solves and audio conversations")
    history_retention_days: int = Field(default=30, description="Retention window for history entries in days (0 = keep indefinitely)")
    confirmed_custom_hosts: List[str] = Field(default_factory=list, description="User-confirmed custom hostnames for BYOK API key transmission")
    ocr_contrast_enhancement: bool = Field(default=True, description="Enable automatic adaptive contrast enhancement for low-contrast captures")
    ocr_deskewing: bool = Field(default=True, description="Enable automatic rotation deskewing when skewed text angle is detected")
    hotkey: str = Field(default="alt+/", description="Global hotkey to trigger solve")
    indicator_mode: str = Field(default="both", description="Indicator mode: 'hud', 'tray', or 'both'")
    hud_opacity: float = Field(default=0.95, description="HUD opacity (0.5 to 1.0)")
    auto_copy_answer: bool = Field(default=False, description="Automatically copy answer to clipboard")
    save_history_locally: bool = Field(default=True, description="Save audit log of queries locally")
    caps_lock_indicator: bool = Field(default=False, description="Enable Caps Lock LED pulse indicator")
    caps_pulse_on_ms: int = Field(default=300, description="Caps Lock LED pulse ON duration in milliseconds")
    caps_pulse_off_ms: int = Field(default=250, description="Caps Lock LED pulse OFF duration between blinks in milliseconds")
    caps_sequence_cooldown_ms: int = Field(default=700, description="Caps Lock LED pulse sequence cooldown in milliseconds")
    show_hud_on_solve: bool = Field(default=False, description="Show HUD automatically after a scan")
    hotkey_hud_toggle: str = Field(default="alt+t", description="Global hotkey to toggle HUD overlay")
    hotkey_quit: str = Field(default="ctrl+alt+q", description="Global hotkey to cleanly terminate Ghostline")

    # Quiet Notification Channels
    quiet_taskbar_flash: bool = Field(default=True, description="Flash taskbar button when answer is ready")
    quiet_taskbar_badge: bool = Field(default=True, description="Show overlay icon badge on taskbar with answer")
    quiet_tray_notification: bool = Field(default=False, description="Show system tray balloon notification when answer is ready")
    quiet_hardware_signal: bool = Field(default=False, description="Signal answer ready via hardware LED/backlight pulse")

    # First Run Experience
    first_run_complete: bool = Field(default=False, description="Whether first-run welcome and hotkey introduction has been shown")

    # Software Dimming
    enable_software_dimming: bool = Field(default=False, description="Software dimming via gamma ramp if hardware unsupported")

    start_minimized: bool = Field(default=False, description="Start application minimized to system tray")
    hide_from_taskbar: bool = Field(default=False, description="Hide main window from the Windows taskbar")
    start_ollama_with_ghostline: bool = Field(default=True, description="Start Ollama automatically when Ghostline starts if installed")
    stop_ollama_on_exit: bool = Field(default=False, description="Stop Ollama when Ghostline quits (only if Ghostline started it)")
    tray_help_card_dismissed: bool = Field(default=False, description="Whether the system tray guidance card has been dismissed")
    minimize_to_tray: bool = Field(default=True, description="Minimize or hide main window to system tray when closed")
    show_tray_icon: bool = Field(default=True, description="Show system tray icon")
    start_with_windows: bool = Field(default=False, description="Launch Ghostline automatically on Windows login")
    tray_notifications: bool = Field(default=True, description="Enable system tray notifications")
    use_profile_in_screen: bool = Field(default=False, description="Also use personal profile grounding in screen solve")
    main_window_width: int = Field(default=960, description="Main window width in pixels")
    main_window_height: int = Field(default=680, description="Main window height in pixels")
    main_window_pos_x: Optional[int] = Field(default=None, description="Main window X position")
    main_window_pos_y: Optional[int] = Field(default=None, description="Main window Y position")
    main_window_maximized: bool = Field(default=False, description="Main window maximized state")
    custom_icon_path: Optional[str] = Field(default=None, description="Path to custom application icon (.ico, .png)")
    custom_icon_preset: str = Field(default="default", description="Active icon preset: 'default', 'stealth_dot', 'windows_utility', 'custom'")
    answer_timeout_sec: int = Field(default=0, description="Auto-dismiss timeout for floating answer HUD in seconds (0 = keep open until dismissed)")
    
    # Floating HUD & Positioning
    hud_enabled: bool = Field(default=True, description="Enable floating transparent HUD overlay")
    hud_opacity: float = Field(default=0.86, description="Floating HUD window opacity (0.50 to 1.00)")
    hud_width: int = Field(default=640, description="HUD window width in pixels")
    hud_height: int = Field(default=560, description="HUD window height in pixels")
    hud_max_width: int = Field(default=1200, description="HUD maximum width constraint in pixels")
    hud_max_height: int = Field(default=950, description="HUD maximum height constraint in pixels")
    hud_scroll_speed: int = Field(default=2, description="HUD mouse-wheel scrolling step multiplier")
    hud_pos_x: Optional[int] = Field(default=None, description="Persistent HUD X screen coordinate")
    hud_pos_y: Optional[int] = Field(default=None, description="Persistent HUD Y screen coordinate")
    hud_pinned: bool = Field(default=False, description="Pin HUD to persistent position")
    hud_always_on_top: bool = Field(default=True, description="Keep HUD above normal windows without stealing focus")
    exclude_from_capture: bool = Field(default=True, description="Exclude HUD from desktop screen captures via SetWindowDisplayAffinity")

    # Hardware Controls Configuration
    hw_brightness_step_pct: int = Field(default=5, description="Screen brightness change percentage per step (1-25)")
    hw_brightness_min_safe_pct: int = Field(default=5, description="Safe minimum screen brightness percentage to prevent blackout")
    hw_led_target: str = Field(default="caps_lock", description="Keyboard indicator LED target: 'caps_lock', 'num_lock', 'scroll_lock'")
    hw_flash_count: int = Field(default=3, description="Keyboard LED flash count: 1, 2, 3, 4, 5, 10")
    hw_flash_speed: str = Field(default="medium", description="Keyboard LED flash speed: 'slow', 'medium', 'fast'")
    hw_controls_collapsed: bool = Field(default=True, description="Whether the hardware controls drawer is collapsed in HUD overlay")
    
    # Automatic Hover-to-Answer
    hover_to_answer_enabled: bool = Field(default=False, description="Enable automatic question detection on cursor hover")
    hover_delay_ms: int = Field(default=800, description="Stationary hover delay in milliseconds before triggering capture")
    hover_cooldown_sec: float = Field(default=3.0, description="Cooldown in seconds between consecutive hover solves")
    hover_movement_threshold_px: int = Field(default=15, description="Cursor movement jitter tolerance in pixels")
    is_hover_paused: bool = Field(default=False, description="Pause/resume state for automatic hover detection")

    # Live Audio Capture & AI Assistance Configuration
    audio_enabled: bool = Field(default=False, description="Enable live audio capture and transcription")
    audio_source_system: bool = Field(default=True, description="Enable system audio / loopback capture (call participants)")
    audio_source_mic: bool = Field(default=True, description="Enable microphone capture (user speech)")
    audio_system_device_index: Optional[int] = Field(default=None, description="Audio device index for system loopback")
    audio_mic_device_index: Optional[int] = Field(default=None, description="Audio device index for microphone")
    audio_system_volume: float = Field(default=1.0, description="Volume multiplier for system loopback capture (0.0 to 2.0)")
    audio_mic_volume: float = Field(default=1.0, description="Volume multiplier for microphone capture (0.0 to 2.0)")
    audio_whisper_model: str = Field(default="tiny", description="Local Whisper model size: 'tiny', 'base', 'small', 'medium'")
    audio_language: str = Field(default="en", description="Spoken language code (e.g. 'en') or 'auto'")
    audio_chunk_sec: float = Field(default=3.0, description="Duration in seconds of rolling audio chunks")
    audio_context_turns: int = Field(default=12, description="Number of finalized turns retained for LLM conversation context")
    audio_auto_answer_questions: bool = Field(default=True, description="Automatically trigger Ollama assistance on detected conversation questions")
    audio_when_to_answer: str = Field(default="questions", description="When to trigger AI answer: 'questions', 'every_pause', 'manual'")
    audio_question_debounce_sec: float = Field(default=2.0, description="Debounce silence delay in seconds after a question before triggering inference")
    audio_hotkey_toggle: str = Field(default="alt+a", description="Global hotkey to toggle audio capture")
    audio_hotkey_ask: str = Field(default="alt+q", description="Global hotkey to trigger 'Ask Ghostline' on current conversation")
    save_audio_recordings: bool = Field(default=False, description="Save raw audio recordings (requires explicit destination)")
    audio_recording_path: Optional[str] = Field(default=None, description="Explicit directory to save raw audio recordings")
    transcript_retention_max_items: int = Field(default=200, description="Maximum transcript segments retained in rolling memory")


    @model_validator(mode="after")
    def sync_ollama_urls(self):
        if self.ollama_url and self.ollama_url != "http://127.0.0.1:11434":
            self.provider_base_urls["ollama"] = self.ollama_url
        elif self.provider_base_urls.get("ollama") and self.provider_base_urls["ollama"] != "http://127.0.0.1:11434":
            self.ollama_url = self.provider_base_urls["ollama"]
        return self

APP_NAME = "Ghostline"

LEGACY_APP_NAME = "Rubric"

def get_app_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        path = Path(app_data) / APP_NAME
    else:
        path = Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_config_path() -> Path:
    # 1. Check for project-local config.json if present
    project_cfg = Path(__file__).resolve().parent.parent / "config.json"
    if project_cfg.exists():
        return project_cfg
    # 2. Check standard APPDATA path
    return get_app_dir() / "config.json"

def _sync_msix_appdata():
    """
    On Windows with Microsoft Store Python (MSIX), %APPDATA% reads and writes
    are isolated into %LOCALAPPDATA%\\Packages\\PythonSoftwareFoundation.*\\LocalCache\\Roaming.
    If the user modifies the unvirtualized %APPDATA%\\Ghostline\\config.json directly,
    Store Python would otherwise read a stale LocalCache copy.
    This helper reads the real file via cmd.exe type and synchronizes LocalCache.
    """
    if os.name != "nt":
        return
    try:
        app_data = os.environ.get("APPDATA")
        if not app_data:
            return
        real_config = Path(app_data) / APP_NAME / "config.json"
        if not real_config.exists():
            legacy_real_config = Path(app_data) / LEGACY_APP_NAME / "config.json"
            if legacy_real_config.exists():
                real_config = legacy_real_config
        
        # Read the real file via cmd.exe to bypass MSIX file virtualization if direct read fails
        real_data = None
        try:
            with open(real_config, "r", encoding="utf-8") as f:
                real_data = json.load(f)
        except Exception:
            pass

        if real_data is None:
            import subprocess
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
            startupinfo.wShowWindow = 0  # SW_HIDE
            res = subprocess.run(
                ["cmd.exe", "/c", "type", f'"{real_config}"'],
                capture_output=True,
                text=True,
                timeout=1,
                creationflags=creationflags,
                startupinfo=startupinfo,
            )
            if res.returncode == 0 and res.stdout.strip():
                try:
                    real_data = json.loads(res.stdout)
                except Exception:
                    real_data = None

        if real_data:
            cfg_path = get_config_path()
            # If cfg_path is not project-local, synchronize the virtualized copy
            if cfg_path != Path(__file__).resolve().parent.parent / "config.json":
                need_write = True
                if cfg_path.exists():
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            current = json.load(f)
                        if current == real_data:
                            need_write = False
                    except Exception:
                        pass
                if need_write:
                    cfg_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(cfg_path, "w", encoding="utf-8") as f:
                        json.dump(real_data, f, indent=2)
    except Exception:
        pass

def load_config(custom_path: Optional[Path] = None, path: Optional[Path] = None) -> AppConfig:
    effective_path = custom_path or path
    if effective_path is None:
        _sync_msix_appdata()
        config_path = get_config_path()
    else:
        config_path = effective_path

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig(**data)
        except Exception:
            pass
    config = AppConfig()
    save_config(config, custom_path=config_path)
    return config

def save_config(config: AppConfig, custom_path: Optional[Path] = None, path: Optional[Path] = None) -> None:
    config_path = custom_path or path or get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            pass
    os.replace(temp_path, config_path)

    # If running on Windows Store Python, also mirror to real APPDATA
    if os.name == "nt" and custom_path is None:
        try:
            app_data = os.environ.get("APPDATA")
            if app_data:
                real_config = Path(app_data) / APP_NAME / "config.json"
                if config_path != real_config:
                    copied = False
                    try:
                        import shutil
                        real_config.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(config_path, real_config)
                        copied = True
                    except Exception:
                        pass
                    if not copied:
                        import subprocess
                        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
                        startupinfo.wShowWindow = 0  # SW_HIDE
                        subprocess.run(
                            ["cmd.exe", "/c", "copy", "/y", f'"{config_path}"', f'"{real_config}"'],
                            capture_output=True,
                            timeout=1,
                            creationflags=creationflags,
                            startupinfo=startupinfo,
                        )
        except Exception:
            pass

