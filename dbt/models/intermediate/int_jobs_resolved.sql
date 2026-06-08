-- The clean list: ONE row per logical role (posting_key), carrying its most-recent
-- known attributes. We pick the latest snapshot per key so company/title/salary/url
-- reflect the freshest listing. This is the deduped backbone the marts build on; the
-- lifecycle history (first_seen, reposts, etc.) is joined in from int_job_lifecycle.

select
    posting_key,
    company,
    title,
    location,
    url,
    source,            -- the source of the most recent listing for this role
    remote,
    salary_min,
    salary_max,
    salary_currency,
    posted_at,
    ingested_at        as last_snapshot_at,
    description
from {{ ref('fct_posting_snapshots') }}
qualify row_number() over (partition by posting_key order by ingested_at desc) = 1
