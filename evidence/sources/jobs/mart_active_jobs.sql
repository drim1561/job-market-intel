select
    posting_key, company, title, role_category, location,
    remote_type, seniority, salary_min, salary_max,
    skills, url, fit_score, verdict, reason,
    is_active, first_seen, repost_count, days_span
from analytics.mart_active_jobs
order by fit_score desc
