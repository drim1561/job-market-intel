-- The fit-ranked matches list: currently-active, target-role postings scored against the
-- profile, best fit first. This is the "front door" output — what you (or a self-serve
-- user) open to see which roles are worth your time, with the lifecycle/ghost context.

with enriched as (
    select * from {{ ref('int_jobs_enriched') }}
),

life as (
    select posting_key, is_active, first_seen, repost_count, days_span
    from {{ ref('int_job_lifecycle') }}
),

fit as (
    select *
    from {{ source('raw_jobs', 'job_fit') }}
    qualify row_number() over (partition by posting_key order by scored_at desc) = 1
)

select
    e.posting_key,
    e.company,
    e.title,
    e.role_category,
    e.location,
    e.remote_type,
    e.seniority,
    e.salary_min,
    e.salary_max,
    e.skills,
    e.url,
    f.fit_score,
    f.verdict,
    f.reason,
    l.is_active,
    l.first_seen,
    l.repost_count,
    l.days_span
from enriched e
join life l on l.posting_key = e.posting_key
join fit f on f.posting_key = e.posting_key
where l.is_active
order by f.fit_score desc
