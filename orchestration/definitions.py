"""Dagster definitions for the job-market-intel pipeline.

Pipeline flow (assets in materialization order):

  1. ingest_raw         – all source producers → Redpanda → dlt → RAW.JOB_POSTINGS
  2. dbt_pre_ai         – staging → fct_snapshots → int_jobs_resolved → int_job_lifecycle
                          + mart_salary_benchmarks, mart_market_trends, mart_posting_lifecycle
                          (all models that only need RAW.JOB_POSTINGS)
  3. ai_extraction      – Claude Haiku reads INT_JOBS_RESOLVED, writes RAW.JOB_ENRICHMENT
  4. dbt_post_extract   – int_jobs_enriched → int_job_skills → mart_skill_demand
                          (models that join against the JOB_ENRICHMENT source)
  5. ai_fit_scoring     – Claude Haiku reads INT_JOBS_ENRICHED, writes RAW.JOB_FIT
  6. dbt_final          – mart_active_jobs (fit-ranked open matches, joins JOB_FIT)

Python assets produce the three Snowflake source tables that dbt reads; Dagster wires
them up automatically because the AssetKey values match what DagsterDbtTranslator
generates for the dbt sources (source_name + table_name → ["raw_jobs", "job_postings"]).

Usage:
    .\\load-env.ps1     # load SNOWFLAKE_* + ANTHROPIC_API_KEY into env
    dagster dev         # starts the Dagster UI at localhost:3000
"""

import sys
from pathlib import Path

from dagster import (\
    AssetKey,
    AssetSelection,
    Definitions,
    RetryPolicy,
    ScheduleDefinition,
    asset,
    define_asset_job,
)
from dagster import AssetExecutionContext  # used only by @dbt_assets functions
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

# ── paths + sys.path ──────────────────────────────────────────────────────────
# Ensure the project root is on sys.path so `ingest.*` and `ai.*` are importable
# when Dagster executes asset functions.
_HERE = Path(__file__).parent
PROJECT_ROOT = _HERE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DBT_DIR = PROJECT_ROOT / "dbt"

# ── dbt project + resource ─────────────────────────────────────────────────────
# profiles_dir tells dagster-dbt (and dbt) where to find profiles.yml.
# prepare_if_dev() re-runs `dbt parse` when launched via `dagster dev` so the
# manifest stays in sync with any model changes before the UI loads.
dbt_project = DbtProject(
    project_dir=DBT_DIR,
    profiles_dir=DBT_DIR,
)
dbt_project.prepare_if_dev()

dbt_resource = DbtCliResource(
    project_dir=dbt_project,
    profiles_dir=str(DBT_DIR),
)

# ── 1. Ingest ──────────────────────────────────────────────────────────────────
# AssetKey must match dagster-dbt's key for source('raw_jobs', 'job_postings'),
# which is AssetKey(["raw_jobs", "job_postings"]).

@asset(
    key=AssetKey(["raw_jobs", "job_postings"]),
    description=(
        "Fetch job postings from all sources (Adzuna, USAJobs, ATS) → Redpanda, "
        "then drain Redpanda → Snowflake RAW.JOB_POSTINGS via dlt."
    ),
    retry_policy=RetryPolicy(max_retries=2, delay=30),
)
def ingest_raw(context) -> None:
    from dotenv import load_dotenv

    load_dotenv()

    from ingest.producer import get_producer, publish
    from ingest.sources import adzuna, ats, usajobs

    shared_producer = get_producer()
    total = 0
    for name, fetch in [
        ("adzuna", adzuna.fetch),
        ("usajobs", usajobs.fetch),
        ("ats", ats.fetch),
    ]:
        try:
            n = publish(fetch(), producer=shared_producer)
            total += n
            context.log.info(f"{name}: published {n}")
        except KeyError as missing:
            context.log.warning(f"{name}: skipped (missing env var {missing})")
        except Exception as err:  # noqa: BLE001 – one bad source shouldn't stop the rest
            context.log.warning(f"{name}: error ({err.__class__.__name__}: {err})")
    context.log.info(f"total: {total} postings → Redpanda")

    from ingest.dlt_pipeline import run as dlt_run

    dlt_run()
    context.log.info("dlt complete → RAW.JOB_POSTINGS")


