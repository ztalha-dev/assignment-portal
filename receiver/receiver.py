"""Local HTTP receiver: accepts the CI test report and saves it as testreport.json.

Run:  python receiver/receiver.py
Env:  RECEIVER_PORT (default 5001), RECEIVER_HOST (default 127.0.0.1),
      RECEIVER_TOKEN (shared secret; if set, requests must send X-Report-Token),
      REPORT_PATH (default: <project folder>/testreport.json)
"""
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.environ.get("RECEIVER_HOST", "127.0.0.1")
PORT = int(os.environ.get("RECEIVER_PORT", "5001"))
TOKEN = os.environ.get("RECEIVER_TOKEN", "")
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "testreport.json"
REPORT_PATH = Path(os.environ.get("REPORT_PATH", DEFAULT_PATH))
MAX_BODY_BYTES = 1_000_000


class ReportHandler(BaseHTTPRequestHandler):
    def _reply(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._reply(200, {"status": "ok", "report_path": str(REPORT_PATH)})
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/report":
            return self._reply(404, {"error": "not found"})
        if TOKEN and self.headers.get("X-Report-Token") != TOKEN:
            return self._reply(401, {"error": "invalid or missing token"})

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            return self._reply(400, {"error": "missing or oversized body"})
        try:
            report = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self._reply(400, {"error": "body is not valid JSON"})
        if not isinstance(report, dict) or "summary" not in report or "tests" not in report:
            return self._reply(400, {"error": "body is not a test report"})

        report["received_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        temp_path = REPORT_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        os.replace(temp_path, REPORT_PATH)  # atomic: never leaves a half-written file

        s = report["summary"]
        print(
            f"\n>>> Report saved: commit {str(report.get('commit_sha'))[:7]} | "
            f"{str(report.get('overall_status')).upper()} | "
            f"{s.get('passed')}/{s.get('total')} passed, {s.get('failed')} failed\n"
            f"    -> {REPORT_PATH}\n",
            flush=True,
        )
        self._reply(200, {"status": "saved", "path": str(REPORT_PATH)})


def main():
    server = ThreadingHTTPServer((HOST, PORT), ReportHandler)
    print(f"Receiver listening on http://localhost:{PORT}/report")
    print(f"Reports will be saved to {REPORT_PATH}")
    if not TOKEN:
        print("Note: RECEIVER_TOKEN is not set, so any request is accepted.")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()