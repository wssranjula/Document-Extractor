# Document Verification API

Backend for checking a hospital discharge summary against an institutional formulary. A job returns immediately, then a worker runs one fixed LangGraph workflow.

## Setup

Install Docker, then from this folder:

```bash
copy .env.example .env
```

On macOS or Linux, use `cp .env.example .env` instead.

Put your OpenAI key in `.env` as `OPENAI_API_KEY`.

```bash
docker compose up --build
```

In a second terminal:

```bash
docker compose exec api python -m app.seed
```

The API is at `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`.

Reviewer login, already created by the seed command:

- Email: `reviewer@example.com`
- Password: `Reviewer123!`

Upload `primary_document_medical.docx` with the seeded reference id from `GET /references`.

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

Only the formulary is embedded. The discharge summary is parsed and sent to the model as page-labeled text. Chunk and embed stages finish immediately when that formulary was indexed by an earlier job.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/signup` | Create an account and return a JWT |
| POST | `/auth/login` | Return a JWT |
| GET | `/auth/me` | Current user |
| GET | `/references` | Formularies the user can select |
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

## Decisions

The workflow is a straight LangGraph graph because every document takes the same steps. Verification loops over the extracted medications in ordinary Python. A later use case would be a new graph that reuses parsing, pgvector search, and the job runner.

The formulary is split on Heading 2, so each drug monograph is one chunk. The quick-reference section is a separate chunk. Embeddings use `text-embedding-3-small`. Chat uses `gpt-4o-mini`. Both names are set in `.env`.

Retrieval looks up the extracted drug name against monograph titles first. `Cordizem XR` matches the chunk titled `Cordizem-XR` because punctuation and case are ignored. A single close spelling, such as a missing letter, uses that monograph too. Vector search runs only when no title matches: the medication name, dose, route, frequency, duration, and indication are embedded, and the closest four chunks within a cosine distance of 0.55 are kept. The verdict quote must appear in a retrieved passage; otherwise the flag is `unsupported` and has no citation. Critical points are kept only when their quote appears in the primary document.

The upload transaction contains the document row, the job row, and the eight stage rows. The file is written first and deleted if that transaction rolls back.

Logs are JSON lines with `job_id` and `stage`.

## Tests

- A Velantine dose above the monograph maximum is stored as `contradicted` and keeps the formulary quote.
- No retrieved passage is stored as `unsupported` with an empty citation.
- One user receives 404 for another user's job, result, and file.
- The sample formulary splits into the eight monographs plus the quick-reference section.
- `Cordizem XR` resolves to the `Cordizem-XR` monograph by title, without a vector search.

## Known limits

Page numbers in a DOCX exist when the file contains page breaks. Otherwise the text is page 1 and the citation uses the monograph section name.

A worker that dies mid-job leaves that job `running`. The next worker start queues it again and reruns it.

Duplicate upload detection and a second workflow are not in this version.
