---
title: Ghost Jobs
---

# Ghost Job Detection

A "ghost job" is a posting that appears active but shows no signs of actually being filled.
This view applies a first-pass heuristic rule — Phase 8 will replace it with a Snowpark ML score.

**Ghost heuristic:**
- Reposted **2 or more times**, OR
- Still active but open for **60+ days**

```sql ghost_summary
select
    count(*)                                                                          as total_active,
    sum(case when ghost_suspected then 1 else 0 end)                                  as ghost_count,
    round(100.0 * sum(case when ghost_suspected then 1 else 0 end) / count(*), 1)     as ghost_pct,
    round(avg(repost_count), 1)                                                       as avg_reposts,
    round(avg(days_span), 0)                                                          as avg_days_open
from mart_posting_lifecycle
where is_active
```

<BigValue data={ghost_summary} value="total_active"  title="Active Postings" />
<BigValue data={ghost_summary} value="ghost_count"   title="Suspected Ghost Jobs" />
<BigValue data={ghost_summary} value="ghost_pct"     title="Ghost Rate (%)" />
<BigValue data={ghost_summary} value="avg_days_open" title="Avg Days Open" />

---

## Ghost Reason Breakdown

```sql ghost_reasons
select
    case
        when ghost_reason like 'reposted%' then 'Reposted 2+ times'
        when ghost_reason like 'open%'     then 'Open 60+ days'
        else 'Other'
    end                     as reason,
    count(*)                as jobs
from mart_posting_lifecycle
where ghost_suspected = true
group by 1
order by jobs desc
```

<BarChart data={ghost_reasons} x="reason" y="jobs" title="Ghost Job Reasons" />

---

## Suspected Ghost Jobs

```sql ghost_jobs
select
    company,
    title,
    location,
    first_seen,
    repost_count,
    days_span,
    ghost_reason,
    url
from mart_posting_lifecycle
where ghost_suspected = true
  and is_active = true
order by repost_count desc, days_span desc
limit 100
```

<DataTable data={ghost_jobs} search=true link="url" />
