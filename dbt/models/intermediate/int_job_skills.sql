-- One row per (posting_key, skill), flattened from the extracted skills array and
-- canonicalized via the skill_aliases seed (so "Google Cloud Platform" and "GCP" count
-- as one skill). DISTINCT collapses cases where a JD listed two aliases of the same skill.

with enrich as (
    select *
    from {{ source('raw_jobs', 'job_enrichment') }}
    qualify row_number() over (partition by posting_key order by extracted_at desc) = 1
),

exploded as (
    select
        e.posting_key,
        trim(f.value::string) as skill_raw
    from enrich e,
         lateral flatten(input => e.skills) f
    where trim(f.value::string) <> ''
),

canonicalized as (
    select
        x.posting_key,
        coalesce(a.canonical, x.skill_raw) as skill
    from exploded x
    left join {{ ref('skill_aliases') }} a
        on lower(x.skill_raw) = lower(a.alias)
)

select distinct posting_key, skill
from canonicalized
