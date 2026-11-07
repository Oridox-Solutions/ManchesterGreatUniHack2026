import { useEffect, useState } from "react";
import { GitPullRequest, ShieldCheck, Activity, Play } from "lucide-react";
import {
  checkBackend,
  analysePullRequest,
  type AnalysisResult,
} from "./services/api";

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking...");
  const [backendError, setBackendError] = useState(false);

  const [pullRequestUrl, setPullRequestUrl] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    checkBackend()
      .then((data) => {
        setBackendStatus(data.status);
        setBackendError(false);
      })
      .catch(() => {
        setBackendStatus("Unavailable");
        setBackendError(true);
      });
  }, []);

  async function handleAnalyse() {
    if (!pullRequestUrl.trim()) {
      setError("Please enter a GitHub pull request URL.");
      return;
    }

    setLoading(true);
    setError("");
    setAnalysis(null);

    try {
      const result = await analysePullRequest(pullRequestUrl.trim());
      setAnalysis(result);
    } catch {
      setError("Analysis failed. Please check the PR URL and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>TestPilot</h1>
      <p>Intelligent Automated Testing</p>

      <div>
        <GitPullRequest />
        <span>GitHub pull request analysis</span>
      </div>

      <div>
        <ShieldCheck />
        <span>Intelligent test recommendations</span>
      </div>

      <div>
        <Activity />
        <span>Backend status: {backendStatus}</span>
      </div>

      {backendError && <p>Could not connect to the backend.</p>}

      <hr />

      <section>
        <h2>Analyse a Pull Request</h2>

        <input
          type="url"
          placeholder="https://github.com/owner/repository/pull/123"
          value={pullRequestUrl}
          onChange={(event) => setPullRequestUrl(event.target.value)}
        />

        <button onClick={handleAnalyse} disabled={loading}>
          <Play size={16} />
          {loading ? "Analysing..." : "Analyse PR"}
        </button>

        {error && <p>{error}</p>}
      </section>

      {analysis && (
        <section>
          <hr />
          <h2>{analysis.pull_request.title}</h2>

          <p>Repository: {analysis.pull_request.repository}</p>

          <p>Risk score: {analysis.risk_score}/100</p>

          <p>Risk level: {analysis.risk_level.toUpperCase()}</p>

          <p>{analysis.summary}</p>

          <h3>Changed Files</h3>

          {analysis.changed_files.length === 0 ? (
            <p>No changed files returned.</p>
          ) : (
            <ul>
              {analysis.changed_files.map((file) => (
                <li key={file.path}>
                  {file.path} (+{file.additions} / -{file.deletions})
                </li>
              ))}
            </ul>
          )}

          <h3>Recommended Tests</h3>

          {analysis.recommended_tests.length === 0 ? (
            <p>No test recommendations returned.</p>
          ) : (
            <ul>
              {analysis.recommended_tests.map((test, index) => (
                <li key={`${test.test_file}-${test.test_name}-${index}`}>
                  <strong>{test.test_name}</strong>
                  <p>{test.test_file}</p>
                  <p>
                    Priority: {test.priority} | Confidence:{" "}
                    {Math.round(test.confidence * 100)}%
                  </p>
                  <ul>
                    {test.reasons.map((reason, reasonIndex) => (
                      <li key={reasonIndex}>{reason}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}

export default App;
