# Folioport — AI Portfolio + Job Matcher

Folioport is a full-stack starter project with a ChatGPT-style public portfolio assistant, a public job-description matcher, and an authenticated admin workspace.

## What is included

- **Frontend:** React, Vite, React Router, responsive CSS, light/dark black-and-white themes, Expletus Sans / Ubuntu / Philosopher / Fira Mono fonts.
- **Backend:** Python + Flask REST API, Flask-SQLAlchemy, JWT-protected admin endpoints, password hashes, upload parsing, and validation.
- **SQL source of truth:** TiDB Cloud (MySQL-compatible). If you leave `DATABASE_URL` unset, a local SQLite database is used for quick UI development only.
- **AI:** Groq chat completions, with system prompts for portfolio Q&A, job-description extraction, and career guidance.
- **RAG:** Qdrant vector retrieval, local FastEmbed sentence embeddings, chunked portfolio records, public/private retrieval filtering, and manual reindexing.
- **Job matcher:** Accepts pasted text or `.txt`, `.pdf`, and `.docx` files. The language model extracts requirements; Python calculates the score from public portfolio records. A skill is an exact match only when it is listed in saved skills. Project, experience, and vector-search evidence is labelled related rather than treated as confirmed skill proficiency.
- **Admin:** Profile, Skills, Education, Projects, and Experience pages. Each page includes a PDF/DOCX resume import that extracts only that page's fields for editable review. Existing records are retained; extracted records are appended, and non-empty profile fields are updated.

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
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=openai/gpt-oss-20b
QDRANT_URL=https://your-cluster-id.region.cloud.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key
QDRANT_COLLECTION=folioport_portfolio
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

**TiDB:** Set `TIDB_URL` to the complete SQLAlchemy-compatible MySQL URL and TLS parameters shown by your TiDB Cloud connection dialog. The app also accepts `DATABASE_URL` as an alias. URL-encode special characters in the username/password. Do not put credentials into React or commit `.env` files. The example query parameters are a starting point; follow the connection options provided for your specific TiDB cluster. Leaving both variables unset falls back to SQLite for local UI experiments only.

**Qdrant:** Folioport connects to Qdrant Cloud using `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION`. The configured `sentence-transformers/all-MiniLM-L6-v2` embedding model has 384 dimensions. The vector collection size is taken from generated vectors; if you change embedding models, rebuild the collection with **Rebuild index** so the stored vectors use one consistent model/size.

### Create your private admin user

Run this once after configuring the database:

```bash
python -m scripts.create_admin
```

Enter a username, email, and a password of at least 12 characters. Passwords are hashed; there is no public admin registration. For production, use a password manager and keep the secrets out of source control.

### Start Flask

