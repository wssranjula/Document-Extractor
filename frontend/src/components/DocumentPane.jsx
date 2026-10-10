import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { renderAsync } from "docx-preview";
import { fetchFile } from "../api/client";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// The original discharge, shown beside the findings. PDFs and Word files render differently.

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function DocumentPane({ jobId }) {
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    fetchFile(jobId)
      .then((result) => {
        if (!cancelled) setFile(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (loading || error || !file) {
    return (
      <div className="sheet">
        {loading ? <p className="hint">Loading the document…</p> : null}
        {error ? <p className="banner error">{error}</p> : null}
        {!loading && !error ? <p className="banner empty">The document file is empty.</p> : null}
      </div>
    );
  }
  if (file.type.includes("pdf")) return <PdfView blob={file.blob} />;
  return <DocxView blob={file.blob} />;
}

function PdfView({ blob }) {
  const [pages, setPages] = useState(0);
  const [width, setWidth] = useState(480);
  const frame = useRef(null);

  useEffect(() => {
    if (!frame.current) return undefined;
    const measure = () => setWidth(Math.max(frame.current.clientWidth - 24, 240));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(frame.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="sheet" ref={frame}>
      <Document
        file={blob}
        loading={<p className="hint">Rendering PDF…</p>}
        error={<p className="banner error">This PDF could not be displayed.</p>}
        onLoadSuccess={({ numPages }) => setPages(numPages)}
      >
        {Array.from({ length: pages }, (_, index) => (
          <Page key={index + 1} pageNumber={index + 1} width={width} />
        ))}
      </Document>
    </div>
  );
}

function DocxView({ blob }) {
  const host = useRef(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!host.current) return undefined;
    let cancelled = false;
    host.current.replaceChildren();
    blob.arrayBuffer().then((buffer) => {
      if (cancelled) return;
      return renderAsync(buffer, host.current, null, { breakPages: true, inWrapper: true });
    }).catch(() => {
      if (!cancelled) setError("This document could not be displayed.");
    });
    return () => {
      cancelled = true;
    };
  }, [blob]);

  return (
    <div className="sheet docx-sheet">
      {error ? <p className="banner error">{error}</p> : null}
      <div ref={host} />
    </div>
  );
}
