select
    posting_key, company, title, location, remote,
    salary_min, salary_max, url, source,
    first_seen, last_seen, is_active, repost_count,
    days_span, days_since_first_seen, ghost_suspected, ghost_reason
from analytics.mart_posting_lifecycle
