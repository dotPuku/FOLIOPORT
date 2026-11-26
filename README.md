# Folioport — AI Portfolio + Job Matcher

Folioport is a full-stack starter project with a ChatGPT-style public portfolio assistant, a public job-description matcher, and an authenticated admin workspace.

## What is included

- **Frontend:** React, Vite, React Router, responsive CSS, light/dark black-and-white themes, Expletus Sans / Ubuntu / Philosopher / Fira Mono fonts.
- **Backend:** Python + Flask REST API, Flask-SQLAlchemy, HttpOnly cookie sessions with CSRF protection, password hashes, upload parsing, and validation.
- **SQL source of truth:** TiDB Cloud (MySQL-compatible). If you leave `DATABASE_URL` unset, a local SQLite database is used for quick UI development only.
- **AI:** Groq chat completions, with system prompts for portfolio Q&A, job-description extraction, and career guidance.
- **RAG:** Qdrant vector retrieval, local FastEmbed sentence embeddings, chunked portfolio records, indexed public/private filters, and a durable, bounded reindex queue.
- **Database evolution:** Alembic migrations run before the Render web process starts and are also available as a local command.
- **Operations:** Per-IP rate limits, JSON request timing logs, request IDs, and a database-aware health endpoint.
- **Job matcher:** Accepts pasted text or `.txt`, `.pdf`, `.doc`, and `.docx` files. The language model extracts requirements; Python calculates the score from public portfolio records. A skill is an exact match only when it is listed in saved skills. Project, experience, and vector-search evidence is labelled related rather than treated as confirmed skill proficiency.
- **Admin:** Profile, Skills, Education, Projects, and Experience pages. Each page includes a PDF/DOC/DOCX resume import that extracts only that page's fields for editable review. Existing records are retained; extracted records are appended, and non-empty profile fields are updated.

## 1. Prerequisites

- Python 3.11 or 3.12 recommended.
- Node.js 20.19+ or 22.12+ and npm (Vite 8 requirement).
- A TiDB Cloud database/user (recommended for the requested deployment), a Groq API key, and a Qdrant Cloud endpoint/key for hosted usage.
- Internet access the first time the local FastEmbed model is downloaded. Embeddings are generated locally; the Qdrant API key is not needed for local Qdrant mode.

## 2. Configure the backend

Open a terminal in `folioport/backend`.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
pip install -r requirements.txt
```

Edit `backend/.env`:

```dotenv
SECRET_KEY=use-a-long-random-secret
JWT_SECRET_KEY=use-a-different-long-random-secret
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
TIDB_URL=mysql+pymysql://USERNAME:PASSWORD@TIDB_HOST:4000/DATABASE_NAME?ssl_verify_cert=true&ssl_verify_identity=true
RATELIMIT_STORAGE_URI=memory://
TRUST_PROXY=0
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=openai/gpt-oss-20b
QDRANT_URL=https://your-cluster-id.region.cloud.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key
QDRANT_COLLECTION=folioport_portfolio
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

**TiDB:** Set `TIDB_URL` to the complete SQLAlchemy-compatible MySQL URL and TLS parameters shown by your TiDB Cloud connection dialog. The app also accepts `DATABASE_URL` as an alias. URL-encode special characters in the username/password. Do not put credentials into React or commit `.env` files. The example query parameters are a starting point; follow the connection options provided for your specific TiDB cluster. Leaving both variables unset falls back to SQLite for local UI experiments only.

**Qdrant:** Folioport connects to Qdrant Cloud using `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION`. The configured `sentence-transformers/all-MiniLM-L6-v2` embedding model has 384 dimensions. The vector collection size is taken from generated vectors; if you change embedding models, rebuild the collection with **Rebuild index** so the stored vectors use one consistent model/size.

`RATELIMIT_STORAGE_URI=memory://` is appropriate for the single Render Free instance, but counters are process-local and reset on restarts or spin-down. Use a shared Redis-compatible service if deploying multiple API instances or requiring limits that survive restarts. `TRUST_PROXY=0` is for local development; the Render Blueprint enables trusted proxy headers for client-IP rate limiting.

