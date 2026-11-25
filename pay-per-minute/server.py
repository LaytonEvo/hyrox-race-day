#!/usr/bin/env python3
"""Serve the Pay Per Minute site and keep data.json fresh from the FPL API.

Railway runs this with PORT set. Rebuilds on start, then every REFRESH_HOURS (default 6).
If a rebuild fails, the last good data.json keeps being served.
"""
import functools, http.server, os, pathlib, threading, time, traceback

import build

HERE = pathlib.Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8080"))
REFRESH_SECONDS = float(os.environ.get("REFRESH_HOURS", "6")) * 3600


def refresh_forever():
    while True:
        try:
            build.main([])
        except Exception:
            traceback.print_exc()
        time.sleep(REFRESH_SECONDS)


class Handler(http.server.SimpleHTTPRequestHandler):
    PUBLIC = {"/", "/index.html", "/data.json"}

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(b"ok"); return
        if path not in self.PUBLIC:
            self.send_error(404); return
        super().do_GET()

    def end_headers(self):
        if self.path.split("?", 1)[0] == "/data.json":
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    threading.Thread(target=refresh_forever, daemon=True).start()
    handler = functools.partial(Handler, directory=str(HERE))
    with http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler) as httpd:
        print(f"Serving on :{PORT}", flush=True)
        httpd.serve_forever()
