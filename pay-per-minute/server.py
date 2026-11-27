#!/usr/bin/env python3
"""Serve the Pay Per Minute site and keep it fresh from the FPL API.

Railway runs this with PORT set. On start, and then every REFRESH_HOURS (default 6), it
rebuilds data.json and re-renders every page into site/. If a refresh fails, the pages from
the last good build keep being served; on a cold start it renders from the committed data.json.
"""
import functools, http.server, os, pathlib, threading, time, traceback

import build
import site_pages

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE / "site"
PORT = int(os.environ.get("PORT", "8080"))
REFRESH_SECONDS = float(os.environ.get("REFRESH_HOURS", "6")) * 3600


def refresh_once():
    try:
        build.main([], render=True)
        return True
    except Exception:
        traceback.print_exc()
        return False


def refresh_forever():
    while True:
        time.sleep(REFRESH_SECONDS)
        refresh_once()


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(b"ok"); return
        super().do_GET()

    def do_HEAD(self):
        super().do_HEAD()

    def end_headers(self):
        path = self.path.split("?", 1)[0]
        if path == "/data.json":
            self.send_header("Cache-Control", "no-cache")
        elif path.endswith("/") or path.endswith(".html"):
            self.send_header("Cache-Control", "public, max-age=300")
        super().end_headers()

    def log_message(self, fmt, *args):  # keep Railway logs readable: skip health checks
        if "/health" not in str(args[0] if args else ""):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    if not refresh_once():
        site_pages.render()  # FPL unreachable: serve pages built from the committed data.json
    threading.Thread(target=refresh_forever, daemon=True).start()
    handler = functools.partial(Handler, directory=str(SITE))
    with http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler) as httpd:
        print(f"Serving on :{PORT}", flush=True)
        httpd.serve_forever()
