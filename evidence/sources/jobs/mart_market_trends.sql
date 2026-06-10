select snapshot_date, active_postings, remote_postings, remote_share, hiring_companies
from analytics.mart_market_trends
order by snapshot_date
