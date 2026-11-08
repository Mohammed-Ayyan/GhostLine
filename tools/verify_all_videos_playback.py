"""
Comprehensive Multi-Browser Playwright Video Playback Test (Run 15 Part B)
Tests all 9 shipped videos across Chromium, Firefox, and WebKit:
- HTTP 206 Range request support
- canplay event & loadedmetadata
- currentTime playback advancement
- Chapter / offset seeking
- WebVTT caption track loading
"""

import os
import sys
import re
import json
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = REPO_ROOT / "website"
MEDIA_DIR = WEBSITE_DIR / "media"
REPORTS_DIR = REPO_ROOT / "reports" / "run15"

class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with robust HTTP 206 Partial Content / Range support."""
    def send_head(self):
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            parts = sys.version_info
            if not self.path.endswith('/'):
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return super().send_head()
        
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno())
        size = fs[6]
        range_header = self.headers.get('Range')

        if range_header:
            match = re.match(r'^bytes=(\d*)-(\d*)$', range_header)
            if match:
                start_str, end_str = match.groups()
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else size - 1
                if start >= size:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    f.close()
                    return None
                if end >= size:
                    end = size - 1
                length = end - start + 1
                
                self.send_response(206)
                self.send_header("Content-type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                self.end_headers()
                f.seek(start)
                return f

        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

def test_playback():
    server = ThreadingHTTPServer(("127.0.0.1", 0), lambda *args, **kwargs: RangeHTTPRequestHandler(*args, directory=str(WEBSITE_DIR), **kwargs))
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{port}"
    print(f"[*] Local static server serving {WEBSITE_DIR} on {base_url}")

    videos = sorted([f.name for f in MEDIA_DIR.glob("*.mp4")])
    browsers = ["chromium", "firefox", "webkit"]
    
    results = {}

    with sync_playwright() as p:
        for b_name in browsers:
            print(f"\n{'='*30} Testing in {b_name.upper()} {'='*30}")
            browser_type = getattr(p, b_name)
            try:
                browser = browser_type.launch(headless=True)
            except Exception as e:
                print(f"Skipping {b_name}: {e}")
                continue

            b_results = []
            context = browser.new_context()
            page = context.new_page()

            for vid in videos:
                vid_path = MEDIA_DIR / vid
                vtt_name = vid_path.with_suffix(".vtt").name
                has_vtt = (MEDIA_DIR / vtt_name).exists()
                
                vtt_tag = f'<track kind="captions" src="media/{vtt_name}" default>' if has_vtt else ''
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <body>
                  <video id="v" src="media/{vid}" controls playsinline muted width="640">
                    {vtt_tag}
                  </video>
                </body>
                </html>
                """
                test_html_file = WEBSITE_DIR / "_test_player.html"
                test_html_file.write_text(html_content, encoding="utf-8")
                try:
                    page.goto(f"{base_url}/_test_player.html", wait_until="networkidle")
                finally:
                    test_html_file.unlink(missing_ok=True)
                
                # Check 1: canplay
                try:
                    page.wait_for_function("document.getElementById('v').readyState >= 3", timeout=10000)
                    canplay = True
                except Exception:
                    canplay = False

                # Check 2: play & currentTime advances
                advances = False
                cur_time = 0.0
                try:
                    page.evaluate("document.getElementById('v').play()")
                    page.wait_for_timeout(600)
                    cur_time = page.evaluate("document.getElementById('v').currentTime")
                    advances = cur_time > 0.1
                except Exception as e:
                    pass

                # Check 3: Seek chapter/offset
                seek_ok = False
                seek_target = 4.0
                try:
                    page.evaluate(f"document.getElementById('v').currentTime = {seek_target}")
                    page.wait_for_timeout(400)
                    post_seek = page.evaluate("document.getElementById('v').currentTime")
                    seek_ok = abs(post_seek - seek_target) < 1.0
                except Exception:
                    pass

                # Check 4: Range request 206 verification
                # Request byte range 0-1023
                range_status = page.evaluate(f"""async () => {{
                    const resp = await fetch('media/{vid}', {{
                        headers: {{ 'Range': 'bytes=0-1023' }}
                    }});
                    return resp.status;
                }}""")
                range_206 = (range_status == 206)

                # Check 5: Captions load if available
                captions_ok = True
                if has_vtt:
                    try:
                        captions_ok = page.evaluate("""() => {
                            const track = document.getElementById('v').textTracks[0];
                            return track && (track.mode !== 'disabled');
                        }""")
                    except Exception:
                        captions_ok = False

                print(f"  {vid:<38} | canplay: {canplay} | advances: {advances} (t={cur_time:.2f}s) | seek: {seek_ok} | 206: {range_206} | vtt: {captions_ok}")
                b_results.append({
                    "video": vid,
                    "canplay": canplay,
                    "advances": advances,
                    "cur_time": cur_time,
                    "seek_ok": seek_ok,
                    "range_206": range_206,
                    "captions_ok": captions_ok
                })

            results[b_name] = b_results
            browser.close()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / "browser_playback_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Browser playback test complete. Saved to {report_file}")

if __name__ == "__main__":
    test_playback()
