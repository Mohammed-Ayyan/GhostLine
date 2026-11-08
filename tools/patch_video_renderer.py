with open("tools/build_run10_videos.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add init_qt_fonts
old_init = "_app = QApplication.instance() or QApplication(sys.argv)"
new_init = """_app = QApplication.instance() or QApplication(sys.argv)
from tools.video.font_guard import init_qt_fonts
init_qt_fonts(_app)"""

if "init_qt_fonts" not in content:
    assert old_init in content, "old_init not found"
    content = content.replace(old_init, new_init, 1)

# Replace font names
content = content.replace('"Segoe UI Variable Display"', '"Inter"')
content = content.replace('"Segoe UI"', '"Inter"')
content = content.replace('"Consolas"', '"JetBrains Mono"')

with open("tools/build_run10_videos.py", "w", encoding="utf-8") as f:
    f.write(content)

print("[+] Successfully patched tools/build_run10_videos.py with FontGuard and Inter / JetBrains Mono.")