```bash
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
3. To import a resume, upload a text-based PDF or DOCX in **Profile**, then review and edit every parsed section before saving. Resume text and detected links are sent to the configured AI provider for extraction; the uploaded file is not stored. Scanned PDFs require OCR. Import does not change public visibility.
4. Add Skills with a category, level, experience years, evidence, and aliases. Category suggestions are loaded from saved skill types with common defaults offered. Skills, education, projects, and experience are public portfolio records.
5. Add Education, Projects, and Experience. Enter experience dates as `MM/YYYY` or full dates as `DD/MM/YYYY`. Use detailed descriptions, technologies, outcomes, GitHub/demo links, and evidence you can substantiate.
6. Use **Rebuild index** in the admin sidebar after bulk updates or when Qdrant was offline during a save.
7. Visit `/` to use the public AI portfolio chat and `/jobmatcher` to analyse a job description.

You need to enter your actual portfolio records through the admin pages; the application does not invent real profile information or include fake candidate data.

## 5. API map

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| GET | `/api/health` | Public | API/database health check |
| POST | `/api/auth/login` | Public | Admin login; returns an access token |
| GET | `/api/auth/me` | Admin JWT | Current admin identity |
| GET | `/api/public/portfolio` | Public | Public profile, skills, education, projects, experience |
| POST | `/api/chat` | Public | Grounded portfolio question-answering |
| POST | `/api/job-match` | Public | Analyse pasted JD or uploaded TXT/PDF/DOCX |
| GET/PATCH | `/api/admin/profile` | Admin JWT | Read / save one profile field per request |
| POST | `/api/admin/resume/parse` | Admin JWT | Parse uploaded PDF/DOCX into an editable, unsaved preview |
| POST | `/api/admin/resume/import` | Admin JWT | Save reviewed profile details and append reviewed portfolio records |
| GET/POST/PUT/DELETE | `/api/admin/skills` | Admin JWT | Skill CRUD |
| GET/POST/PUT/DELETE | `/api/admin/education` | Admin JWT | Education CRUD |
| GET/POST/PUT/DELETE | `/api/admin/projects` | Admin JWT | Project CRUD |
| GET/POST/PUT/DELETE | `/api/admin/experience` | Admin JWT | Experience CRUD |
| POST | `/api/admin/reindex` | Admin JWT | Rebuild the vector index |

CRUD update/delete URLs append `/<record_id>`, e.g. `PUT /api/admin/projects/3`; `DELETE` on a collection URL removes all its records. All admin routes require `Authorization: Bearer <token>`.

## 6. How the application works

### Portfolio chat

The browser sends the conversation to `POST /api/chat`. Flask combines the question with relevant structured SQL records and public Qdrant passages, then streams the model response back to the browser. Portfolio content is treated as data, not instructions. The system prompt directs the assistant to answer in third person, stay grounded in the saved portfolio, and avoid private profile fields. SQL is the source of truth; Qdrant is a derived retrieval index.

### Resume import

Each admin page sends an uploaded resume to the authenticated parse endpoint with its own extraction scope. The backend extracts PDF/DOCX text and asks the configured model for structured fields for that page only. The UI shows an editable preview; the user reviews it before importing. Uploads are parsed in memory and are not saved as files. Scanned PDFs require OCR, which is not included.

### Job description matching

1. The endpoint accepts pasted text or extracts text from TXT, PDF, or DOCX. Scanned/image-only PDFs are unsupported because OCR is not included.
2. Groq converts the job description into a validated JSON structure: required and preferred skills, responsibilities, experience requirements, education requirements, and keywords. Duplicate skill names are removed and obvious aliases are normalized.
3. Python loads the **public** SQL portfolio. Exact skill matches compare normalized names against saved skill records. Mentions in project/experience/profile text are related evidence, not proof of a saved skill.
4. Qdrant may surface additional public related passages. Only results at or above the retrieval threshold are shown as related; their similarity value is a retrieval signal, not a probability.
5. The scorer uses required/preferred skill coverage and, when the JD provides measurable information, experience duration, project relevance, and education. A matched skill earns full credit, related evidence earns partial credit, and a gap earns none. Missing categories are omitted and the remaining component weights are normalized.
6. Report text is assembled deterministically from the scored evidence. The model does not invent the candidate report or control the numeric score.

The estimate supports candidate preparation; it is not a hiring decision or prediction. Keyword extraction and semantic retrieval can miss context or return imperfect neighbours, so users should inspect the evidence and correct their portfolio data.

### Data and request flow

```text
Browser (React/Vite)
  ├─ Public chat ───────> Flask chat route ──> SQL portfolio + Qdrant ──> Groq streaming
  ├─ Job description ──> Flask matcher ─────> Groq requirement extraction
  │                                         └─> public SQL + Qdrant evidence ──> Python score/report
  └─ Admin pages ──────> JWT-protected Flask routes ──> SQL writes ──> Qdrant sync
```

SQL remains authoritative for all portfolio records. Vector indexing improves retrieval but is rebuildable; if indexing is unavailable, the admin API reports a warning and the user can reindex from the admin sidebar.

## 7. Repository map

```text
backend/
  app/
    routes/          Flask API endpoints (public, chat, admin, job matcher)
    services/        AI, portfolio, RAG, resume parsing, matching
    models.py        SQLAlchemy data models
    utils/           serialization, text handling, validation
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
Current verification: **36 backend tests passed** and `npm run build` completed successfully. The fixed RAG fixtures assert at least 0.8 context precision and recall; these are fixture thresholds, not a production accuracy claim.

Build the frontend from `frontend`:

```bash
npm run build
```

