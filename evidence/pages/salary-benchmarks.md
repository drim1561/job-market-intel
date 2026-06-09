---
title: Salary Benchmarks
---

# Salary Benchmarks

Salary ranges across AE/DE roles. Only postings with explicit salary data are included
(Adzuna and USAJobs often include structured salary; thin ATS descriptions usually lack it).

```sql salary
select
    role_category,
    remote_bucket,
    n_postings,
    n_with_salary,
    avg_salary,
    median_salary,
    min_salary,
    max_salary,
    round(100.0 * n_with_salary / nullif(n_postings, 0), 0) as salary_coverage_pct
from analytics.mart_salary_benchmarks
order by role_category, remote_bucket
```

```sql role_summary
select
    role_category,
    sum(n_postings)               as total_postings,
    sum(n_with_salary)            as postings_with_salary,
    round(avg(median_salary), 0)  as blended_median
from analytics.mart_salary_benchmarks
where n_with_salary > 0
group by role_category
order by blended_median desc nulls last
```

## Median Salary by Role

<BarChart
  data={role_summary}
  x="role_category"
  y="blended_median"
  title="Blended Median Salary by Role"
  swapXY=true
/>

## Detail: Role × Remote

<DataTable data={salary} />

> **Note:** `salary_coverage_pct` shows what share of postings in that bucket had salary data.
> Low coverage (common for ATS roles) means the averages reflect a biased sample — typically
> larger companies that disclose salaries.
