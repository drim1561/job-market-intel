-- The deduped postings joined with their Claude-extracted fields. Where a posting hasn't
-- been enriched yet, the AI remote flag falls back to the rule-based one from ingest, so
-- this model is always complete (is_enriched marks which rows have AI data).

with resolved as (
    select * from {{ ref('int_jobs_resolved') }}
),

enrich as (
    select *
    from {{ source('raw_jobs', 'job_enrichment') }}
    -- one enrichment row per posting (latest), in case of any re-extraction
    qualify row_number() over (partition by posting_key order by extracted_at desc) = 1
)

select
    r.posting_key,
    r.company,
    r.title,
    r.location,
    r.url,
    r.source,
    r.salary_min,
    r.salary_max,
    r.posted_at,
    r.description,

    -- AI value wins; fall back to the rule-based remote flag, else 'unknown'
    coalesce(e.remote_type, case when r.remote then 'remote' end, 'unknown') as remote_type,
    e.seniority,
    e.role_category,
    e.min_years_experience,
    e.skills,
    (e.posting_key is not null) as is_enriched
from resolved r
left join enrich e on r.posting_key = e.posting_key
