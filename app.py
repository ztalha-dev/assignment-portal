import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, render_template, request, url_for

REQUIRED_FIELDS = {
    "name": "Name",
    "reg_no": "Registration number",
    "title": "Assignment title",
    "url": "Submission URL",
}


def is_valid_url(value):
    """Accept only http(s) links with a real host, e.g. https://github.com/me/repo"""
    if any(ch.isspace() for ch in value):
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and "." in parsed.netloc


def validate_submission(form):
    """Return (cleaned_data, list_of_error_messages)."""
    data = {field: (form.get(field) or "").strip() for field in REQUIRED_FIELDS}
    errors = []
    for field, label in REQUIRED_FIELDS.items():
        if not data[field]:
            errors.append(f"{label} is required.")
    if data["url"] and not is_valid_url(data["url"]):
        errors.append("Submission URL must be a valid http:// or https:// link.")
    return data, errors


def load_submissions(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_submission(path, submission):
    submissions = load_submissions(path)
    submissions.append(submission)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(submissions, f, indent=2)


def create_app(data_file=None):
    """App factory: tests pass a temporary data_file so real data is never touched."""
    app = Flask(__name__)
    app.config["DATA_FILE"] = data_file or os.environ.get("DATA_FILE", "submissions.json")

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            submissions=load_submissions(app.config["DATA_FILE"]),
            errors=[],
            form={},
            saved=request.args.get("saved") == "1",
        )

    @app.post("/submit")
    def submit():
        data, errors = validate_submission(request.form)
        if errors:
            return render_template(
                "index.html",
                submissions=load_submissions(app.config["DATA_FILE"]),
                errors=errors,
                form=data,
                saved=False,
            ), 400
        data["submitted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_submission(app.config["DATA_FILE"], data)
        return redirect(url_for("index", saved=1))

    @app.get("/api/submissions")
    def api_submissions():
        return jsonify(load_submissions(app.config["DATA_FILE"]))

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )