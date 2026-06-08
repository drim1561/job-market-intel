-- THE clean list you asked for: one row per logical role, with its full repost history
-- and a first-pass ghost-job flag. This is the distinctive output aggregators don't show.
--
-- Ghost heuristic (refined later by the ML model in Phase 8):
--   - reposted 2+ times, OR
--   - still active but has lingered 60+ days
-- Both are crude-but-defensible signals of a role that isn't really being filled.

with resolved as (
    select * from {{ ref('int_jobs_resolved') }}
),

life as (
    select * from {{ ref('int_job_lifecycle') }}
)

select
    r.posting_key,
    r.company,
    r.title,
    r.location,
    r.remote,
    r.salary_min,
    r.salary_max,
    r.url,
    r.source,
    l.first_seen,
    l.last_seen,
    l.is_active,
    l.repost_count,
    l.days_span,
    l.days_since_first_seen,

    -- first-pass ghost flag + a simple reason, replaced by the ML score in Phase 8
    (l.repost_count >= 2 or (l.is_active and l.days_span >= 60)) as ghost_suspected,
    case
        when l.repost_count >= 2 then 'reposted ' || l.repost_count || ' times'
        when l.is_active and l.days_span >= 60 then 'open ' || l.days_span || ' days'
        else null
    end as ghost_reason
from resolved r
join life l using (posting_key)
