"""Claude fit-scoring: score each relevant posting against the candidate profile.

Reuses the same rate-limited, concurrent, cached harness as ai/extract.py (imported), but
instead of extracting fields it produces a 0-100 fit score + verdict + one-line reason for
how well a posting matches profile.json. Only scores postings whose role_category is in the
target set (skips the big 'Other' federal/non-data bucket), which keeps cost down and the
ranked-matches output relevant.

Output lands in RAW.JOB_FIT, which dbt joins into mart_active_jobs (the fit-ranked list).

Usage (project root, venv active):
    python -m ai.fit_score 10        # validate on 10 first
    python -m ai.fit_score 1000      # then the rest
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Reuse the connection + rate limiter built for extraction (DRY).
from ai.extract import REQUESTS_PER_MINUTE, _connect, _RateLimiter

MODEL = "claude-haiku-4-5"
PROFILE_PATH = os.environ.get("PROFILE_PATH", "profile.json")
TARGET_ROLES = (
    "Analytics Engineer",
    "Data Engineer",
    "Data Analyst",
    "BI",
    "Data Scientist",
    "ML Engineer",
)
MAX_JD_CHARS = 3000  # fit-scoring leans on the structured fields, so less JD is needed


class Fit(BaseModel):
    fit_score: int = Field(description="0-100 overall fit of this role for the candidate")
    verdict: str = Field(description="One of: strong, possible, weak")
    reason: str = Field(
        description="One concise sentence on the score: stack overlap, title/seniority "
        "match, salary vs floor, location/remote, and any dealbreaker."
    )


def _ensure_table(cur):
    cur.execute(
        """
        create table if not exists RAW.JOB_FIT (
            posting_key string,
            fit_score   int,
            verdict     string,
            reason      string,
            scored_at   timestamp_ntz default sysdate()
        )
        """
    )


def _fetch_pending(cur, limit: int) -> list[dict]:
    placeholders = ", ".join(["%s"] * len(TARGET_ROLES))
    cur.execute(
        f"""
        select e.posting_key, e.title, e.company, e.location, e.remote_type,
               e.role_category, e.salary_min, e.salary_max, e.skills, e.description
        from ANALYTICS.INT_JOBS_ENRICHED e
        left join RAW.JOB_FIT f on f.posting_key = e.posting_key
        where f.posting_key is null
          and e.role_category in ({placeholders})
        limit {int(limit)}
        """,
        TARGET_ROLES,
    )
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _prompt(profile: dict, p: dict) -> str:
    return (
        "Score how well this job posting fits the candidate (0-100). Weigh stack overlap, "
        "title/role and seniority match, salary vs the floor, and location/remote fit. A "
        "dealbreaker should heavily lower the score.\n\n"
        "CANDIDATE PROFILE:\n"
        f"- Target titles: {profile.get('target_titles')}\n"
        f"- Core stack: {profile.get('core_stack')}\n"
        f"- Experience: {profile.get('experience_years')} yrs; seniority {profile.get('seniority')}\n"
        f"- Salary floor: ${profile.get('salary_floor_usd')}\n"
        f"- Locations / remote pref: {profile.get('locations')} / {profile.get('remote_preference')}\n"
        f"- Dealbreakers: {profile.get('dealbreakers')}\n\n"
        "POSTING:\n"
        f"- {p.get('title')} at {p.get('company')} ({p.get('location')}, remote: {p.get('remote_type')})\n"
        f"- Role: {p.get('role_category')}; skills: {p.get('skills')}\n"
        f"- Salary: {p.get('salary_min')}-{p.get('salary_max')}\n"
        f"- Description: {(p.get('description') or '')[:MAX_JD_CHARS]}"
    )


def _score_one(client, profile, posting, limiter) -> Fit:
    limiter.wait()
    resp = client.messages.parse(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": _prompt(profile, posting)}],
        output_format=Fit,
    )
    return resp.parsed_output


def _write(cur, posting_key: str, fit: Fit) -> None:
    cur.execute(
        "insert into RAW.JOB_FIT (posting_key, fit_score, verdict, reason) "
        "values (%s, %s, %s, %s)",
        (posting_key, fit.fit_score, fit.verdict, fit.reason),
    )


def run(limit: int = 25, workers: int = 4) -> None:
    load_dotenv()
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)
    client = anthropic.Anthropic(max_retries=5)
    limiter = _RateLimiter(REQUESTS_PER_MINUTE)
    conn = _connect()
    cur = conn.cursor()
    _ensure_table(cur)
    pending = _fetch_pending(cur, limit)
    print(f"{len(pending)} postings to score (model={MODEL}, ~{REQUESTS_PER_MINUTE}/min)")

    done, failed = 0, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_score_one, client, profile, p, limiter): p for p in pending}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                _write(cur, p["posting_key"], fut.result())
                done += 1
                if done % 25 == 0:
                    print(f"  {done}/{len(pending)}")
            except Exception as err:  # noqa: BLE001
                failed += 1
                print(f"  error on {p['posting_key']}: {err.__class__.__name__}: {err}")
    conn.commit()
    conn.close()
    print(f"scored {done} postings ({failed} failed) -> RAW.JOB_FIT")


if __name__ == "__main__":
    run(limit=int(sys.argv[1]) if len(sys.argv) > 1 else 25)
