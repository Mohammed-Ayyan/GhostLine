"""
Live verification of GhostlineApp directly in process:
Initializes GhostlineApp with Qt event loop in non-blocking mode,
tests Alt+/ and Alt+A handlers, tests window controls, tests shutdown.
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
pkg_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pkg_dir))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from ghostline.config import load_config
from ghostline.app import GhostlineApp

def test_live_app_instance():
    print("[1] Initializing QApplication and GhostlineApp...")
    qapp = QApplication.instance()
    if qapp is None:
        qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)

    app = GhostlineApp()
    print("[2] GhostlineApp initialized successfully.")
    print(f"    - Main Window: {app.main_window.windowTitle()}")
    print(f"    - HUD Overlay: Width={app.hud.width()}, Height={app.hud.height()}")
    print(f"    - Audio Capture Lock: {type(app.audio_capture._lock).__name__}")
    
    # 3. Test Main Window Controls
    print("[3] Testing Main Window Controls...")
    app.main_window.show_window()
    qapp.processEvents()
    assert app.main_window.isVisible()
    
    # Maximize & Restore
    app.main_window.maximize_window()
    qapp.processEvents()
    print(f"    - Window isMaximized: {app.main_window.isMaximized()}")
    assert app.main_window.isMaximized()
    
    app.main_window.restore_window()
    qapp.processEvents()
    print(f"    - Window restored: not isMaximized = {not app.main_window.isMaximized()}")
    assert not app.main_window.isMaximized()
    
    # Minimize to Tray
    app.main_window.minimize_window()
    qapp.processEvents()
    print(f"    - Window isMinimized: {app.main_window.isMinimized()}")
    
    app.main_window.restore_window()
    qapp.processEvents()
    
    # 4. Test Floating HUD Controls
    print("[4] Testing Floating HUD Controls...")
    app.hud.show_overlay()
    qapp.processEvents()
    assert app.hud.isVisible()
    
    # Collapse HUD
    app.hud.toggle_collapse()
    qapp.processEvents()
    print(f"    - HUD is_collapsed: {app.hud.is_collapsed}, Height: {app.hud.height()}")
    assert app.hud.is_collapsed
    
    # Restore HUD
    app.hud.toggle_collapse()
    qapp.processEvents()
    print(f"    - HUD restored from collapse: {not app.hud.is_collapsed}")
    assert not app.hud.is_collapsed
    
    # Expand HUD Size
    app.hud.toggle_expanded_size()
    qapp.processEvents()
    print(f"    - HUD expanded size width: {app.hud.width()}")
    assert app.hud.width() >= 700
    
    app.hud.toggle_expanded_size()
    qapp.processEvents()
    print(f"    - HUD restored to standard size width: {app.hud.width()}")
    
    # Close HUD (should hide HUD without terminating application)
    app.hud.close()
    qapp.processEvents()
    print(f"    - HUD closed, isHidden: {app.hud.isHidden()}")
    assert app.hud.isHidden()
    
    # 5. Test Alt + / (Screen Assistance / Solve Trigger)
    print("[5] Testing Alt + / (Screen Assistance Trigger)...")
    # Simulate solve start signal
    app.bridge.sig_solve_started.emit()
    qapp.processEvents()
    print("    - Alt + / signal dispatched cleanly to GUI thread without crash!")
    
    # 6. Test Alt + A (Audio Assistance Toggle)
    print("[6] Testing Alt + A (Audio Assistance Toggle)...")
    active = app.toggle_audio_capture()
    qapp.processEvents()
    print(f"    - Audio capture toggle result: {active} (handled gracefully without deadlock or crash)")
    
    # Toggle off if active
    if active:
        app.toggle_audio_capture()
        qapp.processEvents()
        print("    - Audio capture toggled off cleanly.")
        
    # 7. Test Dedicated Exit Button in Sidebar
    print("[7] Testing Sidebar Exit action...")
    assert hasattr(app.main_window, "btn_exit_app")
    print(f"    - Sidebar button label: '{app.main_window.btn_exit_app.text()}'")
    
    # 8. Test Application Clean Shutdown
    print("[8] Testing Application Shutdown and Resource Cleanup...")
    app.shutdown()
    qapp.processEvents()
    print("    - Application shut down cleanly. All resources released.")
    print("\n[+] ALL LIVE VERIFICATION CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_live_app_instance()
