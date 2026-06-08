-- Market volume + composition per ingest day. One row per day now; a trend line as the
-- pipeline runs daily. Built straight off the snapshot history.

with snaps as (
    select * from {{ ref('fct_posting_snapshots') }}
),

by_day as (
    select
        date_trunc('day', ingested_at)                                          as snapshot_date,
        count(distinct posting_key)                                             as active_postings,
        count(distinct case when remote = true then posting_key end)           as remote_postings,
        count(distinct company)                                                 as hiring_companies,
        count(distinct source)                                                  as sources
    from snaps
    group by 1
)

select
    snapshot_date,
    active_postings,
    remote_postings,
    round(remote_postings / nullif(active_postings, 0), 3) as remote_share,
    hiring_companies,
    sources
from by_day
order by snapshot_date
