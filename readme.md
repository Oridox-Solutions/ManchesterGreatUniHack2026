# TestPilot

TestPilot analyses a GitHub pull request, maps changed lines to symbols and modules, traces explicit import relationships, discovers supported tests, and recommends the smallest safe test set. It supports Python, JavaScript/TypeScript, Java, Kotlin, C#/.NET, Ruby, PHP, Dart, Go, Elixir, Clojure, and PowerShell while retaining a safe full-suite fallback for other languages.

When TestPilot cannot analyse a change confidently, it deliberately selects the full suite rather than silently skipping potentially relevant tests.

## What is implemented

- Strict GitHub pull-request URL validation
- GitHub metadata and paginated changed-file retrieval
- Optional token support for private repositories and rate limits
- Safe download and extraction of the PR head revision
- Unified-diff line parsing
- Python function, async function, class and module-level impact analysis
- JavaScript/TypeScript function, class, ES module and CommonJS analysis
- Java and Kotlin method, class, package and import analysis
- C# namespace, class, method and using-directive analysis
- Ruby require/require_relative, class and method analysis
- PHP namespace, use, class and method analysis
- Dart package/relative import, class and function analysis
- Go package, import, function, method and struct analysis
- Elixir module, alias/import and function analysis
- Clojure namespace, require, function and record analysis
- PowerShell module import and function analysis
- Pytest, unittest, Jest, Vitest, Mocha, JUnit, TestNG, xUnit, NUnit, MSTest, RSpec, Minitest, PHPUnit, Dart package:test, Go testing, ExUnit, clojure.test and Pester discovery
- Stable test identifiers with framework metadata
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

The response includes PR metadata and risk score, every changed file and its affected symbols, targeted or conservative selection mode, test counts, and stable test identifiers with framework, confidence and reasons.

## Command line

From backend:

    python -m app.cli https://github.com/owner/repository/pull/123
    python -m app.cli --node-ids https://github.com/owner/repository/pull/123

The identifier command is suitable for CI and Jenkins adapters. For Python repositories, the identifiers can be passed directly to pytest:

    python -m pytest $(python -m app.cli --node-ids "$PULL_REQUEST_URL")

Non-Python identifiers are returned with framework metadata so an executor can translate them to the corresponding JavaScript, JVM, .NET, Ruby, PHP, Dart, Go, Elixir, Clojure, or PowerShell runner syntax.

## Selection approach

1. Download the pull request's head revision.
2. Parse GitHub patches into changed line numbers.
3. Select a language adapter from the changed file extension.
4. Map lines to functions, methods and classes using the selected language adapter.
5. Discover tests for the supported Python, JavaScript/TypeScript, JVM, .NET, Ruby, PHP, Dart, Go, Elixir, Clojure and PowerShell frameworks.
6. Build the repository import graph and calculate transitive dependants.
7. Score direct symbol calls, class use, imports, test changes and scoped semantic relationships.
8. Use the full suite whenever a patch is unavailable, parsing fails, files are deleted, configuration changes, unsupported executable code changes, or no reliable relationship is found.

The supported language set is intentionally conservative. C, C++, Rust, Swift, Scala, and languages without an implemented explicit dependency/test adapter remain unsupported and trigger full-suite selection; they are never treated as safely targeted.

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
        language_support.py
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
