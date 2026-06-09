"""Claude extraction: read JD text from Snowflake, pull structured fields, write back.

Snowflake Cortex (in-warehouse AI) isn't available on trial accounts, so extraction runs
through the Claude API. This is a high-volume, well-structured task, so it uses Haiku (the
cost-efficient model) with structured outputs, and only processes postings that haven't
been enriched yet (cache by posting_key) so re-runs are cheap.

Output lands in RAW.JOB_ENRICHMENT, which dbt reads to build the skills + enriched marts.

Usage (from project root, venv active, .env loaded by the Python code itself):
    python -m ai.extract 10      # extract 10 postings (validate first)
    python -m ai.extract 500     # then scale up
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import anthropic
import snowflake.connector
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Haiku is the deliberate cost choice for bulk, structured extraction. Bump to
# claude-sonnet-4-6 or claude-opus-4-8 if you want higher-quality skill parsing.
MODEL = "claude-haiku-4-5"
MAX_JD_CHARS = 8000  # cap JD length to bound token cost
REQUESTS_PER_MINUTE = 45  # stay under the tier-1 limit of 50/min (raise as your tier grows)


class _RateLimiter:
    """Paces calls to at most `per_minute` starts/minute (thread-safe)."""

    def __init__(self, per_minute: int):
        self._interval = 60.0 / per_minute
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:  # hold the lock across the sleep so starts are serialized
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self._interval


class Extraction(BaseModel):
    """The structured fields we pull from each job description."""

    skills: list[str] = Field(
        description="Specific tools/technologies named in the posting, as short canonical "
        "names (e.g. 'SQL', 'dbt', 'Snowflake', 'Python', 'Airflow', 'Looker'). "
        "Only concrete tools/skills, not soft skills. Empty list if none."
    )
    seniority: str = Field(description="One of: junior, mid, senior, staff, lead, manager, unknown")
    remote_type: str = Field(description="One of: remote, hybrid, onsite, unknown")
    role_category: str = Field(
        description="One of: Analytics Engineer, Data Engineer, Data Analyst, BI, "
        "Data Scientist, ML Engineer, Other"
    )
    min_years_experience: Optional[int] = Field(
        description="Minimum years of experience required, or null if not stated"
    )


def _connect():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="RAW",
    )


def _ensure_table(cur):
    cur.execute(
        """
        create table if not exists RAW.JOB_ENRICHMENT (
            posting_key          string,
            skills               variant,
            seniority            string,
            remote_type          string,
            role_category        string,
            min_years_experience int,
            extracted_at         timestamp_ntz default sysdate()
        )
        """
    )


def _fetch_pending(cur, limit: int) -> list[dict]:
    """Resolved postings with a description that haven't been enriched yet."""
    cur.execute(
        f"""
        select r.posting_key, r.title, r.company, r.location, r.description
        from ANALYTICS.INT_JOBS_RESOLVED r
        left join RAW.JOB_ENRICHMENT e on e.posting_key = r.posting_key
        where e.posting_key is null
          and r.description is not null
          and length(r.description) > 0
        limit {int(limit)}
        """
    )
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _extract_one(client: anthropic.Anthropic, posting: dict, limiter: _RateLimiter) -> Extraction:
    limiter.wait()  # respect the API rate limit before firing
    jd = (posting.get("description") or "")[:MAX_JD_CHARS]
    content = (
        "Extract structured fields from this job posting.\n\n"
        f"Title: {posting.get('title')}\n"
        f"Company: {posting.get('company')}\n"
        f"Location: {posting.get('location')}\n\n"
        f"Job description:\n{jd}"
    )
    resp = client.messages.parse(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
        output_format=Extraction,
    )
    return resp.parsed_output


def _write(cur, posting_key: str, ext: Extraction) -> None:
    cur.execute(
        """
        insert into RAW.JOB_ENRICHMENT
            (posting_key, skills, seniority, remote_type, role_category, min_years_experience)
        select %s, parse_json(%s), %s, %s, %s, %s
        """,
        (
            posting_key,
            json.dumps(ext.skills),
            ext.seniority,
            ext.remote_type,
            ext.role_category,
            ext.min_years_experience,
        ),
    )


def run(limit: int = 25, workers: int = 4) -> None:
    load_dotenv()
    # max_retries lets the SDK back off + retry the occasional 429 automatically.
    client = anthropic.Anthropic(max_retries=2)  # thread-safe to share across workers
    limiter = _RateLimiter(REQUESTS_PER_MINUTE)
    conn = _connect()
    cur = conn.cursor()
    _ensure_table(cur)
    pending = _fetch_pending(cur, limit)
    print(f"{len(pending)} postings to extract (model={MODEL}, ~{REQUESTS_PER_MINUTE}/min)")

    # Parallelize the slow part (the API calls); keep DB writes on the main thread (the
    # cursor isn't thread-safe). as_completed yields results as each call returns.
    done, failed = 0, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_extract_one, client, p, limiter): p for p in pending}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                _write(cur, p["posting_key"], fut.result())
                done += 1
                if done % 25 == 0:
                    print(f"  {done}/{len(pending)}")
            except Exception as err:  # noqa: BLE001 - one bad posting shouldn't stop the batch
                failed += 1
                print(f"  error on {p['posting_key']}: {err.__class__.__name__}: {err}")
    conn.commit()
    conn.close()
    print(f"extracted {done} postings ({failed} failed) -> RAW.JOB_ENRICHMENT")


if __name__ == "__main__":
    run(limit=int(sys.argv[1]) if len(sys.argv) > 1 else 25)
