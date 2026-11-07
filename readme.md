# TestPilot

TestPilot analyses a GitHub pull request, maps changed lines to Python symbols and modules, traces import relationships, discovers the repository's tests, and recommends the smallest safe test set.

When TestPilot cannot analyse a change confidently, it deliberately selects the full suite rather than silently skipping potentially relevant tests.

## What is implemented

- Strict GitHub pull-request URL validation
- GitHub metadata and paginated changed-file retrieval
- Optional token support for private repositories and rate limits
- Safe download and extraction of the PR head revision
- Unified-diff line parsing
- Python function, async function, class and module-level impact analysis
- Pytest and unittest.TestCase discovery
- Exact executable test node IDs
- Direct and transitive import dependency analysis
- Multi-signal confidence scoring
- Conservative full-suite fallback for unknown, configuration, deleted or unsupported changes
- Explainable risk scoring and recommendation reasons
- Responsive React results dashboard
- Backend tests and GitHub Actions CI

## Requirements

- Python 3.12 or newer
- Node.js 22 or newer
- Git

## Backend setup

From the repository root on Windows PowerShell:

    cd backend
    py -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    python -m uvicorn app.main:app --reload

On macOS or Linux:

    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    python -m uvicorn app.main:app --reload

The API is available at http://localhost:8000, with interactive documentation at http://localhost:8000/docs.

## GitHub token

Public repositories work without authentication, but GitHub applies a low anonymous rate limit. Copy .env.example or set the variables in the terminal before starting the backend.

PowerShell:

    $env:GITHUB_TOKEN="your_token_here"

macOS or Linux:

    export GITHUB_TOKEN="your_token_here"

The token needs repository read access for private repositories. Never commit it.

## Frontend setup

In a second terminal:

    cd frontend
    npm ci
    npm run dev

Open http://localhost:5173. Vite proxies /api and /health to the local backend. For a separately hosted API, set VITE_API_URL.

## Run tests and checks

Backend:

    cd backend
    python -m pytest -q

Frontend:

    cd frontend
    npm run lint
    npm run build

GitHub Actions runs all three checks on pushes and pull requests.

## API

POST /api/analyse with:

    {
      "pull_request_url": "https://github.com/owner/repository/pull/123"
    }

The response includes PR metadata and risk score, every changed file and its affected symbols, targeted or conservative selection mode, test counts, and exact test node IDs with confidence and reasons.

## Command line

From backend:

    python -m app.cli https://github.com/owner/repository/pull/123
    python -m app.cli --node-ids https://github.com/owner/repository/pull/123

The node-ID command is suitable for CI and Jenkins command construction:

    python -m pytest $(python -m app.cli --node-ids "$PULL_REQUEST_URL")

## Selection approach

1. Download the pull request's head revision.
2. Parse GitHub patches into changed line numbers.
3. Map lines to Python functions/classes and detect module-level edits.
4. Discover pytest functions and unittest/pytest test classes.
5. Build the repository import graph and calculate transitive dependants.
6. Score test-name, class, symbol-reference, import and file-path relationships.
7. Use the full suite whenever a patch is unavailable, parsing fails, files are deleted, configuration changes, unsupported executable code changes, or no reliable relationship is found.

This is currently a Python test selector. Changes to unsupported executable languages intentionally trigger the safe full-suite fallback.

## Project structure

    backend/app/
      main.py
      cli.py
      models/analyse.py
      routes/analyse.py
      services/
        analysis.py
        github.py
        diff_parser.py
        code_analysis.py
        dependencies.py
        test_discovery.py
        test_matching.py
        risk.py
    frontend/src/
      App.tsx
      App.css
      services/api.ts

## Safety behaviour

Test selection must prefer false positives over false negatives. A recommendation of zero tests is only allowed for documentation-only changes. All ambiguous executable changes use conservative mode and select every discovered test.
