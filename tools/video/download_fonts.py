import os
import urllib.request

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

# Sources for unsubsetted open-license TTF files
FONT_URLS = {
    # Inter (SIL Open Font License 1.1) from Google Fonts / rsms official release
    "Inter-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    "Inter-Bold.ttf": "https://raw.githubusercontent.com/rsms/inter/master/docs/font-files/Inter-Bold.ttf",
    "Inter-SemiBold.ttf": "https://raw.githubusercontent.com/rsms/inter/master/docs/font-files/Inter-SemiBold.ttf",
    "Inter-Medium.ttf": "https://raw.githubusercontent.com/rsms/inter/master/docs/font-files/Inter-Medium.ttf",
    "OFL-Inter.txt": "https://raw.githubusercontent.com/rsms/inter/master/LICENSE.txt",

    # JetBrains Mono (OFL 1.1)
    "JetBrainsMono-Regular.ttf": "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-Regular.ttf",
    "JetBrainsMono-Bold.ttf": "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-Bold.ttf",
    "OFL-JetBrainsMono.txt": "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/OFL.txt"
}

print(f"Downloading bundled fonts to {FONTS_DIR}...")
for fname, url in FONT_URLS.items():
    dest = os.path.join(FONTS_DIR, fname)
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        print(f"  [OK] {fname} already exists ({os.path.getsize(dest)} bytes)")
        continue
    print(f"  Downloading {fname} from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Ghostline/1.0 (Windows)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp, open(dest, "wb") as out:
            out.write(resp.read())
        print(f"  [+] Saved {fname} ({os.path.getsize(dest)} bytes)")
    except Exception as e:
        print(f"  [-] Failed to download {fname}: {e}")

print("Font download finished.")

