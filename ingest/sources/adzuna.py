"""Adzuna source: fetch AE/DE postings and map them to CanonicalPosting.

Adzuna is the richest source for *market* signal: it aggregates many boards and returns
structured salary. Docs: https://developer.adzuna.com/ (free app_id + app_key).

Endpoint:
  GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
      ?app_id=...&app_key=...&results_per_page=50&what=...&max_days_old=...
Response: {"results": [ {id, title, company:{display_name}, location:{display_name,area[]},
                        description, redirect_url, salary_min, salary_max, created,
                        contract_time}, ... ]}
"""

from __future__ import annotations

import os
from typing import Iterator

import requests

from ..schema import CanonicalPosting, normalize_posting

_BASE = "https://api.adzuna.com/v1/api/jobs"
# Search terms that cover the AE/DE niche. Tune freely; each becomes its own query.
_QUERIES = [
    "analytics engineer",
    "data engineer",
    "senior data analyst",
    "product analyst",
    "bi analyst",
]


def fetch(
    country: str = "us",
    queries: list[str] | None = None,
    max_pages: int = 3,
    max_days_old: int = 7,
) -> Iterator[CanonicalPosting]:
    """Yield CanonicalPosting records. Requires ADZUNA_APP_ID / ADZUNA_APP_KEY in env."""
    app_id = os.environ["ADZUNA_APP_ID"]
    app_key = os.environ["ADZUNA_APP_KEY"]
    queries = queries or _QUERIES

    for what in queries:
        for page in range(1, max_pages + 1):
            resp = requests.get(
                f"{_BASE}/{country}/search/{page}",
                params={
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": 50,
                    "what": what,
                    "max_days_old": max_days_old,
                    "content-type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                break  # no more pages for this query
            for raw in results:
                yield _map(raw)


def _map(raw: dict) -> CanonicalPosting:
    loc = raw.get("location") or {}
    company = (raw.get("company") or {}).get("display_name", "")
    posting: CanonicalPosting = {
        "source": "adzuna",
        "source_posting_id": str(raw.get("id", "")),
        "company": company,
        "title": raw.get("title", ""),
        "location": loc.get("display_name", ""),
        "url": raw.get("redirect_url", ""),
        "description": raw.get("description", ""),
        "remote": _is_remote(raw),
        "salary_min": raw.get("salary_min"),
        "salary_max": raw.get("salary_max"),
        "salary_currency": "USD",
        "posted_at": raw.get("created"),
        "raw_payload": raw,
    }
    return normalize_posting(posting)


def _is_remote(raw: dict) -> bool | None:
    """Adzuna has no explicit remote flag; infer from location/title text, else None."""
    text = " ".join(
        [
            raw.get("title", ""),
            ((raw.get("location") or {}).get("display_name") or ""),
        ]
    ).lower()
    if "remote" in text:
        return True
    return None
