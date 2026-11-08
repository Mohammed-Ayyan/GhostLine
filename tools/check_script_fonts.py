import re

with open("tools/build_run10_videos.py", encoding="utf-8") as f:
    text = f.read()

fonts = set(re.findall(r'QFont\(\s*["\']([^"\']+)["\']', text))
print("Fonts found:", sorted(fonts))

