-- Skill demand across the current AE/DE market: how many postings (and companies) mention
-- each skill. One row per skill now; add a date grain later for a demand trend over time.

with skills as (
    select * from {{ ref('int_job_skills') }}
),

enriched as (
    select posting_key, company, role_category from {{ ref('int_jobs_enriched') }}
),

joined as (
    select
        s.skill,
        s.posting_key,
        e.company,
        e.role_category
    from skills s
    join enriched e using (posting_key)
)

select
    skill,
    count(distinct posting_key)                                          as postings,
    count(distinct company)                                              as companies,
    count(distinct case when role_category = 'Analytics Engineer'
                        then posting_key end)                            as ae_postings,
    count(distinct case when role_category = 'Data Engineer'
                        then posting_key end)                            as de_postings
from joined
group by 1
order by postings desc