# ── 2. dbt pre-AI ──────────────────────────────────────────────────────────────
# All models whose only upstream source is RAW.JOB_POSTINGS.  Building these
# first gives ai_extraction a fresh INT_JOBS_RESOLVED to read.

_PRE_AI = (
    "stg_job_postings fct_posting_snapshots int_jobs_resolved int_job_lifecycle "
    "mart_salary_benchmarks mart_market_trends mart_posting_lifecycle"
)


@dbt_assets(manifest=dbt_project.manifest_path, select=_PRE_AI, name="dbt_pre_ai")
def dbt_pre_ai(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build", "--select", _PRE_AI], context=context).stream()


# ── 3. AI extraction ───────────────────────────────────────────────────────────
# Reads INT_JOBS_RESOLVED (from dbt_pre_ai), writes RAW.JOB_ENRICHMENT.
# The AssetKey matches dagster-dbt's key for source('raw_jobs', 'job_enrichment').

@asset(
    key=AssetKey(["raw_jobs", "job_enrichment"]),
    deps=[AssetKey(["int_jobs_resolved"])],
    description=(
        "Claude Haiku extracts skills, seniority, remote_type, and role_category "
        "from JD text → RAW.JOB_ENRICHMENT.  Only processes new postings (cached by key)."
    ),
    retry_policy=RetryPolicy(max_retries=2, delay=60),
)
def ai_extraction(context) -> None:
    from ai.extract import run

    run(limit=1000, workers=4)


# ── 4. dbt post-extract ────────────────────────────────────────────────────────
# Models that join against RAW.JOB_ENRICHMENT (source raw_jobs.job_enrichment).
# Dagster knows to wait for ai_extraction because int_jobs_enriched declares
# that source as an upstream dependency in the dbt manifest.

_POST_EXTRACT = "int_jobs_enriched int_job_skills mart_skill_demand"


@dbt_assets(
    manifest=dbt_project.manifest_path, select=_POST_EXTRACT, name="dbt_post_extract"
)
def dbt_post_extract(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build", "--select", _POST_EXTRACT], context=context).stream()


# ── 5. AI fit scoring ──────────────────────────────────────────────────────────
# Reads INT_JOBS_ENRICHED (from dbt_post_extract), writes RAW.JOB_FIT.

@asset(
    key=AssetKey(["raw_jobs", "job_fit"]),
    deps=[AssetKey(["int_jobs_enriched"])],
    description=(
        "Claude Haiku scores each enriched posting against profile.json (0-100 fit). "
        "Only scores postings in target role categories → RAW.JOB_FIT."
    ),
    retry_policy=RetryPolicy(max_retries=2, delay=60),
)
def ai_fit_scoring(context) -> None:
    from ai.fit_score import run

    run(limit=1000, workers=4)


# ── 6. dbt final ───────────────────────────────────────────────────────────────
# mart_active_jobs joins INT_JOBS_ENRICHED against RAW.JOB_FIT (source raw_jobs.job_fit).

@dbt_assets(
    manifest=dbt_project.manifest_path, select="mart_active_jobs", name="dbt_final"
)
def dbt_final(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build", "--select", "mart_active_jobs"], context=context).stream()


# ── job + schedule ─────────────────────────────────────────────────────────────
# One job that materializes every asset; run every 4 hours (job postings change
# on the order of hours, not minutes – the cadence reflects the data's freshness
# rate while keeping Snowflake credits low).

pipeline_job = define_asset_job(
    name="job_market_pipeline",
    selection=AssetSelection.all(),
)

every_four_hours = ScheduleDefinition(
    name="every_four_hours",
    cron_schedule="0 */4 * * *",
    job=pipeline_job,
    execution_timezone="America/New_York",
)

# ── Definitions ────────────────────────────────────────────────────────────────

defs = Definitions(
    assets=[ingest_raw, dbt_pre_ai, ai_extraction, dbt_post_extract, ai_fit_scoring, dbt_final],
    resources={"dbt": dbt_resource},
    jobs=[pipeline_job],
    schedules=[every_four_hours],
)