### Apply schema migrations

Run this after installing backend requirements and before starting Flask:

```powershell
python -m scripts.migrate_db
```

The migration command is repeatable. Its baseline creates missing tables without recreating existing ones, then the next revision adds the durable reindex queue and backfills known legacy skill/education fields. Existing portfolio rows are preserved; the baseline migration intentionally cannot be downgraded because it may represent pre-existing data.

### Create your private admin user

Run this after configuring the database. It applies pending migrations before creating or updating the account:

```bash
python -m scripts.create_admin
```

Enter a username, email, and a password of at least 12 characters. Passwords are hashed; there is no public admin registration. For production, use a password manager and keep the secrets out of source control.

### Start Flask

```bash
python -m scripts.migrate_db
python run.py
```

The API starts at `http://127.0.0.1:5000`. On first use, Qdrant collection/model setup may take a little time; FastEmbed downloads its model the first time if it is not cached.

## 3. Configure and start the frontend

Open a second terminal in `folioport/frontend`.

```bash
Copy-Item .env.example .env   # Windows PowerShell
npm install
npm run dev
```

On macOS/Linux, copy the frontend `.env.example` to `.env` with `cp .env.example .env`.

The Vite app is available at `http://127.0.0.1:5173`. In `frontend/.env`, set `VITE_API_URL=http://127.0.0.1:5000/api` if your Flask API runs elsewhere.

## 4. First-time setup / adding portfolio data

1. Sign in at `http://127.0.0.1:5173/admin/login`.
2. In **Profile**, edit each field and click its own Save button. Use the eye buttons to control public visibility. Phone and email remain private by default.
3. To import a resume, upload a text-based PDF, DOC, or DOCX in **Profile**, then review and edit every parsed section before saving. Resume text and detected links are sent to the configured AI provider for extraction; the uploaded file is not stored. Image-only documents require OCR. Import does not change public visibility.
4. Add Skills with a category, level, experience years, evidence, and aliases. Category suggestions are loaded from saved skill types with common defaults offered. Skills, education, projects, and experience are public portfolio records.
5. Add Education, Projects, and Experience. Enter experience dates as `MM/YYYY` or full dates as `DD/MM/YYYY`. Use detailed descriptions, technologies, outcomes, GitHub/demo links, and evidence you can substantiate.
6. Use **Rebuild index** in the admin sidebar after bulk updates or when Qdrant was offline during a save. It queues a database-backed job and processes five records per authenticated API request; the admin page can resume an unfinished job after reload.
7. Visit `/` to use the public AI portfolio chat and `/jobmatcher` to analyse a job description.

You need to enter your actual portfolio records through the admin pages; the application does not invent real profile information or include fake candidate data.

## 5. API map

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| GET | `/api/health` | Public | API/database health check |
| POST | `/api/auth/login` | Public | Admin login; sets a short-lived HttpOnly JWT cookie and returns a CSRF token |
| GET | `/api/auth/me` | Admin cookie | Current admin identity |
| GET | `/api/auth/csrf` | Admin cookie | Refresh the CSRF token after opening a new tab |
| POST | `/api/auth/logout` | Admin cookie + CSRF | Clear the admin session cookie |
| GET | `/api/public/portfolio` | Public | Public profile, skills, education, projects, experience |
| POST | `/api/chat` | Public | Grounded portfolio question-answering |
| POST | `/api/job-match` | Public | Analyse pasted JD or uploaded TXT/PDF/DOC/DOCX |
| GET/PATCH | `/api/admin/profile` | Admin cookie (+ CSRF for PATCH) | Read / save one profile field per request |
| POST | `/api/admin/resume/parse` | Admin cookie + CSRF | Parse uploaded PDF/DOC/DOCX into an editable, unsaved preview |
| POST | `/api/admin/resume/import` | Admin cookie + CSRF | Save reviewed profile details and append reviewed portfolio records |
| GET/POST/PUT/DELETE | `/api/admin/skills` | Admin cookie (+ CSRF for writes) | Skill CRUD |
| GET/POST/PUT/DELETE | `/api/admin/education` | Admin cookie (+ CSRF for writes) | Education CRUD |
| GET/POST/PUT/DELETE | `/api/admin/projects` | Admin cookie (+ CSRF for writes) | Project CRUD |
| GET/POST/PUT/DELETE | `/api/admin/experience` | Admin cookie (+ CSRF for writes) | Experience CRUD |
| POST | `/api/admin/reindex` | Admin cookie + CSRF | Queue a rebuild or return the active job |
| GET | `/api/admin/reindex/jobs/active` | Admin cookie | Find a queued/running rebuild |
| GET | `/api/admin/reindex/jobs/<job_id>` | Admin cookie | Read rebuild progress |
| POST | `/api/admin/reindex/jobs/<job_id>/process` | Admin cookie + CSRF | Process at most five records in one request |

