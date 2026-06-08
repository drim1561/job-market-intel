"""Canonical posting schema + normalization helpers.

Every source (Adzuna, USAJobs, ATS) maps its raw payload into ONE shape: the
``CanonicalPosting``. Downstream (dlt -> Snowflake RAW -> dbt) only ever sees this
shape, so adding a new source later means writing one mapper, not touching the
pipeline. This module is the contract.

The raw VARIANT payload is still preserved end-to-end (``raw_payload``) so nothing is
lost if we later want a field we didn't map.
"""

from __future__ import annotations

import re
from typing import Optional, TypedDict


class CanonicalPosting(TypedDict, total=False):
    # --- identity / provenance ---
    source: str                 # "adzuna" | "usajobs" | "ats:greenhouse" | ...
    source_posting_id: str      # the id WITHIN that source (not unique across sources)
    company: str
    title: str
    location: str               # human string as posted, e.g. "Remote - US" / "Washington, DC"
    url: str                    # link back to the original posting (we link out, never republish full JD)

    # --- content ---
    description: str            # full JD text (used for extraction; not republished publicly)
    remote: Optional[bool]      # True/False if the source states it, else None
    salary_min: Optional[float]
    salary_max: Optional[float]
    salary_currency: Optional[str]

    # --- timestamps ---
    posted_at: Optional[str]    # ISO8601 if the source provides it
    ingested_at: str            # set by the producer at publish time (ISO8601, UTC)

    # --- normalized helpers (filled by normalize_posting) ---
    company_norm: str
    title_norm: str
    location_norm: str

    # --- escape hatch ---
    raw_payload: dict           # the original source record, untouched


# Tokens we strip from titles so "Sr. Analytics Engineer II (Remote)" and
# "Senior Analytics Engineer" collapse toward the same normalized form.
_TITLE_NOISE = re.compile(
    r"\b(sr|snr|senior|jr|junior|staff|lead|principal|i{1,3}|iv|v|"
    r"remote|hybrid|onsite|contract|full[- ]?time|part[- ]?time)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace to single hyphens."""
    return _NON_ALNUM.sub("-", text.strip().lower()).strip("-")


def normalize_company(company: str) -> str:
    """Drop common suffixes so 'Acme, Inc.' and 'Acme' match."""
    c = company.strip().lower()
    c = re.sub(r"[,.]", " ", c)
    c = re.sub(r"\b(inc|llc|ltd|corp|co|the|company)\b", " ", c)
    return _slug(c)


def normalize_title(title: str) -> str:
    """Strip seniority/modifier noise, keep the role core. Tune _TITLE_NOISE as needed."""
    t = _TITLE_NOISE.sub(" ", title.lower())
    return _slug(t)


def normalize_location(location: str) -> str:
    """Coarse location bucket. 'Remote - US' / 'remote' -> 'remote'; else slug the string."""
    loc = location.strip().lower()
    if "remote" in loc:
        return "remote"
    return _slug(loc)


def normalize_posting(p: CanonicalPosting) -> CanonicalPosting:
    """Populate the *_norm fields from the raw company/title/location."""
    p["company_norm"] = normalize_company(p.get("company", ""))
    p["title_norm"] = normalize_title(p.get("title", ""))
    p["location_norm"] = normalize_location(p.get("location", ""))
    return p


# ---------------------------------------------------------------------------
# Entity-resolution key.
#
# Decision: MERGE reposts into one logical posting so the clean list has a single row
# per role. We intentionally exclude posted_at AND source_posting_id, so every board
# and every repost of the same role collapse to the same key. The *number* of reposts
# is NOT encoded here -- it is derived in the lifecycle layer (dbt int_job_lifecycle)
# from the distinct underlying listings and any disappear/reappear gaps across polls.
#
#   key merges roles  ->  one clean row per logical posting
#   lifecycle counts  ->  first_seen, last_seen, days_open, repost_count, is_active
#
# The dbt int_jobs_resolved model mirrors this exact concatenation in SQL.
# ---------------------------------------------------------------------------
def posting_key(p: CanonicalPosting) -> str:
    """Deterministic key identifying one logical posting across sources and reposts."""
    return "|".join(
        [
            p.get("company_norm", ""),
            p.get("title_norm", ""),
            p.get("location_norm", ""),
        ]
    )
