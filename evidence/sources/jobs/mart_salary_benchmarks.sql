select role_category, remote_bucket, n_postings, n_with_salary,
    avg_salary, median_salary, min_salary, max_salary
from analytics.mart_salary_benchmarks
order by role_category, remote_bucket
