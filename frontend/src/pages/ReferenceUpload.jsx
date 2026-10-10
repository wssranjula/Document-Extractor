/** Upload a DOCX formulary. The server rejects a file that has no Heading 2 monographs. */

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createReference, listReferences } from "../api/client";

const MAX_BYTES = 20 * 1024 * 1024;

export function ReferenceUploadPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState("");
  const [references, setReferences] = useState(null);
  const [listError, setListError] = useState("");

  useEffect(() => {
    listReferences()
      .then(setReferences)
      .catch((err) => setListError(err.message));
  }, []);

  function chooseFile(next) {
    setError("");
    if (!next) return;
    if (!next.name.toLowerCase().endsWith(".docx")) {
      setFile(null);
      setError("Upload a DOCX formulary.");
      return;
    }
    if (next.size > MAX_BYTES) {
      setFile(null);
      setError("The file is larger than 20 MB.");
      return;
    }
    setFile(next);
    if (!name.trim()) {
      setName(next.name.replace(/\.docx$/i, "").replace(/[_-]+/g, " "));
    }
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Enter a formulary name.");
      return;
    }
    if (!file) {
      setError("Choose a DOCX formulary.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const reference = await createReference(name.trim(), file);
      setSaved(reference);
      setReferences((current) => [
        reference,
        ...(current || []).filter((item) => item.id !== reference.id),
      ]);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  if (saved) {
    return (
      <section className="reference-upload">
        <p className="eyebrow">
          <Link to="/">Back to document checks</Link>
        </p>
        <h1>Formulary saved</h1>
        <div className="card saved-reference">
          <p className="banner success">The formulary was added successfully.</p>
          <h2>{saved.name}</h2>
          <p>{saved.filename}</p>
          <p className="hint">
            Choose “Use this formulary” to select it. Indexing runs the first time a discharge summary uses it, when Chunked and Embedded turn green.
          </p>
          <button
            type="button"
            onClick={() =>
              navigate("/", {
                replace: true,
                state: {
                  referenceId: saved.id,
                  referenceAdded: `${saved.name} was saved and is selected.`,
                },
              })
            }
          >
            Use this formulary
          </button>
        </div>
        <ReferenceList references={references} error={listError} />
      </section>
    );
  }

  return (
    <section className="reference-upload">
      <p className="eyebrow">
        <Link to="/">Back to document checks</Link>
      </p>
      <h1>Add a formulary</h1>
      <p className="lede">
        Upload a Word document with each drug monograph formatted as Heading 2. It will be indexed when first used.
      </p>
      <form className="card" onSubmit={onSubmit}>
        <label>
          Formulary name
          <input
            type="text"
            maxLength={255}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Example: North Campus Formulary"
            disabled={saving}
          />
        </label>
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
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(event) => chooseFile(event.target.files?.[0])}
            disabled={saving}
          />
          {file ? <strong>{file.name}</strong> : <strong>Drop a DOCX formulary here</strong>}
          <span>Maximum 20 MB</span>
        </label>
        {error ? <p className="banner error">{error}</p> : null}
        <button type="submit" disabled={saving}>
          {saving ? "Adding formulary…" : "Add formulary"}
        </button>
      </form>
      <ReferenceList references={references} error={listError} />
    </section>
  );
}

function ReferenceList({ references, error }) {
  return (
    <section className="reference-list">
      <div className="section-title">
        <div>
          <h2>Uploaded formularies</h2>
          <p className="hint">Files become ready after their first document check builds the search index.</p>
        </div>
        {references ? <span className="count-badge">{references.length}</span> : null}
      </div>
      {error ? <p className="banner error">{error}</p> : null}
      {references === null && !error ? <p className="hint">Loading uploaded files…</p> : null}
      {references?.length === 0 ? <p className="banner empty">No formularies have been uploaded yet.</p> : null}
      {references?.length ? (
        <ul>
          {references.map((reference) => (
            <li key={reference.id} className="card">
              <div>
                <strong>{reference.name}</strong>
                <span>{reference.filename}</span>
              </div>
              <span className={`reference-status ${reference.indexed ? "ready" : "waiting"}`}>
                {reference.indexed ? "Ready" : "Not indexed yet"}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
