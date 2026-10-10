import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getJob, getResult, streamJob } from "../api/client";
import { DocumentPane } from "../components/DocumentPane";
import { OPTIMISTIC_STAGES, completedStages, Pipeline } from "../components/Pipeline";
import { loadPendingCheck } from "../pendingCheck";

export function JobPage() {
  const { jobId } = useParams();
  const location = useLocation();
  // "pending" is the gap between clicking Check and receiving a job id.
  const pending = jobId === "pending" ? location.state || loadPendingCheck() : null;
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (jobId === "pending") return undefined;
    let cancelled = false;
    const controller = new AbortController();
    setJob(null);
    setResult(null);
    setError("");

    getJob(jobId)
      .then((current) => {
        if (cancelled) return;
        setJob(current);
        if (current.status === "succeeded") return getResult(jobId).then((value) => !cancelled && setResult(value));
        if (current.status === "failed") return undefined;
        // Keep asking the server for stage updates until the check finishes.
        return streamJob(
          jobId,
          (event, data) => {
            if (cancelled) return;
            if (data.stages) setJob((previous) => ({ ...(previous || {}), ...data, filename: previous?.filename || data.filename }));
            if (event === "done") getResult(jobId).then((value) => !cancelled && setResult(value));
            if (event === "failed") setError("Verification failed.");
          },
          controller.signal,
        );
      })
      .catch((err) => {
        if (!cancelled && err.name !== "AbortError") setError(err.message);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [jobId]);

  if (jobId === "pending" && !pending) {
    return (
      <section className="card">
        <h1>Upload not found</h1>
        <p>This check is no longer waiting to be accepted.</p>
        <Link to="/">Back to upload</Link>
      </section>
    );
  }

  if (error && !job && !pending) {
    return (
      <section className="card">
        <h1>Document unavailable</h1>
        <p className="banner error">{error}</p>
        <Link to="/">Back to upload</Link>
      </section>
    );
  }

  const visible = job || (pending
    ? { filename: pending.filename, status: "queued", stages: pending.stages, error: null }
    : { filename: location.state?.filename || "Checking document", status: "queued", stages: OPTIMISTIC_STAGES, error: null });

  const running = visible.status === "queued" || visible.status === "running";

  return (
    <section>
      <p className="eyebrow">
        <Link to="/">All checks</Link>
      </p>
      <h1>{visible.filename}</h1>
      <Pipeline stages={completedStages(visible.stages, visible.status, visible.finished_at)} />
      {pending ? <p className="lede">The file is still being accepted. These stages update as soon as the server takes the job.</p> : null}
      {visible.error ? <p className="banner error">{visible.error}</p> : null}
      {error && visible.status !== "failed" ? <p className="banner error">{error}</p> : null}
      <div className="review">
        {pending ? (
          <div className="sheet">
            <p className="hint">The document appears here as soon as the upload is accepted.</p>
          </div>
        ) : (
          <DocumentPane jobId={jobId} />
        )}
        <div className="findings">
          {running ? <p className="hint">Summary and flags appear as soon as verification finishes.</p> : null}
          {visible.status === "failed" ? <p className="banner empty">This check stopped before a result was saved.</p> : null}
          {visible.status === "succeeded" && !result ? <p className="hint">Loading the findings…</p> : null}
          {result ? <Findings result={result} /> : null}
        </div>
      </div>
    </section>
  );
}

function Findings({ result }) {
  return (
    <>
      <article className="card summary-card">
        <div className="section-heading">
          <span className="section-icon" aria-hidden="true">✦</span>
          <div>
            <p className="eyebrow">At a glance</p>
            <h2>Document summary</h2>
          </div>
        </div>
        {result.summary ? <Summary text={result.summary} /> : <p className="hint">No summary was produced.</p>}
      </article>
      <article className="card">
        <div className="section-title">
          <div>
            <h2>Critical points</h2>
            <p className="hint">Important details identified in the document.</p>
          </div>
          <span className="count-badge">{result.critical_points.length}</span>
        </div>
        {result.critical_points.length === 0 ? <p className="hint">No critical points were found in the document.</p> : null}
        <ol className="points">
          {result.critical_points.map((point) => (
            <li key={point.source_quote}>
              <p>{point.text}</p>
              <ReferenceDisclosure
                quote={point.source_quote}
                metadata={point.source_page ? `Document · page ${point.source_page}` : "Document"}
              />
            </li>
          ))}
        </ol>
      </article>
      <article className="card">
        <div className="section-title">
          <div>
            <h2>Flagged medications</h2>
            <p className="hint">Extracted medications checked against the formulary.</p>
          </div>
          <span className="count-badge">{result.medications.length}</span>
        </div>
        {result.medications.length === 0 ? <p className="hint">No medications were extracted.</p> : null}
        <ul className="meds">
          {result.medications.map((medication) => (
            <li key={medication.id}>
              <div className="medication-head">
                <div>
                  <strong>{medication.drug_name}</strong>
                  {detail(medication) ? <span>{detail(medication)}</span> : null}
                </div>
                {medication.flag ? (
                  <span className={`pill ${medication.flag.status}`}>{medication.flag.status}</span>
                ) : null}
              </div>
              {medication.flag ? <p>{medication.flag.explanation}</p> : <p className="hint">Not verified yet.</p>}
              {medication.flag?.citation ? (
                <ReferenceDisclosure
                  quote={medication.flag.citation.quote}
                  metadata={[
                    medication.flag.citation.section || "Formulary",
                    medication.flag.citation.page ? `page ${medication.flag.citation.page}` : null,
                  ].filter(Boolean).join(" · ")}
                />
              ) : medication.flag ? (
                <p className="reference-missing">No supporting reference passage was retrieved.</p>
              ) : null}
            </li>
          ))}
        </ul>
      </article>
    </>
  );
}

function Summary({ text }) {
  const paragraphs = text.split(/\n\s*\n/).map((paragraph) => paragraph.trim()).filter(Boolean);
  return (
    <div className="summary-content">
      {paragraphs.map((paragraph, index) => <p key={`${index}-${paragraph.slice(0, 24)}`}>{paragraph}</p>)}
    </div>
  );
}

function ReferenceDisclosure({ quote, metadata }) {
  return (
    <details className="reference-disclosure">
      <summary>
        <span>View source</span>
        <span className="chevron" aria-hidden="true">⌄</span>
      </summary>
      <div className="reference-content">
        <blockquote>{quote}</blockquote>
        <cite>{metadata}</cite>
      </div>
    </details>
  );
}

function detail(medication) {
  return [medication.dose, medication.unit, medication.route, medication.frequency, medication.duration]
    .filter(Boolean)
    .join(" · ");
}
