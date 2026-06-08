-- The repost-history layer. For each logical role (posting_key), aggregate every
-- snapshot we've ever seen into a lifecycle:
--   first_seen / last_seen  -> when the role entered and was last observed
--   n_listings              -> distinct physical listings (boards/reposts) under the key
--   repost_count            -> n_listings - 1 (0 = never reposted)
--   days_span               -> last_seen - first_seen (the "how long has this lingered" signal)
--   is_active               -> seen in (roughly) the latest run
--
-- These two signals (repost_count, days_span) are the raw material for the ghost-job
-- flag, which the mart layer applies thresholds to.

with snaps as (
    select * from {{ ref('fct_posting_snapshots') }}
),

latest_run as (
    select max(ingested_at) as latest_run_at from snaps
),

agg as (
    select
        posting_key,
        min(ingested_at)                                   as first_seen,
        max(ingested_at)                                   as last_seen,
        count(distinct listing_id)                         as n_listings,
        count(distinct listing_id) - 1                     as repost_count,
        datediff('day', min(ingested_at), max(ingested_at)) as days_span,
        count(*)                                           as n_snapshots
    from snaps
    group by 1
)

select
    a.posting_key,
    a.first_seen,
    a.last_seen,
    a.n_listings,
    a.repost_count,
    a.days_span,
    a.n_snapshots,
    -- active if observed within ~36h of the most recent ingest run (covers the
    -- every-few-hours cadence with margin); once a role stops appearing it goes inactive.
    (a.last_seen >= dateadd('hour', -36, lr.latest_run_at))           as is_active,
    datediff('day', a.first_seen, sysdate())                          as days_since_first_seen
from agg a
cross join latest_run lr
