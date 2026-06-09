---
title: Remote Ratio
---

# Remote Ratio & Market Volume

How the remote share and total posting volume change across pipeline runs.
Each row represents one ingest cycle.

```sql trends
select
    snapshot_date,
    active_postings,
    remote_postings,
    round(remote_share * 100, 1)  as remote_pct,
    hiring_companies
from analytics.mart_market_trends
order by snapshot_date
```

## Remote Share Over Time

<LineChart
  data={trends}
  x="snapshot_date"
  y="remote_pct"
  title="Remote Posting Share (%)"
/>

## Active Postings Over Time

<LineChart
  data={trends}
  x="snapshot_date"
  y="active_postings"
  title="Active Postings"
/>

## Hiring Companies Over Time

<LineChart
  data={trends}
  x="snapshot_date"
  y="hiring_companies"
  title="Distinct Hiring Companies"
/>

## Raw Data

<DataTable data={trends} />
