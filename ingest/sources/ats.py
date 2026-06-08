"""ATS source: per-company public job boards (Greenhouse / Lever / Ashby).

Unlike Adzuna/USAJobs (which we query by keyword), an ATS board lists ALL of a
company's roles, so we fetch the whole board and filter to AE/DE-relevant titles.
Companies + slugs come from companies.yml. Full JD text here is the richest input for
LLM skill/salary extraction.

Endpoints:
  greenhouse: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
  lever:      https://api.lever.co/v0/postings/{slug}?mode=json
  ashby:      https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Iterator

import requests
import yaml

from ..schema import CanonicalPosting, normalize_posting

# Keep only titles in the AE/DE niche (the board lists everything).
_RELEVANT = ("analyt", "data engineer", "data analyst", "business intelligence", " bi ", "analytics engineer")


def _is_relevant(title: str) -> bool:
    t = f" {title.lower()} "
    return any(kw in t for kw in _RELEVANT)


def _load_companies(path: str | None = None) -> list[dict]:
    path = path or os.environ.get("COMPANIES_FILE", "companies.yml")
    with open(path, "r", encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("companies", [])


def fetch(companies_path: str | None = None) -> Iterator[CanonicalPosting]:
    """Yield CanonicalPosting records for every configured company board. No keys needed."""
    for entry in _load_companies(companies_path):
        ats, slug, name = entry.get("ats"), entry.get("slug"), entry.get("name", "")
        fetcher = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby}.get(ats)
        if not fetcher or not slug:
            continue
        try:
            yield from fetcher(slug, name)
        except requests.HTTPError:
            # A dead/renamed slug shouldn't kill the whole run; skip and continue.
            continue


def _greenhouse(slug: str, company: str) -> Iterator[CanonicalPosting]:
    r = requests.get(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        params={"content": "true"},
        timeout=30,
    )
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        title = j.get("title", "")
        if not _is_relevant(title):
            continue
        loc = (j.get("location") or {}).get("name", "")
        yield normalize_posting(
            {
                "source": "ats:greenhouse",
                "source_posting_id": str(j.get("id", "")),
                "company": company,
                "title": title,
                "location": loc,
                "url": j.get("absolute_url", ""),
                "description": j.get("content", ""),  # HTML
                "remote": True if "remote" in loc.lower() else None,
                "posted_at": j.get("updated_at"),
                "raw_payload": j,
            }
        )


def _lever(slug: str, company: str) -> Iterator[CanonicalPosting]:
    r = requests.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}, timeout=30)
    r.raise_for_status()
    for j in r.json():
        title = j.get("text", "")
        if not _is_relevant(title):
            continue
        cats = j.get("categories") or {}
        loc = cats.get("location", "")
        created = j.get("createdAt")
        yield normalize_posting(
            {
                "source": "ats:lever",
                "source_posting_id": str(j.get("id", "")),
                "company": company,
                "title": title,
                "location": loc,
                "url": j.get("hostedUrl", ""),
                "description": j.get("descriptionPlain") or j.get("description", ""),
                "remote": True if "remote" in str(loc).lower() else None,
                "posted_at": _epoch_ms(created),
                "raw_payload": j,
            }
        )


def _ashby(slug: str, company: str) -> Iterator[CanonicalPosting]:
    r = requests.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
        params={"includeCompensation": "true"},
        timeout=30,
    )
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        title = j.get("title", "")
        if not _is_relevant(title):
            continue
        yield normalize_posting(
            {
                "source": "ats:ashby",
                "source_posting_id": str(j.get("id", "")),
                "company": company,
                "title": title,
                "location": j.get("location", ""),
                "url": j.get("jobUrl") or j.get("applyUrl", ""),
                "description": j.get("descriptionPlain") or j.get("descriptionHtml", ""),
                "remote": j.get("isRemote"),
                "posted_at": j.get("publishedAt"),
                "raw_payload": j,
            }
        )


def _epoch_ms(ms) -> str | None:
    """Lever createdAt is epoch milliseconds; convert to ISO8601 UTC."""
    try:
        return dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None
