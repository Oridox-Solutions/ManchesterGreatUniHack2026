const API_URL = "http://localhost:8000";

export async function checkBackend(): Promise<{ status: string }> {
  const response = await fetch(`${API_URL}/health`);

  if (!response.ok) {
    throw new Error("Backend unavailable");
  }

  return response.json();
}

export interface AnalysisResult {
  pull_request: {
    title: string;
    number: number;
    repository: string;
    url: string;
  };
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  summary: string;
  changed_files: {
    path: string;
    status: string;
    additions: number;
    deletions: number;
    changed_functions: string[];
    changed_classes: string[];
  }[];
  recommended_tests: {
    test_file: string;
    test_name: string;
    priority: "low" | "medium" | "high" | "critical";
    confidence: number;
    reasons: string[];
  }[];
}

export async function analysePullRequest(
  pullRequestUrl: string,
): Promise<AnalysisResult> {
  const response = await fetch(`${API_URL}/api/analyse`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      pull_request_url: pullRequestUrl,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to analyse pull request");
  }

  return response.json();
}
