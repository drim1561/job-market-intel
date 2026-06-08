-- One clean, typed row per raw snapshot. No per-source logic: ingest already mapped
-- every source into the canonical shape, so this is a single staging model.
--
-- posting_key mirrors ingest/schema.py::posting_key() EXACTLY (company|title|location,
-- normalized) so Python and SQL agree on what "the same role" means. listing_id =
-- source + source id identifies one physical listing (used later to count reposts).

with src as (
    select * from {{ source('raw_jobs', 'job_postings') }}
)

select
    source,
    source_posting_id,
    company,
    title,
    location,
    url,
    description,
    remote,
    -- dlt already typed these (numbers / TIMESTAMP_TZ), so cast directly rather than
    -- re-parse from text. Normalize timestamps to TIMESTAMP_NTZ for consistent math.
    salary_min::float                          as salary_min,
    salary_max::float                          as salary_max,
    salary_currency,
    posted_at::timestamp_ntz                   as posted_at,
    ingested_at::timestamp_ntz                 as ingested_at,
    company_norm,
    title_norm,
    location_norm,

    -- entity-resolution key (merges boards + reposts of the same role)
    company_norm || '|' || title_norm || '|' || location_norm as posting_key,

    -- one physical listing (a board's specific posting)
    source || ':' || source_posting_id        as listing_id,

    raw_payload
from src
where coalesce(company_norm, '') <> ''
  and coalesce(title_norm, '') <> ''
