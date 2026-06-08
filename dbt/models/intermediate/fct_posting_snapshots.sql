-- The incremental fact: one row per observed snapshot of a listing.
-- Each ingest run appends new snapshots; this model only processes rows newer than what
-- it already has (incremental on ingested_at), so re-runs stay cheap and never reprocess
-- history. This append-only snapshot history is what the lifecycle model aggregates to
-- compute first_seen / last_seen / repost_count.

{{
    config(
        materialized="incremental",
        unique_key="snapshot_id",
        incremental_strategy="merge",
    )
}}

with stg as (
    select * from {{ ref('stg_job_postings') }}

    {% if is_incremental() %}
    -- only snapshots newer than the latest we've already loaded
    where ingested_at > (select coalesce(max(ingested_at), '1900-01-01') from {{ this }})
    {% endif %}
)

select
    md5(listing_id || '|' || to_varchar(ingested_at)) as snapshot_id,  -- stable, de-dupes exact re-loads
    posting_key,
    listing_id,
    source,
    source_posting_id,
    company,
    title,
    location,
    url,
    remote,
    salary_min,
    salary_max,
    salary_currency,
    posted_at,
    ingested_at,
    description
from stg
qualify row_number() over (partition by snapshot_id order by ingested_at) = 1
