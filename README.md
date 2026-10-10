# Formulary Check

A discharge summary is checked against an institutional formulary. The React app accepts the file immediately, and a worker runs one fixed LangGraph workflow.

## Setup

Install Docker, then from this folder:

```bash
copy .env.example .env
```

On macOS or Linux, use `cp .env.example .env` instead.

Put your OpenAI key in `.env` as `OPENAI_API_KEY`.

Put your LangSmith key in `.env` as `LANGSMITH_API_KEY` and set `LANGSMITH_TRACING=true`. Each job is one trace in the `formulary-check` project at [smith.langchain.com](https://smith.langchain.com): the LangGraph stages, the summary, the critical points, each medication verdict, and the embedding calls. Restart the worker after changing `.env`.

```bash
docker compose up --build
```

In a second terminal:

```bash
docker compose exec api python -m app.seed
```

Open the app at `http://localhost:8080`.

Reviewer login, already created by the seed command:

- Email: `reviewer@example.com`
- Password: `Reviewer123!`

Upload `primary_document_medical.docx`. The seeded formulary is already selected. Additional DOCX formularies can be added from **Add formulary** in the application header; each drug monograph must use the Heading 2 style.

The API remains at `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`.

To work on the UI locally, with the API running on port 8000:

```bash
cd frontend
npm install
npm run dev
```

The dev server is at `http://localhost:5173` and proxies `/api` to the backend.

Run the tests from `backend` after `pip install -r requirements.txt`:

```bash
cd backend
pytest
```

## What happens to a document

`POST /jobs` stores the file and writes the document, job, and eight stage rows in one database transaction. The response is the job id. The request does not wait for the model.

The worker claims the oldest queued job and runs this sequence:

`parsed` → `chunked` → `embedded` → `summarized` → `key_points` → `entities` → `verified` → `done`

`GET /jobs/{id}/events` is a server-sent event stream of those stages. `GET /jobs/{id}/result` returns the summary, critical points, medications, and flags after the job succeeds.

Only the formulary is embedded. The discharge summary is parsed, including Word tables, and sent to the model as page-labeled text. A medication table is read directly so dose, route, and frequency are kept. A document without that table still uses the model for extraction. Chunk and embed stages finish immediately when that formulary was indexed by an earlier job.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/signup` | Create an account and return a JWT |
| POST | `/auth/login` | Return a JWT |
| GET | `/auth/me` | Current user |
| GET | `/references` | Formularies the user can select |
| POST | `/references` | Upload a DOCX formulary |
| POST | `/jobs` | Upload a PDF or DOCX and a `reference_id` |
| GET | `/jobs` | The current user's jobs |
| GET | `/jobs/{id}` | Status and stage timings |
| GET | `/jobs/{id}/events` | Live stage events |
| GET | `/jobs/{id}/result` | Summary, critical points, medications, flags |
| GET | `/jobs/{id}/file` | Original primary file |

Send `Authorization: Bearer <token>` on every route except signup and login. A job owned by someone else is a 404.

Each flag status is `supported`, `contradicted`, or `unsupported`. A flag includes the formulary quote, section, and page when a passage was retrieved. If none was, the explanation says so and the citation is empty.

## Schema

- `users` — email and password hash
- `references` — formulary file; `indexed_at` is set after its embeddings exist
- `documents` — a primary file owned by one user
- `jobs` — queued, running, succeeded, or failed, plus the summary and critical points
- `job_stages` — one row per pipeline stage, with status and timestamps
- `chunks` — formulary monograph text and a 1536-dimension pgvector embedding
- `medications` — structured prescriptions extracted from the primary document
- `flags` — one verdict per medication

The worker claims jobs with `FOR UPDATE SKIP LOCKED`.

## Critical-point ranking

A critical point is a patient instruction from the primary document whose omission could change how a medicine is taken or delay required care. The model ranks candidates in this order:

1. Duration limits, stop rules, and serious side effects that require action.
2. Required administration timing and instructions not to stop a medicine abruptly.
3. Time-bound clinical follow-up and laboratory monitoring.
4. Expected, non-urgent adverse effects and general counseling.

Every point must include an exact quote from the primary document. The backend drops a point when that quote is not found, so the list cannot introduce new clinical advice.

## Retrieval evaluation

`backend/evaluation/retrieval_golden.json` is a small versioned golden set containing exact names, punctuation and spelling variants, semantic descriptions, and drugs that are absent from the formulary. Run it after the reference has been indexed:

```bash
cd backend
python -m evaluation.evaluate_retrieval
```

The report includes micro precision, recall, Precision@1, mean reciprocal rank (MRR), and the unsupported-query rejection rate. Precision measures how many returned monographs are relevant; recall measures how many expected monographs were found. Precision@1 and MRR expose ranking problems, while unsupported rejection catches unrelated passages returned for absent drugs. The checked-in 15-query set currently scores 1.000 on all five metrics. This is a development sanity set, not evidence of production quality. For a production set, clinicians would label de-identified medication queries and relevant monographs, and CI would compare these metrics with a checked-in baseline before retrieval changes are accepted.

## Decisions

The workflow is a straight LangGraph graph because every document takes the same steps. Verification loops over the extracted medications in ordinary Python. A later use case would be a new graph that reuses parsing, pgvector search, and the job runner.

The formulary is split on Heading 2, so each drug monograph is one chunk. The quick-reference section is a separate chunk. Embeddings use `text-embedding-3-small`. Chat uses `gpt-4o-mini`. Both names are set in `.env`.

Retrieval looks up the extracted drug name against monograph titles first. `Cordizem XR` matches the chunk titled `Cordizem-XR` because punctuation and case are ignored. A single insertion, deletion, or substitution can use that monograph too. A short unknown drug name is rejected instead of being semantically matched to a similarly spelled but different drug; this prevents `Pranixol` from retrieving `Pravoxil`. Longer descriptive queries use vector search: the closest four chunks within a cosine distance of 0.55 are kept. The verdict quote must appear in a retrieved passage; otherwise the flag is `unsupported` and has no citation. Critical points are kept only when their quote appears in the primary document.

The upload transaction contains the document row, the job row, and the eight stage rows. The file is written first and deleted if that transaction rolls back.

Logs are JSON lines with `job_id` and `stage`.

## Tests

- A Velantine dose above the monograph maximum is stored as `contradicted` and keeps the formulary quote.
- No retrieved passage is stored as `unsupported` with an empty citation.
- An open-ended prescription is not treated as a duration conflict when the monograph states no duration limit.
- A real dose conflict is preserved when an unsupported duration claim is removed.
- One user receives 404 for another user's job, result, and file.
- The sample formulary splits into the eight monographs plus the quick-reference section.
- `Cordizem XR` resolves to the `Cordizem-XR` monograph by title, without a vector search.
- Retrieval metric calculations include false-positive passages and unsupported queries.

## Extra credit

LangSmith tracing is included for job-level LangGraph, model, and embedding traces. Deep-linking into the rendered reference and duplicate-upload detection were not attempted.

## Known limits

Page numbers in a DOCX exist when the file contains page breaks. Otherwise the text is page 1 and the citation uses the monograph section name.

A worker updates a heartbeat while a job is running. If that heartbeat is older than 45 seconds, the next status read marks the job failed instead of leaving it running. Restarting the worker still requeues a job that is running at startup.

Duplicate upload detection and a second workflow are not in this version.