CRUD update/delete URLs append `/<record_id>`, e.g. `PUT /api/admin/projects/3`; `DELETE` on a collection URL removes all its records. Admin requests use credentialed cookies; mutations also require the `X-CSRF-TOKEN` header. The API does not return or store bearer tokens in browser storage.

## 6. How the application works

### Portfolio chat

The browser sends the conversation to `POST /api/chat`. Flask combines the question with relevant structured SQL records and public Qdrant passages, then streams the model response back to the browser. Portfolio content is treated as data, not instructions. The system prompt directs the assistant to answer in third person, stay grounded in the saved portfolio, and avoid private profile fields. SQL is the source of truth; Qdrant is a derived retrieval index.

### Resume import

Each admin page sends an uploaded resume to the authenticated parse endpoint with its own extraction scope. The backend extracts PDF/DOC/DOCX text and asks the configured model for structured fields for that page only. The UI shows an editable preview; the user reviews it before importing. Uploads are parsed in memory and are not saved as files. Image-only documents require OCR, which is not included.

### Job description matching

1. The endpoint accepts pasted text or extracts text from TXT, PDF, DOC, or DOCX. Image-only documents are unsupported because OCR is not included.
2. Groq converts the job description into a validated JSON structure: required and preferred skills, responsibilities, experience requirements, education requirements, and keywords. Duplicate skill names are removed and obvious aliases are normalized.
3. Python loads the **public** SQL portfolio. Exact skill matches compare normalized names against saved skill records. Mentions in project/experience/profile text are related evidence, not proof of a saved skill.
4. Qdrant embeds skill requirements with their job-description evidence and batch-retrieves public portfolio passages for distinct responsibilities and education requirements. Only evidence from relevant record types above the relevance threshold contributes to project or education coverage; supporting passages are shown in the report. Similarity values are retrieval signals, not probabilities.
5. Exact skill matches require a saved skill name or recognized alias. Related evidence from project, experience, or semantic retrieval earns partial credit, while unsupported requirements remain gaps. Measurable years use structured dates/profile data; missing score categories are omitted and the remaining component weights are normalized.
6. Report text is assembled deterministically from scored requirements and retrieved evidence. The model does not invent the candidate report or control the numeric score.

The estimate supports candidate preparation; it is not a hiring decision or prediction. Keyword extraction and semantic retrieval can miss context or return imperfect neighbours, so users should inspect the evidence and correct their portfolio data.

### Data and request flow

```text
Browser (React/Vite)
  └─ /api/* ───────────> Vercel same-origin rewrite ──> Render Flask API
                                                   ├─ Public chat ──> SQL + Qdrant ──> Groq stream
                                                   ├─ Job match ────> Groq extraction + Python scoring
                                                   └─ Admin ────────> HttpOnly cookie + CSRF ──> SQL/Qdrant
```

