import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  FileCode2,
  FlaskConical,
  GitBranch,
  GitPullRequest,
  Play,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  analysePullRequest,
  checkBackend,
  type AnalysisResult,
} from "./services/api";
import "./App.css";

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking");
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

  async function handleAnalyse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pullRequestUrl.trim()) {
      setError("Enter a GitHub pull request URL.");
      return;
    }

    setLoading(true);
    setError("");
    setAnalysis(null);
    try {
      setAnalysis(await analysePullRequest(pullRequestUrl.trim()));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Analysis failed. Check the pull request URL and try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  const skipped = analysis
    ? Math.max(0, analysis.total_tests_discovered - analysis.tests_selected)
    : 0;

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="TestPilot home">
          <span className="brand-mark"><Sparkles size={18} /></span>
          <span>TestPilot</span>
        </a>
        <div className={"health-pill " + (backendError ? "offline" : "")}>
          <span />
          API {backendStatus}
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="eyebrow"><ShieldCheck size={15} /> Change-aware testing</div>
          <h1>Run the tests that matter.<br /><em>Skip the ones that don’t.</em></h1>
          <p>
            TestPilot maps pull-request changes to the code and tests they affect,
            with a safe full-suite fallback whenever confidence is low.
          </p>

          <form className="analyse-form" onSubmit={handleAnalyse}>
            <GitPullRequest size={21} />
            <label className="sr-only" htmlFor="pr-url">GitHub pull request URL</label>
            <input
              id="pr-url"
              type="url"
              placeholder="https://github.com/owner/repository/pull/123"
              value={pullRequestUrl}
              onChange={(event) => setPullRequestUrl(event.target.value)}
              disabled={loading}
              required
            />
            <button type="submit" disabled={loading || backendError}>
              {loading ? <span className="spinner" /> : <Play size={16} fill="currentColor" />}
              {loading ? "Analysing…" : "Analyse PR"}
            </button>
          </form>
          <div className="form-note">
            <ShieldCheck size={13} /> Public repositories work without a token.
            Private repositories use the backend’s GitHub token.
          </div>
          {error && <div className="error-message" role="alert"><AlertTriangle size={17} />{error}</div>}
        </section>

        {!analysis && (
          <section className="feature-row" aria-label="How TestPilot works">
            <Feature icon={<GitBranch />} number="01" title="Understand the diff">
              Changed lines are mapped to functions, classes and modules.
            </Feature>
            <Feature icon={<Activity />} number="02" title="Trace dependencies">
              Imports and test references reveal downstream impact.
            </Feature>
            <Feature icon={<FlaskConical />} number="03" title="Select safely">
              Low-confidence changes automatically trigger the full suite.
            </Feature>
          </section>
        )}

        {analysis && (
          <section className="results" aria-live="polite">
            <div className="result-heading">
              <div>
                <span className="result-kicker">{analysis.pull_request.repository} · PR #{analysis.pull_request.number}</span>
                <h2>{analysis.pull_request.title}</h2>
                <p>{analysis.summary}</p>
              </div>
              <a href={analysis.pull_request.url} target="_blank" rel="noreferrer">
                View on GitHub ↗
              </a>
            </div>

            <div className="metrics">
              <Metric label="Tests discovered" value={analysis.total_tests_discovered} />
              <Metric label="Tests selected" value={analysis.tests_selected} accent />
              <Metric label="Tests skipped" value={skipped} positive />
              <Metric
                label="Risk score"
                value={String(analysis.risk_score) + "/100"}
                suffix={analysis.risk_level}
              />
            </div>

            <div className={"selection-banner " + analysis.selection_mode}>
              {analysis.selection_mode === "targeted" ? <CheckCircle2 /> : <ShieldCheck />}
              <div>
                <strong>
                  {analysis.selection_mode === "targeted"
                    ? "Targeted selection"
                    : "Conservative full-suite selection"}
                </strong>
                <span>
                  {analysis.selection_mode === "targeted"
                    ? "Only confidently related tests were selected."
                    : "An uncertain change was found, so TestPilot chose safety."}
                </span>
              </div>
            </div>

            <div className="result-grid">
              <section className="result-panel">
                <div className="panel-title"><FileCode2 size={18} /><h3>Changed files</h3><span>{analysis.changed_files.length}</span></div>
                <div className="file-list">
                  {analysis.changed_files.map((file) => (
                    <article className="file-row" key={file.path}>
                      <div>
                        <strong>{file.path}</strong>
                        <small>
                          {file.changed_functions.length || file.changed_classes.length
                            ? [...file.changed_classes, ...file.changed_functions].join(", ")
                            : file.analysis_status.replace("_", " ")}
                        </small>
                      </div>
                      <div className="diff-count"><b>+{file.additions}</b><i>-{file.deletions}</i></div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="result-panel tests-panel">
                <div className="panel-title"><FlaskConical size={18} /><h3>Recommended tests</h3><span>{analysis.tests_selected}</span></div>
                <div className="test-list">
                  {analysis.recommended_tests.length === 0 ? (
                    <div className="empty-state">
                      {analysis.total_tests_discovered === 0 ? <AlertTriangle /> : <CheckCircle2 />}
                      <strong>
                        {analysis.total_tests_discovered === 0
                          ? "No supported tests discovered"
                          : "No tests required"}
                      </strong>
                      <span>
                        {analysis.total_tests_discovered === 0
                          ? "Check the repository test layout and supported languages."
                          : "This pull request only changes documentation."}
                      </span>
                    </div>
                  ) : analysis.recommended_tests.map((test) => (
                    <article className="test-row" key={test.node_id}>
                      <div className="test-topline">
                        <strong>{test.test_name}</strong>
                        <span className={"priority " + test.priority}>{test.priority}</span>
                      </div>
                      <code>{test.node_id}</code>
                      <div className="confidence">
                        <span><i style={{ width: String(Math.round(test.confidence * 100)) + "%" }} /></span>
                        <b>{Math.round(test.confidence * 100)}%</b>
                      </div>
                      <p>{test.reasons.join(" · ")}</p>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          </section>
        )}
      </main>

      <footer>TestPilot · Built for GreatUniHack 2026</footer>
    </div>
  );
}

function Feature({
  icon,
  number,
  title,
  children,
}: {
  icon: ReactNode;
  number: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <article className="feature">
      <div className="feature-icon">{icon}</div>
      <span>{number}</span>
      <h2>{title}</h2>
      <p>{children}</p>
    </article>
  );
}

function Metric({
  label,
  value,
  suffix,
  accent = false,
  positive = false,
}: {
  label: string;
  value: string | number;
  suffix?: string;
  accent?: boolean;
  positive?: boolean;
}) {
  return (
    <article className={"metric " + (accent ? "accent" : "") + " " + (positive ? "positive" : "")}>
      <span>{label}</span>
      <strong>{value}</strong>
      {suffix && <small>{suffix}</small>}
    </article>
  );
}

export default App;
