# Assignment Submission Portal

CSC418 – DevOps for Cloud Computing, Lab Mid.

A Flask portal where students submit their name, registration number,
assignment title and submission URL. Every push is tested automatically by
GitHub Actions inside Docker, and the test report is delivered to a local
HTTP receiver that saves it as `testreport.json`.

## Project structure

```
app.py                     Flask application (validation, saving, listing)
templates/index.html       Submission form and saved submissions list
tests/test_app.py          Automated pytest test cases
scripts/build_report.py    Builds the JSON test report in CI
receiver/receiver.py       Local HTTP receiver that saves testreport.json
.github/workflows/ci.yml   CI pipeline
Dockerfile                 Container image for the portal and tests
docker-compose.yml         Runs portal + receiver + ngrok tunnel together
```

## Requirements

- Docker Desktop (running)
- Git
- Python 3.10+ (only needed to run without Docker)

## 1. Get the code

```powershell
git clone https://github.com/ztalha-dev/assignment-portal.git
cd assignment-portal
```

## 2. Run the application

**With Docker**

```powershell
docker build -t assignment-portal .
docker run --rm -p 5000:5000 -v portal-data:/app/data assignment-portal
```

**Without Docker**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

## 3. Run the tests

**Inside Docker (same as CI)**

```powershell
docker build -t assignment-portal .
docker run --rm assignment-portal pytest -v
```

**Locally:** `pytest -v`

## 4. Start the report receiver

The receiver runs on your computer. An ngrok tunnel lets GitHub Actions reach it.

1. Create a free account at https://ngrok.com and copy your authtoken.
2. Create a `.env` file in the project folder. It is git-ignored; never commit it.

   ```env
   NGROK_AUTHTOKEN=your-ngrok-authtoken
   RECEIVER_TOKEN=any-long-random-string
   ```

   Generate a token with `python -c "import secrets; print(secrets.token_urlsafe(24))"`.

3. Start the portal, receiver and tunnel:

   ```powershell
   docker compose up
   ```

4. Find your public URL:

   ```powershell
   docker compose logs tunnel | Select-String "url="
   ```

5. In GitHub, go to **Settings → Secrets and variables → Actions** and add:
   - `RECEIVER_URL`: `https://<your-ngrok-domain>/report`
   - `RECEIVER_TOKEN`: the same value as in `.env`

Keep `docker compose up` running. After every push, the latest report is
saved as `testreport.json` in the project folder.

## CI pipeline

`.github/workflows/ci.yml` runs on every push:

1. Builds a Docker image of the pushed commit
2. Runs pytest inside the container. A failing test fails the run.
3. Builds the JSON report, even when tests fail
4. Sends the report to the local receiver

## Test report contents

Repository, branch, commit SHA, pipeline run ID/number/URL, execution
timestamp, each test's name, result and failure message, total/passed/failed
counts and the overall status.