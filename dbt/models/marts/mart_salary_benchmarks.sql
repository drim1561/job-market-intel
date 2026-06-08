-- Salary distribution by role category and remote status, over the current deduped
-- postings. Salary comes structured from Adzuna/USAJobs; ATS rows usually lack it
-- (the AI/Cortex extraction in Phase 4 will fill more of those in from JD text).

with jobs as (
    select
        *,
        case
            when title ilike '%analytics engineer%'                                 then 'Analytics Engineer'
            when title ilike '%data engineer%'                                      then 'Data Engineer'
            when title ilike '%data analyst%'                                       then 'Data Analyst'
            when title ilike '%business intelligence%' or title ilike '% bi %'      then 'BI'
            else 'Other'
        end                                                                         as role_category,
        -- guard against junk values (Adzuna sometimes returns 1 / tiny placeholders):
        -- only count salaries in a plausible annual range.
        case
            when coalesce((salary_min + salary_max) / 2, salary_min, salary_max) between 20000 and 1000000
            then coalesce((salary_min + salary_max) / 2, salary_min, salary_max)
        end                                                                         as salary_mid
    from {{ ref('int_jobs_resolved') }}
)

select
    role_category,
    case when remote = true then 'Remote' else 'Onsite/Hybrid/Unknown' end as remote_bucket,
    count(*)                                  as n_postings,
    count(salary_mid)                         as n_with_salary,
    round(avg(salary_mid))                    as avg_salary,
    round(median(salary_mid))                 as median_salary,
    round(min(salary_mid))                    as min_salary,
    round(max(salary_mid))                    as max_salary
from jobs
group by 1, 2
order by 1, 2
