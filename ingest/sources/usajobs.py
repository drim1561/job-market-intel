"""USAJobs source: federal postings (DC-relevant) mapped to CanonicalPosting.

USAJobs Search API. Docs: https://developer.usajobs.gov/ (free key).
Auth headers: Host: data.usajobs.gov, User-Agent: <your email>, Authorization-Key: <key>.

Endpoint:
  GET https://data.usajobs.gov/api/search?Keyword=...&ResultsPerPage=50&Page=N
Response: {"SearchResult": {"SearchResultItems": [ {"MatchedObjectId",
            "MatchedObjectDescriptor": {PositionTitle, OrganizationName,
            PositionLocationDisplay, PositionURI, UserArea:{Details:{JobSummary}},
            PositionRemuneration:[{MinimumRange,MaximumRange,RateIntervalCode}],
            PublicationStartDate, ...}} ]}}
"""

from __future__ import annotations

import os
from typing import Iterator

import requests

from ..schema import CanonicalPosting, normalize_posting

_BASE = "https://data.usajobs.gov/api/search"
_QUERIES = ["analytics engineer", "data engineer", "data analyst", "business intelligence"]


def fetch(queries: list[str] | None = None, max_pages: int = 2) -> Iterator[CanonicalPosting]:
    """Yield CanonicalPosting records. Requires USAJOBS_API_KEY / USAJOBS_USER_AGENT."""
    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": os.environ["USAJOBS_USER_AGENT"],  # USAJobs requires a contact email
        "Authorization-Key": os.environ["USAJOBS_API_KEY"],
    }
    queries = queries or _QUERIES

    for keyword in queries:
        for page in range(1, max_pages + 1):
            resp = requests.get(
                _BASE,
                headers=headers,
                params={"Keyword": keyword, "ResultsPerPage": 50, "Page": page},
                timeout=30,
            )
            resp.raise_for_status()
            items = resp.json().get("SearchResult", {}).get("SearchResultItems", [])
            if not items:
                break
            for item in items:
                yield _map(item)


def _map(item: dict) -> CanonicalPosting:
    d = item.get("MatchedObjectDescriptor", {}) or {}
    pay = (d.get("PositionRemuneration") or [{}])[0]
    location = d.get("PositionLocationDisplay", "")
    posting: CanonicalPosting = {
        "source": "usajobs",
        "source_posting_id": str(item.get("MatchedObjectId", "")),
        "company": d.get("OrganizationName", ""),
        "title": d.get("PositionTitle", ""),
        "location": location,
        "url": d.get("PositionURI", ""),
        "description": (((d.get("UserArea") or {}).get("Details") or {}).get("JobSummary", "")),
        "remote": _is_remote(d, location),
        "salary_min": _num(pay.get("MinimumRange")),
        "salary_max": _num(pay.get("MaximumRange")),
        "salary_currency": "USD",
        "posted_at": d.get("PublicationStartDate"),
        "raw_payload": item,
    }
    return normalize_posting(posting)


def _num(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _is_remote(d: dict, location: str) -> bool | None:
    if str(d.get("PositionLocation", "")).lower().find("remote") >= 0 or "remote" in location.lower():
        return True
    return None
