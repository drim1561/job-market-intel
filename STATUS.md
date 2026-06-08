# Build Status

Working plan lives at: `C:\Users\Teddy\.claude\plans\so-what-have-i-dapper-cookie.md`

## Done (authored; not yet run)
- Repo scaffold: README, .gitignore, .env.example, requirements.txt, docker-compose.yml (Redpanda), profile.example.json, companies.yml. Git initialized on `main`.
- Canonical schema + entity-resolution key: `ingest/schema.py` (posting_key MERGES reposts; lifecycle counts them).
- Ingest: `ingest/producer.py`, `ingest/sources/{adzuna,usajobs,ats}.py`, `ingest/dlt_pipeline.py`.
- Terraform infra: `infra/*.tf` (XS warehouse, db, RAW + ANALYTICS schemas, role, credit-cap resource monitor).
- dbt core (Snowflake-native): `dbt/` project + profiles + packages + staging + `fct_posting_snapshots` (incremental) + `int_jobs_resolved` + `int_job_lifecycle` (repost counting) + `mart_posting_lifecycle` (clean list + ghost flag) + tests.

## Your setup tasks (free)
- [ ] Adzuna account -> ADZUNA_APP_ID / ADZUNA_APP_KEY
- [ ] USAJobs account -> USAJOBS_API_KEY / USAJOBS_USER_AGENT (your email)
- [ ] Anthropic API key -> ANTHROPIC_API_KEY
- [ ] Snowflake (have it): collect SNOWFLAKE_ACCOUNT / USER / PASSWORD
- [ ] Install Docker Desktop (running) + Terraform CLI
- [ ] `copy .env.example .env` and fill it in (edit .env, NOT .env.example)
- [ ] `copy infra\terraform.tfvars.example infra\terraform.tfvars`; set grant_to_user (UPPERCASE Snowflake user)
- [ ] (optional) verify ATS slugs in companies.yml

## Run sequence (once accounts + .env are ready)
1. `python -m venv .venv` then `.venv\Scripts\activate` then `pip install -r requirements.txt`
2. Set SNOWFLAKE_ACCOUNT/USER/PASSWORD as env vars, then in `infra/`: `terraform init && terraform apply`
3. `docker compose up -d`  (local Redpanda)
4. `python -m ingest.producer`  (fetch sources -> Redpanda)
5. `python -m ingest.dlt_pipeline`  (Redpanda -> Snowflake RAW)
6. `cd dbt && dbt deps && dbt build --profiles-dir .`  -> populates mart_posting_lifecycle

## Next to build (no accounts needed)
- Remaining marts: mart_market_trends, mart_salary_benchmarks (pure SQL).
- Phase 4: AI extraction + fit-scoring (then mart_active_jobs, mart_skill_demand).
- Phases 5-10: Elementary, Dagster, BI/serving, ML predictor, v2 self-serve, integration.