The browser sends API calls to its own `/api/*` path. Vercel proxies those paths to Render, so the browser sees same-origin requests and the HttpOnly `SameSite=Lax` admin cookie works without custom domains. SQL remains authoritative for all portfolio records. Vector indexing improves retrieval but is rebuildable; if indexing is unavailable, the admin API reports a warning and the user can reindex from the admin sidebar.

### Reindex job flow

The admin API stores a `ReindexJob` and a snapshot of entity IDs in TiDB. The browser requests one batch at a time; each request processes no more than five records, updates job progress in SQL, and returns. This avoids requiring a persistent Render worker or one-off job, which are unavailable on Render Free. If the browser closes, the queued/running job remains in TiDB and the admin page resumes it on the next visit. Qdrant is cleared once before batches begin; while a rebuild is incomplete, public chat still has the SQL portfolio as its fallback context.

### Schema migration flow

`backend/migrations/versions/` contains the Alembic history. `python -m scripts.migrate_db` applies pending revisions and seeds the singleton profile if it does not exist. Render's start command runs that migration step before Gunicorn starts; local development and the admin-creation script use the same command. Do not edit deployed tables manually or reintroduce `db.create_all()` at application startup. For a schema change, edit the SQLAlchemy model, generate a revision with `python -m flask --app run:app db migrate -m "describe the change"`, review its `upgrade()` and `downgrade()` carefully, and test it against a disposable SQLite database before deploying to TiDB.

## 7. Repository map

```text
backend/
  app/
    routes/          Flask API endpoints (public, chat, admin, job matcher)
    services/        AI, portfolio, RAG, resume parsing, matching
    models.py        SQLAlchemy data models
    utils/           serialization, text handling, validation
  migrations/        Alembic environment and versioned schema changes
  scripts/           admin setup, migrations, and manual reindex tooling
  tests/             unittest coverage for APIs, RAG, imports, and matching
  run.py             local API entry point
frontend/
  src/pages/         public chat, job matcher, admin screens
  src/components/    shared UI and resume-import component
  src/api.js         browser-to-backend API client
  src/styles.css     app styles and responsive layouts
README.md             setup, architecture, API map, testing, limitations
```

## 8. Tests and evaluation

