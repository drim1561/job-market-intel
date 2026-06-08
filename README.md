# AE/DE Job-Market Intelligence

A streaming analytics pipeline that ingests Analytics-Engineer / Data-Engineer job
postings from multiple sources, resolves duplicates across boards, tracks each
posting's lifecycle, extracts skills and salary from free text, scores roles against
a candidate profile, and publishes both a personal match feed and a public market
report.

> Portfolio + personal-use data-engineering project. The expensive pipeline runs once,
> centrally; anyone can use the self-serve match tool in a browser with zero setup.

## What it does

- **Multi-source ingest** — Adzuna, USAJobs, and ATS board APIs (Greenhouse / Lever / Ashby)
  → Redpanda → Snowflake via dlt.
- **dbt modeling** — cross-source entity resolution, posting-lifecycle tracking
  (first-seen / last-seen / closed), and tested marts.
- **Applied AI** — LLM skill/salary extraction, profile fit-scoring, a daily NL digest,
  NL→SQL query, and resume→profile parsing (Claude API).
- **Classical ML** — a ghost-job / time-to-close predictor trained on the pipeline's own
  lifecycle labels.
- **Serving** — a public Evidence.dev market report + a self-serve Streamlit app
  (paste resume → ranked matches).

## Architecture

```
sources (Adzuna / USAJobs / ATS)
  -> Redpanda topic  -> dlt  -> Snowflake RAW
  -> dbt (staging -> entity resolution -> lifecycle -> marts, tested)
  -> Claude (extract / score / digest) + scikit-learn (ghost-job predictor)
  -> Evidence.dev (public market report) + Streamlit (self-serve matches)
Orchestrated by Dagster | infra via Terraform | data quality via Elementary | CI via dbt Cloud
```

The public app reads a cheap exported serving store (Parquet/DuckDB), never Snowflake,
so public traffic costs nothing in warehouse credits.

## Status

Early build. See the phased plan; phases are independently demoable. Current focus:
repo scaffold + canonical schema.

## Setup

Requires: Python 3.11+, Docker (for local Redpanda), and accounts/keys for Adzuna,
USAJobs, Snowflake, and the Anthropic API. Copy `.env.example` to `.env` and fill in.

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
docker compose up -d                              # local Redpanda
```

Configuration lives in two files (the "data" you swap to retarget the system):
- `profile.example.json` — candidate profile used for fit-scoring (copy to `profile.json`).
- `companies.yml` — target companies and their ATS slugs.

## Privacy / terms

Pasted resumes in the self-serve app are processed in memory and never stored. The public
report shows aggregate market stats; self-serve matches link out to original postings
rather than republishing full job-description text. Respect each source's terms of use.
