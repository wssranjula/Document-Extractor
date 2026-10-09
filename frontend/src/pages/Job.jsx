import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getJob, getResult, streamJob } from "../api";
import { DocumentPane } from "../DocumentPane";
import { Pipeline } from "../Pipeline";

export function JobPage() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
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

  if (error && !job) {
    return (
      <section className="card">
        <h1>Document unavailable</h1>
        <p className="banner error">{error}</p>
        <Link to="/">Back to upload</Link>
      </section>
    );
  }

  if (!job) return <p className="page-loading">Loading this check…</p>;

  const selected = result?.medications.find((item) => item.id === selectedId) || null;
  const running = job.status === "queued" || job.status === "running";

  return (
    <section>
      <p className="eyebrow">
        <Link to="/">All checks</Link>
      </p>
      <h1>{job.filename}</h1>
      <Pipeline stages={job.stages} />
      {job.error ? <p className="banner error">{job.error}</p> : null}
      {error && job.status !== "failed" ? <p className="banner error">{error}</p> : null}
      <div className="review">
        <DocumentPane jobId={jobId} />
        <div className="findings">
          {running ? <p className="hint">Summary and flags appear as soon as verification finishes.</p> : null}
          {job.status === "failed" ? <p className="banner empty">This check stopped before a result was saved.</p> : null}
          {job.status === "succeeded" && !result ? <p className="hint">Loading the findings…</p> : null}
          {result ? <Findings result={result} selectedId={selectedId} onSelect={setSelectedId} /> : null}
          {selected ? <Citation flag={selected.flag} drug={selected.drug_name} onClose={() => setSelectedId(null)} /> : null}
        </div>
      </div>
    </section>
  );
}

function Findings({ result, selectedId, onSelect }) {
  return (
    <>
      <article className="card">
        <h2>Summary</h2>
        {result.summary ? <p>{result.summary}</p> : <p className="hint">No summary was produced.</p>}
      </article>
      <article className="card">
        <h2>Critical points</h2>
        {result.critical_points.length === 0 ? <p className="hint">No critical points were found in the document.</p> : null}
        <ol className="points">
          {result.critical_points.map((point) => (
            <li key={point.source_quote}>
              <p>{point.text}</p>
              <blockquote>
                {point.source_quote}
                {point.source_page ? <cite>Page {point.source_page}</cite> : null}
              </blockquote>
            </li>
          ))}
        </ol>
      </article>
      <article className="card">
        <h2>Flagged medications</h2>
        {result.medications.length === 0 ? <p className="hint">No medications were extracted.</p> : null}
        <ul className="meds">
          {result.medications.map((medication) => (
            <li key={medication.id} className={medication.id === selectedId ? "selected" : ""}>
              <div>
                <strong>{medication.drug_name}</strong>
                <span>{detail(medication)}</span>
                {medication.flag ? <p>{medication.flag.explanation}</p> : <p className="hint">Not verified yet.</p>}
              </div>
              {medication.flag ? (
                <button type="button" className={`pill ${medication.flag.status}`} onClick={() => onSelect(medication.id)}>
                  {medication.flag.status}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </article>
    </>
  );
}

function Citation({ flag, drug, onClose }) {
  const citation = flag?.citation;
  return (
    <aside className="card citation">
      <div className="citation-head">
        <h2>Reference passage</h2>
        <button type="button" className="text-button" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="hint">{drug}</p>
      {citation?.quote ? (
        <>
          <blockquote>{citation.quote}</blockquote>
          <p>
            {citation.section || "Formulary"}
            {citation.page ? ` · page ${citation.page}` : ""}
          </p>
        </>
      ) : (
        <p className="banner empty">No supporting passage was retrieved for this medication.</p>
      )}
    </aside>
  );
}

function detail(medication) {
  return [medication.dose, medication.unit, medication.route, medication.frequency, medication.duration]
    .filter(Boolean)
    .join(" · ");
}
