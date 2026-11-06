"""Build the JSON test report from pytest's JUnit XML and the CI environment.

Usage: python scripts/build_report.py <junit.xml> <output.json>
"""
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

MAX_MESSAGE = 2000


def env(name, default="local"):
    """Read a GitHub Actions variable; fall back to 'local' when run on your PC."""
    return os.environ.get(name) or default


def parse_junit(path):
    """Return (list_of_test_results, problem_message_or_None)."""
    if not os.path.exists(path):
        return [], f"No test results found at {path}; the test stage crashed before tests ran."

    tests = []
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        result, message = "passed", None
        for tag, outcome in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
            node = case.find(tag)
            if node is not None:
                result = outcome
                if outcome in ("failed", "error"):
                    text = (node.get("message") or node.text or "").strip()
                    message = text[:MAX_MESSAGE] or "Test failed without a message."
                break
        tests.append({
            "name": case.get("name", "unknown"),
            "classname": case.get("classname", ""),
            "result": result,
            "duration_seconds": round(float(case.get("time") or 0), 3),
            "failure_message": message,
        })
    return tests, None


def write_step_summary(report):
    """Show a results table on the GitHub Actions run page (CI only)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    s = report["summary"]
    icon = "✅" if report["overall_status"] == "passed" else "❌"
    lines = [
        f"## {icon} Test report: {report['overall_status'].upper()}",
        "",
        f"**Commit:** `{report['commit_sha'][:7]}` on `{report['branch']}` | "
        f"**Run ID:** {report['pipeline_run_id']} | "
        f"**Passed:** {s['passed']}/{s['total']} | **Failed:** {s['failed']}",
        "",
        "| Test | Result | Failure message |",
        "|---|---|---|",
    ]
    for t in report["tests"]:
        first_line = (t["failure_message"] or "").splitlines()[0] if t["failure_message"] else ""
        lines.append(f"| `{t['name']}` | {t['result']} | {first_line.replace('|', '/')} |")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/build_report.py <junit.xml> <output.json>")
        sys.exit(2)
    junit_path, output_path = sys.argv[1], sys.argv[2]

    tests, problem = parse_junit(junit_path)
    total = len(tests)
    passed = sum(t["result"] == "passed" for t in tests)
    failed = sum(t["result"] in ("failed", "error") for t in tests)
    skipped = sum(t["result"] == "skipped" for t in tests)
    overall = "passed" if total > 0 and failed == 0 else "failed"

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    repo = env("GITHUB_REPOSITORY")
    run_id = env("GITHUB_RUN_ID")
    run_url = (
        f"{env('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{run_id}"
        if "GITHUB_RUN_ID" in os.environ else None
    )

    report = {
        "repository": repo,
        "branch": env("GITHUB_REF_NAME"),
        "commit_sha": env("GITHUB_SHA"),
        "pipeline_run_id": run_id,
        "pipeline_run_number": env("GITHUB_RUN_NUMBER"),
        "pipeline_run_attempt": env("GITHUB_RUN_ATTEMPT"),
        "pipeline_run_url": run_url,
        "workflow": env("GITHUB_WORKFLOW"),
        "triggered_by": env("GITHUB_ACTOR"),
        "execution_timestamp": os.environ.get("TESTS_STARTED_AT") or now,
        "report_generated_at": now,
        "overall_status": overall,
        "summary": {"total": total, "passed": passed, "failed": failed, "skipped": skipped},
        "tests": tests,
    }
    if problem:
        report["error"] = problem

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    write_step_summary(report)
    print(f"Report written to {output_path}: {overall.upper()} "
          f"({passed}/{total} passed, {failed} failed)")


if __name__ == "__main__":
    main()