Run the backend tests from `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Or, after activating the virtual environment:

```bash
python -m unittest discover -s tests
```

The suite includes offline regression cases for public/private context handling, hostile prompt text, empty-field filtering, resume import flows, matching classifications, score behavior, and overlap-safe experience dates. The RAG evaluation fixture computes context precision and recall on fixed retrieval cases. These tests validate those fixtures and deterministic code paths; they do **not** establish live-model accuracy, production retrieval quality, or hiring validity.
Current verification: **49 backend tests passed** and `npm run build` completed successfully. The fixed RAG fixtures assert at least 0.8 context precision and recall; these are fixture thresholds, not a production accuracy claim.

Build the frontend from `frontend`:

```bash
npm run build
```

## 9. Key security and production notes

- Keep all secrets in environment variables. Do not expose `GROQ_API_KEY`, TiDB credentials, or `QDRANT_API_KEY` in Vite variables.
- Admin sessions use an eight-hour JWT in an `HttpOnly`, `Secure` (outside debug), `SameSite=Lax` cookie. State-changing admin requests require a CSRF token in `X-CSRF-TOKEN`; the browser keeps only that non-authenticating token in session storage.
- Production cookie login uses the Vercel `/api/*` rewrite to make browser requests same-origin. The browser talks to its Vercel hostname while Vercel proxies requests to Render; this works with the default `vercel.app` and `onrender.com` domains and does not require buying a custom domain.
- CORS allows only the configured frontend origins and credentials. Set `CORS_ORIGINS` to the exact HTTPS frontend origin; never use `*` with cookies.
- Flask-Limiter protects login (5/minute), chat (12/minute), job matching (10/minute), resume parsing (10/hour), and reindex processing (30/minute). Render Free uses in-memory counters; they are per process and reset on restarts/spin-down. Configure a shared Redis-compatible storage URI before scaling or relying on persistent limits.
- The API logs structured request IDs, route, status, and request time to Render logs; chat separately logs retrieval and completion time. `/api/health` returns 503 when the SQL database cannot be reached. These are operational logs and health checks, not a hosted alerting/metrics service.
- Alembic migrations run before Gunicorn starts. `db.create_all()` is reserved for isolated test setup; it is not the production migration mechanism.
- Qdrant indexing after a database save is best-effort. If the vector provider is offline, SQL remains saved and the API returns an `index_warning`; rebuild from the admin sidebar when connectivity returns.
- Resume/JD parsing is text extraction only; scanned/image-only documents need OCR outside this project. Avoid using matcher results as the sole basis for a hiring or employment decision.

## 10. Common troubleshooting

- **Database connection failed:** verify `TIDB_URL`, TiDB hostname, port `4000`, database/user privileges, URL-encoded credentials, TLS settings, and the exact connection string from the TiDB console.
- **AI not configured:** set `GROQ_API_KEY` in `backend/.env`, restart Flask, and verify `GROQ_MODEL` is currently available to your Groq account.
- **Qdrant is unavailable:** check `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION`. Use the admin reindex action after reconnecting.
- **CORS error:** set `CORS_ORIGINS` to the exact frontend origin including scheme and port, restart Flask, then hard-refresh the browser.
- **Admin sign-in fails on hosted domains:** verify that the frontend uses its Vercel `/api` path, that `frontend/vercel.json` points to the correct Render service URL, and that Render's `CORS_ORIGINS` contains the exact Vercel production origin.
- **Too many requests:** wait for the applicable rate-limit window to expire. Memory-backed counters reset when the Render service restarts.
- **Migration error:** inspect Render deploy logs, confirm the TiDB URL/TLS options and migration privileges, then retry the deploy. Migrations preserve existing records; do not delete the `alembic_version` table to force a rerun.
- **No readable document text:** scanned/image-based documents are not OCR'd by this code. Use OCR, upload a text-based file, or paste the JD into the text box.
- **Admin cannot sign in:** run `python -m scripts.create_admin` again to update the existing admin password, and ensure this command uses the same `TIDB_URL` / `DATABASE_URL` as Flask.

## 11. Publish with GitHub, Render, and Vercel

Folioport is a monorepo with a static React/Vite frontend and a Flask API. Render serves the backend; Vercel serves the frontend. The root [render.yaml](./render.yaml) configures the Render Blueprint service, and [frontend/vercel.json](./frontend/vercel.json) routes React Router paths back to the SPA entry point.

### Before publishing

1. Create or choose a GitHub repository. If creating one on GitHub, make it empty (do not initialize it with another README or license).
2. From the project folder in PowerShell, check whether this workspace is already a Git repository:

   ```powershell
   git status
   ```

   If it reports that this is not a repository, initialize it and connect it to the empty GitHub repository:

   ```powershell
   git init -b main
   git remote add origin https://github.com/YOUR-USER/YOUR-REPOSITORY.git
   ```

3. Before staging, confirm `backend/.env` is ignored and is not already tracked:

   ```powershell
   git check-ignore -v backend/.env
   git ls-files backend/.env
   ```

   The first command should show the ignore rule; the second should print nothing. If the second command lists the file, untrack it with `git rm --cached backend/.env` before continuing. `.env` contains credentials: never commit it, paste its contents into an issue, or set those credentials as Vercel variables. If real credentials were ever pushed, rotate them before deploying. Only the placeholder `backend/.env.example` belongs in Git.
4. Stage and push the source:

   ```powershell
   git add .
   git status --short
   git commit -m "Prepare Folioport for deployment"
   git push -u origin main
   ```

   If the folder already has a Git remote, use its existing branch and push normally instead of initializing it or adding a second remote. Review the staged file list before committing.
5. Have service credentials ready in their providers: a TiDB Cloud connection URL, a Groq API key, and a Qdrant Cloud URL/API key. Render Free does not make these external services free; check each provider's current plans and usage limits. Do not put credentials in GitHub source files or GitHub Actions.

### Deploy the API to Render

1. In Render, choose **New → Blueprint**, connect the GitHub repository, and select the branch to deploy. Render reads `render.yaml`; confirm the service is named `folioport-api` and uses `backend` as its root directory.
2. Supply the Blueprint's `sync: false` values in Render's environment prompt or service **Environment** settings:

   | Variable | Value |
   | --- | --- |
   | `TIDB_URL` | Full TiDB SQLAlchemy URL, including the TLS query options from TiDB Cloud |
   | `CORS_ORIGINS` | Exact Vercel production origin, e.g. `https://your-project.vercel.app` (no trailing slash) |
   | `GROQ_API_KEY` | Secret key from Groq |
   | `QDRANT_URL` | Qdrant Cloud cluster URL |
   | `QDRANT_API_KEY` | Secret key from Qdrant Cloud |

   Render generates `SECRET_KEY` and `JWT_SECRET_KEY`; do not replace them with weak or shared values. The Blueprint selects the Free plan, sets `FLASK_DEBUG=0`, Python 3.12, the model defaults, one Gunicorn worker, and `/api/health` as its health-check path.
3. **Configure TiDB before the first successful app start.** Render applies the Alembic migrations before starting Gunicorn. Do not rely on Render's ephemeral local disk/SQLite for production data, and do not substitute a Render PostgreSQL URL. Use a TiDB Cloud database and the exact TLS-enabled connection string. URL-encode special characters in the username/password.
4. Wait for the first deployment to complete. Copy the service URL, for example `https://folioport-api.onrender.com`, and open:

   ```text
   https://YOUR-RENDER-SERVICE.onrender.com/api/health
   ```

   Confirm the JSON reports `"database": "connected"`. The Render URL is the upstream used by the Vercel API rewrite.
5. Render Free has no Shell/SSH access or one-off jobs, so create the admin account from your computer against the **same TiDB database** used by Render. In PowerShell, open the backend folder, enter the URL at the prompt, and run the existing script:

   ```powershell
   Set-Location backend
   $secureUrl = Read-Host "Production TiDB URL" -AsSecureString
   $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureUrl)
   try {
       $env:TIDB_URL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
       .\.venv\Scripts\python.exe -m scripts.create_admin
   } finally {
       Remove-Item Env:\TIDB_URL -ErrorAction SilentlyContinue
       [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
   }
   ```

   Use the backend virtual environment created during setup. Enter the URL at the masked prompt; do not put it directly in a command, source file, GitHub, or Vercel. The script asks for the admin username, email, and password and writes the account to TiDB. If it fails, check that TiDB allows connections from your local network and that the URL/TLS options are correct. Use a unique, strong password.

### Deploy the frontend to Vercel

1. In Vercel, choose **Add New → Project**, import the same GitHub repository, and set **Root Directory** to `frontend`.
2. Use the Vite settings (normally detected automatically):
   - Build command: `npm run build`
   - Output directory: `dist`
   - Install command: `npm install` (or Vercel's detected npm install)
3. Do not set `VITE_API_URL` to the Render host in Vercel. Production builds always use the same-origin `/api` path, and `frontend/vercel.json` proxies `/api/*` to `https://folioport-api.onrender.com/api/*`. Remove any old `VITE_API_URL` override from Vercel to keep the configuration clear. If Render assigns a different service URL, update the rewrite destination and redeploy Vercel. Never add Groq, TiDB, Qdrant, or admin credentials to Vercel.
4. Deploy. Visit the generated Vercel URL, refresh `/jobmatcher`, and sign into `/admin/login`. The included rewrite sends API requests to Render and routes other paths back to the SPA entry point.
5. Set Render's `CORS_ORIGINS` to the exact Vercel production origin, such as `https://dotpuku.vercel.app` (no trailing slash). Save and restart/redeploy the Render service. Use the actual Vercel production URL if it differs.
6. Visit the Vercel site, refresh `/jobmatcher`, sign into `/admin/login`, and try a public chat and job match. The browser stays on the Vercel origin for API calls, so the HttpOnly cookie is first-party; no custom domain is needed. Vercel preview deployments may require their exact preview origin in `CORS_ORIGINS` if you want to test API calls from previews.
7. Pushes to the connected GitHub branch trigger deployments. Vercel can create preview deployments for pull requests; Render deploys pushes to its selected branch.

### Render Free limits and post-deploy checks

Render Free is intended for hobby/testing use, not production workloads. Its web service has 0.1 CPU and 512 MB RAM, spins down after 15 minutes without inbound traffic, and can take about a minute to wake when the next request arrives. Free services share a 750-hour monthly allowance per workspace; exhausting it suspends Free services until the next month. The filesystem is ephemeral, with no persistent disk, Shell/SSH, or one-off job support. The Blueprint uses one Gunicorn worker to limit memory use and a longer request timeout for cold model initialization. Do not store portfolio data or SQLite databases on Render's filesystem. TiDB and Qdrant remain external hosted services; check their own pricing and limits.

- Open the Render `/api/health` URL and verify `database` is `connected`.
- Open the Vercel frontend, refresh `/jobmatcher`, sign into `/admin/login`, and try a public chat and job match.
- In browser developer tools, a CORS error usually means `CORS_ORIGINS` is missing the exact Vercel production origin, has a trailing slash, or Render has not restarted since the change.
- A failed request to `/api/*` may mean the Render service URL in `frontend/vercel.json` is wrong; correct the rewrite destination and redeploy Vercel. Production frontend code always uses `/api`, even if an old `VITE_API_URL` setting remains in Vercel.
- A 503 from AI or matching endpoints usually means Groq or Qdrant credentials/configuration are missing or invalid. Check Render logs; keep provider keys only in Render's environment settings.
- If Render logs show the process being killed or out-of-memory errors while FastEmbed initializes, the Free plan's 512 MB limit is insufficient for that workload; reduce usage or move embedding generation off the web process/upgrade the service rather than repeatedly restarting it.
- If admin login fails, confirm the account was created against the same TiDB database used by the Render service.
- The first semantic search can be slower while the embedding model initializes/downloads. Render Free's filesystem is temporary, so the model cache may need to download again after a restart or spin-down. Qdrant and TiDB remain the hosted data services.

### Official platform documentation

- [Render: Deploy a Flask app](https://render.com/docs/deploy-flask)
- [Render: Free instance limits](https://render.com/docs/free)
- [Render: Blueprint specification](https://render.com/docs/blueprint-spec)
- [Render: Configure a Python version](https://render.com/docs/python-version)
- [Vercel: Deploy Vite projects](https://vercel.com/docs/frameworks/frontend/vite)
- [Vercel: Git deployments](https://vercel.com/docs/git)

## 12. ATS-ready project summary

**Folioport | Full-Stack AI Portfolio and Job Matcher**

Built a React/Vite and Flask application with HttpOnly-cookie admin sessions and CSRF protection, scoped PDF/DOC/DOCX resume parsing, streamed AI portfolio Q&A, and public-data retrieval-augmented generation (RAG) using Qdrant. Implemented a deterministic job-fit scorer that separates explicit saved-skill matches from related vector/text evidence, normalizes available score components, and returns inspectable gaps and evidence. Added Alembic migrations, bounded database-backed reindex jobs, per-route rate limits, request monitoring, and offline tests for authentication, CRUD validation, migration paths, parsing edge cases, matcher behavior, prompt-injection boundaries, and RAG precision/recall fixtures.

**Technologies:** Python, Flask, SQLAlchemy, React, Vite, Groq, Qdrant, FastEmbed, TiDB/MySQL, SQLite, JWT, unittest.

## 13. Possible future enhancements

Potential extensions beyond the implemented scope include citations linking answers to individual portfolio records, a public-portfolio preview in the admin UI, configurable job-match weights, résumé export, expanded live-provider evaluation, and automated database backup/restore drills.
