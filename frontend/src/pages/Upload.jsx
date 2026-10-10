import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { listJobs, listReferences, createJob } from "../api/client";
import { acceptingStages, forgetPendingCheck, loadPendingCheck, rememberPendingCheck } from "../pendingCheck";

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
  const [pendingCheck, setPendingCheck] = useState(() => loadPendingCheck());
  const location = useLocation();
  const submitted = useRef(false);

  useEffect(() => {
    Promise.all([listReferences(), listJobs()])
      .then(([refs, existing]) => {
        setReferences(refs);
        setJobs(existing);
        const preferred = refs.find((reference) => reference.id === location.state?.referenceId);
        if (preferred || refs[0]) setReferenceId((preferred || refs[0]).id);
      })
      .catch((err) => setLoadError(err.message));
  }, [location.state?.referenceId]);

  useEffect(() => {
    if (location.state?.uploadError) setError(location.state.uploadError);
  }, [location.state]);

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

  function onSubmit(event) {
    event.preventDefault();
    if (submitted.current) return;
    if (!file) {
      setError("Choose a discharge summary first.");
      return;
    }
    if (!referenceId) {
      setError("Choose a formulary first.");
      return;
    }
    submitted.current = true;
    const filename = file.name;
    const selectedFile = file;
    const selectedReference = referenceId;
    const stages = acceptingStages();
    const pending = { id: "pending", filename, status: "queued", stages };
    rememberPendingCheck(pending);
    setPendingCheck(pending);
    // Open the check page now. The real job id arrives when the upload finishes.
    navigate("/jobs/pending", { state: pending });
    createJob(selectedFile, selectedReference)
      .then((job) => {
        forgetPendingCheck();
        navigate(`/jobs/${job.job_id}`, { replace: true, state: { filename } });
      })
      .catch((err) => {
        forgetPendingCheck();
        submitted.current = false;
        navigate("/", { replace: true, state: { uploadError: err.message } });
      });
  }

  const visibleJobs = pendingCheck ? [pendingCheck, ...(jobs || [])] : jobs;

  return (
    <div className="upload-layout">
      <section>
        <h1>Check a discharge summary</h1>
        <p className="lede">The check opens immediately. The file is accepted while the first stage is already on screen.</p>
        {location.state?.referenceAdded ? <p className="banner success">{location.state.referenceAdded}</p> : null}
        {loadError ? <p className="banner error">{loadError}</p> : null}
        {references && references.length === 0 ? (
          <p className="banner empty">
            No formulary is loaded yet. <Link to="/references/new">Add one now.</Link>
          </p>
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
              <>
                <select value={referenceId} onChange={(event) => setReferenceId(event.target.value)}>
                  {references.map((reference) => (
                    <option key={reference.id} value={reference.id}>
                      {reference.name}
                      {reference.indexed ? " · indexed" : " · not indexed yet"}
                    </option>
                  ))}
                </select>
                <span className="hint"><Link to="/references/new">Add another formulary</Link></span>
              </>
            )}
          </label>
          {error ? <p className="banner error">{error}</p> : null}
          <button type="submit">Check document</button>
        </form>
      </section>
      <aside className="card jobs">
        <h2>Recent checks</h2>
        {jobs === null ? <p className="hint">Loading…</p> : null}
        {visibleJobs && visibleJobs.length === 0 ? <p className="hint">No documents yet.</p> : null}
        <ul>
          {(visibleJobs || []).map((job) => (
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