## 9. Key security and production notes

- Keep all secrets in environment variables. Do not expose `GROQ_API_KEY`, TiDB credentials, or `QDRANT_API_KEY` in Vite variables.
- Admin APIs use JWT authentication and hashed passwords; public pages do not expose admin write endpoints.
- For production, serve everything over HTTPS, rotate strong `SECRET_KEY` and `JWT_SECRET_KEY`, add login rate-limiting and audit logging, set strict CORS origins, consider short-lived tokens with refresh/revocation, and move browser auth to secure HttpOnly cookies (requires matching CORS/CSRF design).
- Add Alembic/Flask-Migrate schema migrations before evolving a production TiDB schema. `db.create_all()` is intentionally used only to bootstrap this starter and does not migrate existing tables.
- Add request-rate limits to public AI endpoints, cost controls, monitoring, virus scanning for uploads, retention rules, and a privacy notice before opening to the public.
- Qdrant indexing after a database save is best-effort. If the vector provider is offline, SQL remains saved and the API returns an `index_warning`; rebuild from the admin sidebar when connectivity returns.
- Add tests and error monitoring before real job applicants use this tool. Avoid using results as the sole basis for a hiring or employment decision.

## 10. Common troubleshooting

- **Database connection failed:** verify `TIDB_URL`, TiDB hostname, port `4000`, database/user privileges, URL-encoded credentials, TLS settings, and the exact connection string from the TiDB console.
- **AI not configured:** set `GROQ_API_KEY` in `backend/.env`, restart Flask, and verify `GROQ_MODEL` is currently available to your Groq account.
- **Qdrant is unavailable:** check `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION`. Use the admin reindex action after reconnecting.
- **CORS error:** set `CORS_ORIGINS` to the exact frontend origin including scheme and port, restart Flask, then hard-refresh the browser.
- **No PDF text:** scanned/image-based PDFs are not OCR'd by this code. Use a text-based PDF or paste the JD into the text box.
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
5. Have production credentials ready in their providers: a TiDB Cloud connection URL, a Groq API key, and a Qdrant Cloud URL/API key. Do not put these in GitHub source files or GitHub Actions.

### Deploy the API to Render

1. In Render, choose **New → Blueprint**, connect the GitHub repository, and select the branch to deploy. Render reads `render.yaml`; confirm the service is named `folioport-api` and uses `backend` as its root directory.
2. Supply the Blueprint's `sync: false` values in Render's environment prompt or service **Environment** settings:

   | Variable | Value |
   | --- | --- |
   | `TIDB_URL` | Full TiDB SQLAlchemy URL, including the TLS query options from TiDB Cloud |
   | `CORS_ORIGINS` | The exact expected Vercel origin, e.g. `https://your-project.vercel.app` (no trailing slash; correct it after Vercel creates the site if needed) |
   | `GROQ_API_KEY` | Secret key from Groq |
   | `QDRANT_URL` | Qdrant Cloud cluster URL |
   | `QDRANT_API_KEY` | Secret key from Qdrant Cloud |

   Render generates `SECRET_KEY` and `JWT_SECRET_KEY`; do not replace them with weak or shared values. The Blueprint sets `FLASK_DEBUG=0`, Python 3.12, the model defaults, Gunicorn, and `/api/health` as its health-check path.
3. **Configure TiDB before the first successful app start.** This project runs its schema bootstrap at startup and has MySQL/TiDB-specific schema compatibility SQL. Do not rely on Render's ephemeral local disk/SQLite for production data, and do not substitute a Render PostgreSQL URL. Use a TiDB Cloud database and the exact TLS-enabled connection string. URL-encode special characters in the username/password.
4. Wait for the first deployment to complete. Copy the service URL, for example `https://folioport-api.onrender.com`, and open:

   ```text
   https://YOUR-RENDER-SERVICE.onrender.com/api/health
   ```

   Confirm the JSON reports `"database": "connected"`. If the service fails to start, inspect Render's deploy logs first, then verify the database URL/TLS and required environment variables.
5. In the Render service's **Shell**, run `python -m scripts.create_admin` and follow the prompts to create the private admin login. Use a unique, strong password. Do not put the password in the repo or a deployment command.

