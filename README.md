# AE/DE Job-Market Intelligence

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?logo=snowflake&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-FF694B?logo=dbt&logoColor=white)
![Redpanda](https://img.shields.io/badge/Redpanda-streaming-E04F35)
![dlt](https://img.shields.io/badge/dlt-load-1F6FEB)
![Claude API](https://img.shields.io/badge/Claude_API-applied_AI-D97757)
![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform&logoColor=white)

A streaming analytics pipeline that turns scattered Analytics-Engineer / Data-Engineer job
postings into a clean, queryable market view. It ingests from multiple sources, resolves
duplicates across boards, tracks each posting's lifecycle, extracts skills and salary from
free text, scores roles against a candidate profile, and (in progress) serves both a public
market report and a self-serve match tool.

> Portfolio + personal-use data-engineering project. The expensive pipeline runs once,
> centrally; the public app reads a cheap exported store so browsing costs nothing in
> warehouse credits.

## Highlights

- **End to end, many parts that fit together:** streaming ingest → warehouse → tested dbt
  models → applied AI → serving.
- **Real cross-source entity resolution and lifecycle tracking:** first-seen / last-seen /
  closed, with repost counting and a ghost-posting flag.
- **Applied AI on the Claude API:** skill and salary extraction from free text plus 0 to 100
  profile fit-scoring, rate-limited, concurrent, and cached.
- **Cost-aware by design:** an XS Snowflake warehouse, a Terraform credit-cap monitor,
  per-step caching, and a public app that never queries Snowflake.

## Architecture

```
sources (Adzuna / USAJobs / ATS: Greenhouse, Lever, Ashby)
  -> Redpanda topic  -> dlt  -> Snowflake RAW
  -> dbt (staging -> entity resolution -> lifecycle -> marts, tested)
  -> Claude API (extract / fit-score / digest)  +  ML ghost-job predictor
  -> Evidence.dev (public market report)  +  Streamlit (self-serve matches)

Orchestrated by Dagster | infra via Terraform | data quality via Elementary | CI via dbt Cloud
```

The public app reads a cheap exported serving store (Parquet / DuckDB), never Snowflake, so
public traffic costs nothing in warehouse credits.

## Stack

| Layer | Tools |
|---|---|
| Ingest / streaming | Adzuna, USAJobs, ATS APIs (Greenhouse / Lever / Ashby), Redpanda, dlt |
| Warehouse | Snowflake |
| Modeling | dbt (staging → intermediate → marts, tested) |
| Applied AI | Claude API (skill/salary extraction, fit-scoring, digest, NL to SQL) |
| ML | ghost-job / time-to-close predictor (scikit-learn / Snowpark) |
| Serving | Evidence.dev (public report), Streamlit (self-serve) |
| Orchestration | Dagster |
| Infra / quality / CI | Terraform, Elementary, dbt Cloud |

## Pipeline & dbt models

```
ingest/        Adzuna / USAJobs / ATS sources -> Redpanda producer -> dlt -> Snowflake RAW
dbt/models/
  staging/     stg_job_postings              # cleaned, typed postings
  intermediate/
    fct_posting_snapshots                    # incremental daily snapshots
    int_jobs_resolved                        # cross-source entity resolution
    int_job_lifecycle                        # first/last-seen, repost counting
    int_jobs_enriched                        # joins Claude skill/role enrichment
    int_job_skills                           # exploded, alias-normalized skills
  marts/
    mart_posting_lifecycle                   # per-posting lifecycle + ghost flag
    mart_market_trends                       # hiring trends over time
    mart_salary_benchmarks                   # salary bands (junk-salary filtered)
    mart_skill_demand                        # most-in-demand skills
    mart_active_jobs                         # fit-ranked live matches vs profile
ai/            extract.py (skills/seniority/remote/role)  ·  fit_score.py (0-100 fit)
infra/         Terraform: warehouse, db, RAW + ANALYTICS schemas, role, credit-cap monitor
```

## Status

Working end to end from ingest through AI fit-scoring; serving, orchestration, and the ML
predictor are the next phases.

- [x] Multi-source ingest → Redpanda → dlt → Snowflake RAW (~1,061 postings to date)
- [x] Terraform infra (XS warehouse, schemas, role, credit-cap monitor)
- [x] dbt models: staging → resolution → lifecycle → marts, with tests
- [x] Applied AI: Claude extraction + 0 to 100 profile fit-scoring (rate-limited, cached)
- [ ] Elementary data-quality monitoring
- [ ] Dagster orchestration of the run sequence
- [ ] Evidence.dev market report + Streamlit self-serve app
- [ ] ML ghost-job / time-to-close predictor
- [ ] v2 self-serve (paste resume → ranked matches) + deploy

> Note: Snowflake Cortex isn't available on the trial tier, so the AI steps run via the
> Claude API rather than in-warehouse functions.

## Setup

Requires Python 3.11+, Docker (for local Redpanda), and accounts/keys for Adzuna, USAJobs,
Snowflake, and the Anthropic API. Copy `.env.example` to `.env` and fill in.

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
docker compose up -d                              # local Redpanda
```

Two config files are the "data" you swap to retarget the system:

- `profile.example.json` → copy to `profile.json` (candidate profile used for fit-scoring)
- `companies.yml` (target companies and their ATS slugs)

### Run sequence

```powershell
.\load-env.ps1                 # env for terraform/dbt (per new terminal)
docker compose up -d           # Redpanda (when ingesting)
python -m ingest.producer      # fetch -> Redpanda
python -m ingest.dlt_pipeline  # Redpanda -> Snowflake RAW
python -m ai.extract 1000      # Claude skill/role extraction
python -m ai.fit_score 1000    # Claude 0-100 fit-scoring
cd dbt; dbt build              # build all models + tests
```

## Engineering notes

A few findings worth calling out (the kind of thing this project exists to surface):

- **Source coverage correlates with extraction quality** — Adzuna descriptions are thin, so
  fewer skills get extracted than from full ATS postings.
- **Location is part of the posting key** — the same role under different location strings
  ("Alaska" vs "Remote") can split into separate keys; a known refinement.
- **Fit ceilings from thin data** — many roles cap near fit 72 when `remote_type` is unknown
  due to sparse descriptions.
- **Skill normalization** — aliases collapsed via a seed (GCP / Google Cloud Platform,
  Spark / Apache Spark) so demand counts aren't fragmented.

## Privacy / terms

Pasted resumes in the (planned) self-serve app are processed in memory and never stored. The
public report shows aggregate market stats; self-serve matches link out to original postings
rather than republishing full job-description text. Respect each source's terms of use.
