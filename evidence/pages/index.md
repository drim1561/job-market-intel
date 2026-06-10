---
title: Market Overview
---

# AE/DE Job Market — Live Overview

```sql summary
select
    count(*)                                                                   as active_postings,
    count(distinct company)                                                    as hiring_companies,
    round(avg(fit_score), 1)                                                   as avg_fit_score,
    round(100.0 * sum(case when lower(remote_type) = 'remote' then 1 else 0 end)
          / nullif(count(*), 0), 1)                                            as remote_pct
from mart_active_jobs
```

<BigValue data={summary} value="active_postings"   title="Active Postings" />
<BigValue data={summary} value="hiring_companies"  title="Hiring Companies" />
<BigValue data={summary} value="avg_fit_score"     title="Avg Fit Score" />
<BigValue data={summary} value="remote_pct"        title="% Remote" fmt='0.0"%"' />

---

## Top Skills in Demand

```sql top_skills
select skill, postings, ae_postings, de_postings
from mart_skill_demand
order by postings desc
limit 15
```

<BarChart
  data={top_skills}
  x="skill"
  y="postings"
  title="Top 15 Skills by Job Count"
  swapXY=true
/>

---

## Top Hiring Companies

```sql top_companies
select
    company,
    count(*)                      as open_roles,
    round(avg(fit_score), 0)      as avg_fit
from mart_active_jobs
group by company
order by open_roles desc
limit 15
```

<BarChart
  data={top_companies}
  x="company"
  y="open_roles"
  title="Companies with Most Open Roles"
  swapXY=true
/>

---

## Market Volume Trend

```sql market_trend
select
    snapshot_date,
    active_postings,
    hiring_companies,
    round(remote_share * 100, 1) as remote_pct
from mart_market_trends
order by snapshot_date
```

<LineChart
  data={market_trend}
  x="snapshot_date"
  y="active_postings"
  title="Active Postings Over Time"
/>
