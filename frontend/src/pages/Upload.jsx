import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listJobs, listReferences, createJob } from "../api";
import { OPTIMISTIC_STAGES, Pipeline } from "../Pipeline";

const MAX_BYTES = 20 * 1024 * 1024;

export function UploadPage() {
  const navigate = useNavigate();
  const [references, setReferences] = useState(null);
  const [jobs, setJobs] = useState(null);
  const [referenceId, setReferenceId] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    Promise.all([listReferences(), listJobs()])
      .then(([refs, existing]) => {
        setReferences(refs);
        setJobs(existing);
        if (refs[0]) setReferenceId(refs[0].id);
      })
      .catch((err) => setLoadError(err.message));
  }, []);

  function chooseFile(next) {
    setError("");
    if (!next) return;
    const name = next.name.toLowerCase();
    if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
      setError("Upload a PDF or DOCX file.");
      return;
    }
    if (next.size > MAX_BYTES) {
      setError("The file is larger than 20 MB.");
      return;
    }
    setFile(next);
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!file) {
      setError("Choose a discharge summary first.");
      return;
    }
    if (!referenceId) {
      setError("Choose a formulary first.");
      return;
    }
    setSending(true);
    try {
      const job = await createJob(file, referenceId);
      navigate(`/jobs/${job.job_id}`);
    } catch (err) {
      setError(err.message);
      setSending(false);
    }
  }

  if (sending) {
    return (
      <section>
        <h1>{file.name}</h1>
        <p className="lede">The document is on its way. These stages are shown before the server finishes accepting the file.</p>
        <Pipeline stages={OPTIMISTIC_STAGES} />
      </section>
    );
  }

  return (
    <div className="upload-layout">
      <section>
        <h1>Check a discharge summary</h1>
        <p className="lede">The file is accepted immediately. Verification continues on the next screen.</p>
        {loadError ? <p className="banner error">{loadError}</p> : null}
        {references && references.length === 0 ? (
          <p className="banner empty">No formulary is loaded yet. Run the seed command, then refresh this page.</p>
        ) : null}
        <form className="card" onSubmit={onSubmit}>
          <label
            className={dragging ? "dropzone dragging" : "dropzone"}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              chooseFile(event.dataTransfer.files?.[0]);
            }}
          >
            <input
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => chooseFile(event.target.files?.[0])}
            />
            {file ? <strong>{file.name}</strong> : <strong>Drop a PDF or DOCX here</strong>}
            <span>or click to browse</span>
          </label>
          <label>
            Formulary
            {references === null ? (
              <span className="hint">Loading formularies…</span>
            ) : (
              <select value={referenceId} onChange={(event) => setReferenceId(event.target.value)}>
                {references.map((reference) => (
                  <option key={reference.id} value={reference.id}>
                    {reference.name}
                  </option>
                ))}
              </select>
            )}
          </label>
          {error ? <p className="banner error">{error}</p> : null}
          <button type="submit">Check document</button>
        </form>
      </section>
      <aside className="card jobs">
        <h2>Recent checks</h2>
        {jobs === null ? <p className="hint">Loading…</p> : null}
        {jobs && jobs.length === 0 ? <p className="hint">No documents yet.</p> : null}
        <ul>
          {(jobs || []).map((job) => (
            <li key={job.id}>
              <Link to={`/jobs/${job.id}`}>{job.filename}</Link>
              <span className={`status ${job.status}`}>{job.status}</span>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
