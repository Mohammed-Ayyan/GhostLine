import os
import sys
import time
import json
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

class RangeRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler supporting Accept-Ranges and 206 Partial Content."""
    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None
        
        ctype = self.guess_type(path)
        fs = os.fstat(f.fileno())
        size = fs.st_size
        
        range_header = self.headers.get('Range')
        if range_header and range_header.startswith('bytes=') and ',' not in range_header:
            parts = range_header.strip().split('=')[1].split('-')
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else size - 1
            if start >= size or end >= size or start > end:
                self.send_error(416, "Requested range not satisfiable")
                f.close()
                return None
            
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            f.seek(start)
            return f
        
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    def do_GET(self):
        f = self.send_head()
        if f:
            try:
                self.copyfile(f, self.wfile)
            except (ConnectionResetError, BrokenPipeError):
                pass
            finally:
                f.close()

def run_tests():
    website_dir = os.path.abspath("website")
    handler = lambda *args: RangeRequestHandler(*args, directory=website_dir)
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    base_url = f"http://127.0.0.1:{port}"
    results = {}
    
    with sync_playwright() as p:
        browsers = []
        for b in ['chromium', 'firefox', 'webkit']:
            try:
                inst = getattr(p, b).launch(headless=True)
                browsers.append((b, inst))
            except Exception as e:
                results[f"{b}_launch"] = f"Unavailable: {str(e)[:120]}"
        
        for browser_name, browser in browsers:
            # Test desktop and mobile
            test_devices = [
                ('desktop', {'viewport': {'width': 1440, 'height': 900}, 'user_agent': None}),
                ('mobile_iphone', p.devices['iPhone 13']),
                ('mobile_pixel', p.devices['Pixel 5']),
            ]
            for mode, dev_config in test_devices:
                key = f"{browser_name}_{mode}"
                context = browser.new_context(**dev_config)
                page = context.new_page()
                
                req_errors = []
                page.on("requestfailed", lambda req: req_errors.append(f"{req.url}: {req.failure}"))
                
                page.goto(f"{base_url}/index.html", wait_until="networkidle")
                
                video_state = page.evaluate("""() => {
                    const v = document.querySelector('video.main-video-player');
                    if (!v) return { exists: false };
                    return {
                        exists: true,
                        currentSrc: v.currentSrc,
                        readyState: v.readyState,
                        networkState: v.networkState,
                        paused: v.paused,
                        currentTime: v.currentTime,
                        duration: v.duration,
                        videoWidth: v.videoWidth,
                        videoHeight: v.videoHeight,
                        error: v.error ? { code: v.error.code, message: v.error.message } : null
                    };
                }""")
                
                play_res = page.evaluate("""async () => {
                    const v = document.querySelector('video.main-video-player');
                    if (!v) return { play_error: 'no video' };
                    try {
                        v.muted = true;
                        const p = v.play();
                        if (p !== undefined) {
                            await p;
                        }
                        await new Promise(r => setTimeout(r, 1200));
                        return {
                            playing: !v.paused,
                            currentTime: v.currentTime,
                            readyStateAfterPlay: v.readyState,
                            error: v.error ? { code: v.error.code, message: v.error.message } : null
                        };
                    } catch (err) {
                        return { play_error: String(err) };
                    }
                }""")
                
                track_state = page.evaluate("""() => {
                    const v = document.querySelector('video.main-video-player');
                    if (!v || !v.textTracks || v.textTracks.length === 0) return { tracks: 0 };
                    const t = v.textTracks[0];
                    return {
                        tracks: v.textTracks.length,
                        kind: t.kind,
                        label: t.label,
                        mode: t.mode,
                        cues: t.cues ? t.cues.length : 0
                    };
                }""")
                
                results[key] = {
                    'video_state': video_state,
                    'play_res': play_res,
                    'track_state': track_state,
                    'req_errors': req_errors
                }
                context.close()
            browser.close()
    
    server.shutdown()
    with open('reports/run10/forensic_playwright.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    run_tests()
