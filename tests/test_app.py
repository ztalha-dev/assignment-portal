import pytest

from app import create_app

VALID_SUBMISSION = {
    "name": "Ali Khan",
    "reg_no": "FA22-BCS-001",
    "title": "DevOps Lab Mid",
    "url": "https://github.com/ztalha-dev/assignment-portal",
}


@pytest.fixture
def client(tmp_path):
    """Each test gets a fresh app with its own empty, temporary data file."""
    app = create_app(data_file=str(tmp_path / "submissions.json"))
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def saved_submissions(client):
    return client.get("/api/submissions").get_json()


def test_valid_submission_is_saved_and_listed(client):
    """Complete details + valid URL -> saved and appears in the list."""
    response = client.post("/submit", data=VALID_SUBMISSION)
    assert response.status_code == 302, "Valid submission should redirect after saving"

    saved = saved_submissions(client)
    assert len(saved) == 1, "Exactly one submission should be saved"
    assert saved[0]["reg_no"] == "FA22-BCS-001"

    page = client.get("/").get_data(as_text=True)
    assert "Ali Khan" in page, "Saved submission should appear in the list"
    assert "FA22-BCS-001" in page


def test_missing_registration_number_is_rejected(client):
    """Missing registration number -> rejected with a validation message."""
    data = {**VALID_SUBMISSION, "reg_no": ""}
    response = client.post("/submit", data=data)

    assert response.status_code == 400, "Missing reg. number should be rejected"
    assert "Registration number is required." in response.get_data(as_text=True)
    assert saved_submissions(client) == [], "Rejected submission must not be saved"


def test_invalid_url_is_rejected_and_not_saved(client):
    """Invalid submission URL -> rejected and not saved."""
    data = {**VALID_SUBMISSION, "url": "not-a-url"}
    response = client.post("/submit", data=data)

    assert response.status_code == 400, "Invalid URL should be rejected"
    assert "valid http" in response.get_data(as_text=True)
    assert saved_submissions(client) == [], "Rejected submission must not be saved"