### Deploy the frontend to Vercel

1. In Vercel, choose **Add New → Project**, import the same GitHub repository, and set **Root Directory** to `frontend`.
2. Use the Vite settings (normally detected automatically):
   - Build command: `npm run build`
   - Output directory: `dist`
   - Install command: `npm install` (or Vercel's detected npm install)
3. Add this environment variable for **Production** (and Preview only if you intend to use previews):

   ```text
   VITE_API_URL=https://YOUR-RENDER-SERVICE.onrender.com/api
   ```

   This value is compiled into public browser code; it must contain only the API base URL. Never add Groq, TiDB, Qdrant, or admin credentials to Vercel.
4. Deploy. Visit the generated Vercel URL and refresh `/jobmatcher` and `/admin/login` directly. The included `frontend/vercel.json` rewrite supports these client-side routes.
5. Copy the final Vercel production origin (scheme + domain only, no path or trailing slash) into Render's `CORS_ORIGINS`. Save the environment change and redeploy/restart the Render service. The backend checks exact origins; wildcard Vercel preview domains are not accepted by this project. For a preview, add that specific preview URL to `CORS_ORIGINS` or test against production only.
6. Pushes to the connected GitHub branch trigger deployments. Vercel can create preview deployments for pull requests; Render deploys pushes to its selected branch. After changing `VITE_API_URL` in Vercel, trigger a new Vercel deployment because Vite embeds it at build time.

### Production smoke test and common failures

- Open the Render `/api/health` URL and verify `database` is `connected`.
- Open the Vercel site, refresh `/jobmatcher`, sign into `/admin/login`, and try a public chat and job match.
- In browser developer tools, a CORS error usually means `CORS_ORIGINS` is missing the exact Vercel origin, has a trailing slash, or Render has not restarted since the change.
- A frontend request to `127.0.0.1:5000` means `VITE_API_URL` was missing/wrong at Vercel build time; fix it and redeploy.
- A 503 from AI or matching endpoints usually means Groq or Qdrant credentials/configuration are missing or invalid. Check Render logs; keep provider keys only in Render's environment settings.
- If admin login fails, confirm the account was created against the same production TiDB database used by the Render service.
- The first semantic search can be slower while the embedding model initializes/downloads. Render's local filesystem is not a durable vector store; Qdrant Cloud and TiDB remain the hosted data services.

### Official platform documentation

- [Render: Deploy a Flask app](https://render.com/docs/deploy-flask)
- [Render: Blueprint specification](https://render.com/docs/blueprint-spec)
- [Render: Configure a Python version](https://render.com/docs/python-version)
- [Vercel: Deploy Vite projects](https://vercel.com/docs/frameworks/frontend/vite)
- [Vercel: Git deployments](https://vercel.com/docs/git)

## 12. ATS-ready project summary

**Folioport | Full-Stack AI Portfolio and Job Matcher**

Built a React/Vite and Flask application with JWT-protected portfolio administration, scoped PDF/DOCX resume parsing, streamed AI portfolio Q&A, and public-data retrieval-augmented generation (RAG) using Qdrant. Implemented a deterministic job-fit scorer that separates explicit saved-skill matches from related vector/text evidence, normalizes available score components, and returns inspectable gaps and evidence. Added offline tests for matcher classification/scoring, public-data isolation, prompt-injection boundaries, and RAG context precision/recall fixtures; verified 36 backend tests and a production frontend build.

**Technologies:** Python, Flask, SQLAlchemy, React, Vite, Groq, Qdrant, FastEmbed, TiDB/MySQL, SQLite, JWT, unittest.

## 13. Suggested next improvements

1. Expand automated coverage for authentication, CRUD validation, and additional real-world resume/JD parsing edge cases.
2. Add Alembic migrations and a dedicated reindex job/queue for large portfolios.
3. Add chat conversation export, citations linking to individual portfolio records, and an admin preview of exactly what the public sees.
4. Add user-defined weights, role-specific résumé tailoring, export-to-PDF, and a side-by-side JD evidence table.
5. Add rate limiting, monitoring, expanded prompt-injection evaluation, secure cookie auth, backups/restore, and deployment automation for additional hosting providers.
