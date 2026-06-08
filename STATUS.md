# Build Status

Working plan: `C:\Users\Teddy\.claude\plans\so-what-have-i-dapper-cookie.md`

## Working end-to-end (committed)
- **Ingest:** `ingest/` — Adzuna/USAJobs/ATS -> Redpanda -> dlt -> Snowflake `RAW.JOB_POSTINGS` (~1,061 rows).
- **Infra:** `infra/` Terraform (XS warehouse, db, RAW + ANALYTICS schemas, role, credit-cap monitor) — applied.
- **dbt (Snowflake):** staging -> `fct_posting_snapshots` (incremental) -> `int_jobs_resolved` / `int_job_lifecycle` (repost counting) -> marts: `mart_posting_lifecycle` (ghost flag), `mart_market_trends`, `mart_salary_benchmarks` (junk-salary filtered).
- **AI (Phase 4, COMPLETE):** `ai/extract.py` -> `RAW.JOB_ENRICHMENT` (skills/seniority/remote/role); `ai/fit_score.py` -> `RAW.JOB_FIT` (0-100 fit vs profile.json). Both Claude Haiku, rate-limited 45/min, concurrent, cached. dbt: `int_jobs_enriched`, `int_job_skills` (+ `skill_aliases` seed), `mart_skill_demand`, `mart_active_jobs` (fit-ranked matches).
- Cortex SQL functions NOT available on trial -> AI runs via the Claude API.

## Next up: Phase 6 (Dagster orchestration)
Automate the manual run sequence (producer -> dlt -> dbt -> extract -> dbt -> fit_score -> dbt)
on a schedule; the per-step caching makes re-runs cheap. Then Phase 7 (Evidence + Streamlit),
Phase 8 (Snowpark ML predictor), Phase 9 (v2 self-serve).

## Resuming in a new session
Open the job-market-intel folder, then tell Claude: "Read STATUS.md and the plan at
C:\Users\Teddy\.claude\plans\so-what-have-i-dapper-cookie.md; we're resuming the build at
Phase 6." Everything is committed to git (see `git log`), so the code + history are the
source of truth.

## Candidate refinements (noted, not blocking)
- Same role under different location strings (e.g., "Alaska" vs "Remote") splits into
  separate posting_keys since location is part of the key.
- Many roles cap at fit 72 because remote_type is "unknown" (thin Adzuna descriptions).

## Everyday run sequence
```powershell
cd "C:\Users\Teddy\Desktop\job-market-intel"
.\load-env.ps1                      # env vars for terraform/dbt (new terminal each time)
docker compose up -d                # Redpanda (if ingesting)
python -m ingest.producer           # fetch -> Redpanda
python -m ingest.dlt_pipeline       # Redpanda -> Snowflake RAW
python -m ai.extract 1000           # Claude extraction (reads .env itself)
python -m ai.fit_score 1000         # Claude fit-scoring
cd dbt; dbt build                   # build all models + tests
```
Note: dbt/Python read Snowflake creds differently — dbt needs `.\load-env.ps1`; the Python
scripts read `.env` directly via load_dotenv.

## Remaining phases
5 Elementary data quality · 6 Dagster orchestration · 7 Evidence + Streamlit serving ·
8 Snowpark ML ghost-job predictor · 9 v2 self-serve (resume->matches) · 10 integration + deploy.

## Known data-quality findings (good writeup material)
- Adzuna descriptions are thin -> fewer skills extracted (coverage correlates with source).
- "Other" role bucket is large -> federal/non-data postings (USAJobs heavy).
- Skill aliases normalized via seed (GCP/Google Cloud Platform, Spark/Apache Spark).
