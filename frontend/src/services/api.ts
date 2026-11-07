const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export interface AnalysisResult {
  pull_request: {
    title: string;
    number: number;
    repository: string;
    url: string;
    base_sha: string;
    head_sha: string;
  };
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  selection_mode: "targeted" | "conservative";
  summary: string;
  total_tests_discovered: number;
  tests_selected: number;
  changed_files: {
    path: string;
    status: string;
    additions: number;
    deletions: number;
    changed_functions: string[];
    changed_classes: string[];
    changed_lines: number[];
    analysis_status:
      | "analysed"
      | "file_level"
      | "unsupported"
      | "missing_source"
      | "parse_failed";
    module_level_change: boolean;
  }[];
  recommended_tests: {
    test_file: string;
    test_name: string;
    test_class: string | null;
    node_id: string;
    framework:
      | "pytest"
      | "unittest"
      | "jest"
      | "vitest"
      | "mocha"
      | "junit"
      | "testng"
      | "xunit"
      | "nunit"
      | "mstest"
      | "rspec"
      | "minitest"
      | "phpunit"
      | "dart_test"
      | "go_test"
      | "exunit"
      | "clojure_test"
      | "pester";
    priority: "low" | "medium" | "high" | "critical";
    confidence: number;
    reasons: string[];
  }[];
}

async function readJson<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String(data.detail)
        : "The server could not complete the request.";
    throw new Error(detail);
  }
  return data as T;
}

export async function checkBackend(): Promise<{ status: string }> {
  const response = await fetch(API_URL + "/health", {
    signal: AbortSignal.timeout(5000),
  });
  return readJson(response);
}

export async function analysePullRequest(
  pullRequestUrl: string,
): Promise<AnalysisResult> {
  const response = await fetch(API_URL + "/api/analyse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pull_request_url: pullRequestUrl }),
    signal: AbortSignal.timeout(120000),
  });
  return readJson(response);
}
