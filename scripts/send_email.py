"""Email the JSON test report after every CI run.

Usage: python scripts/send_email.py <test-report.json>
Env (from CI secrets):
  SMTP_USERNAME    sender account, e.g. you@gmail.com
  SMTP_PASSWORD    app password for that account
  REPORT_EMAIL_TO  recipient(s), comma-separated
  SMTP_SERVER      default smtp.gmail.com
  SMTP_PORT        default 465 (SSL); use 587 for STARTTLS
"""
import html
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage


def first_line(text):
    return text.strip().splitlines()[0] if text and text.strip() else ""


def build_message(report, sender, recipients):
    s = report["summary"]
    status = report["overall_status"].upper()
    sha = str(report.get("commit_sha", ""))
    run_url = report.get("pipeline_run_url") or "-"

    msg = EmailMessage()
    msg["Subject"] = (
        f"[{status}] {report['repository']} @ {sha[:7]}: "
        f"{s['passed']}/{s['total']} tests passed"
    )
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    # Plain-text version
    lines = [
        f"Test report: {status}",
        "",
        f"Repository : {report['repository']}",
        f"Branch     : {report['branch']}",
        f"Commit     : {sha}",
        f"Run ID     : {report['pipeline_run_id']} (run #{report['pipeline_run_number']})",
        f"Run URL    : {run_url}",
        f"Executed   : {report['execution_timestamp']}",
        "",
        f"Total: {s['total']} | Passed: {s['passed']} | Failed: {s['failed']}",
        "",
        "Individual results:",
    ]
    for t in report["tests"]:
        lines.append(f"  [{t['result'].upper()}] {t['name']}")
        if t.get("failure_message"):
            lines.append(f"      -> {first_line(t['failure_message'])}")
    lines += ["", "The full report is attached as test-report.json."]
    msg.set_content("\n".join(lines))

    # HTML version (what most mail apps show)
    color = "#1a7f37" if report["overall_status"] == "passed" else "#cf222e"
    cell = "padding:6px 10px;border:1px solid #d0d7de;text-align:left"
    rows = []
    for t in report["tests"]:
        rows.append(
            "<tr>"
            f"<td style='{cell}'><code>{html.escape(t['name'])}</code></td>"
            f"<td style='{cell}'>{html.escape(t['result'])}</td>"
            f"<td style='{cell}'>{html.escape(first_line(t.get('failure_message') or ''))}</td>"
            "</tr>"
        )
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#1f2328">
  <h2 style="color:{color}">Test report: {status}</h2>
  <p>
    <b>Repository:</b> {html.escape(report['repository'])}<br>
    <b>Branch:</b> {html.escape(report['branch'])}<br>
    <b>Commit:</b> <code>{html.escape(sha)}</code><br>
    <b>Run:</b> <a href="{html.escape(run_url)}">{html.escape(str(report['pipeline_run_id']))}</a>
    (run #{html.escape(str(report['pipeline_run_number']))})<br>
    <b>Executed:</b> {html.escape(report['execution_timestamp'])}
  </p>
  <p><b>Total:</b> {s['total']} &nbsp; <b>Passed:</b> {s['passed']} &nbsp; <b>Failed:</b> {s['failed']}</p>
  <table style="border-collapse:collapse">
    <tr><th style='{cell}'>Test</th><th style='{cell}'>Result</th><th style='{cell}'>Failure message</th></tr>
    {''.join(rows)}
  </table>
  <p>The full report is attached as <code>test-report.json</code>.</p>
</body></html>
"""
    msg.add_alternative(html_body, subtype="html")

    # Attach the full JSON report
    msg.add_attachment(
        json.dumps(report, indent=2).encode("utf-8"),
        maintype="application",
        subtype="json",
        filename="test-report.json",
    )
    return msg


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/send_email.py <test-report.json>")
        sys.exit(2)

    user = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").replace(" ", "")
    recipients = [a.strip() for a in os.environ.get("REPORT_EMAIL_TO", "").split(",") if a.strip()]
    if not (user and password and recipients):
        print("::warning::Email secrets (SMTP_USERNAME, SMTP_PASSWORD, REPORT_EMAIL_TO) "
              "are not set; skipping email.")
        return

    with open(sys.argv[1], encoding="utf-8") as f:
        report = json.load(f)
    msg = build_message(report, user, recipients)

    server = os.environ.get("SMTP_SERVER") or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT") or "465")
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(server, port, context=context, timeout=30) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(server, port, timeout=30) as smtp:
            smtp.starttls(context=context)
            smtp.login(user, password)
            smtp.send_message(msg)
    print(f"Email sent to {', '.join(recipients)} "
          f"({report['overall_status'].upper()})")


if __name__ == "__main__":
    main()