---
title: Skill Demand
---

# Skill Demand

Which technical skills appear most in AE/DE postings right now, and how demand splits
between Analytics Engineer and Data Engineer roles.

```sql skills
select
    skill,
    postings,
    companies,
    ae_postings,
    de_postings,
    round(100.0 * ae_postings / nullif(postings, 0), 1) as ae_pct,
    round(100.0 * de_postings / nullif(postings, 0), 1) as de_pct
from mart_skill_demand
order by postings desc
```

## Top 25 Skills

```sql top25
select skill, postings, ae_postings, de_postings
from mart_skill_demand
order by postings desc
limit 25
```

<BarChart
  data={top25}
  x="skill"
  y="postings"
  title="Top 25 Skills — Total Postings"
  swapXY=true
/>

## AE vs DE Skill Split

```sql ae_vs_de
select skill, ae_postings, de_postings
from mart_skill_demand
where ae_postings + de_postings > 0
order by (ae_postings + de_postings) desc
limit 20
```

<BarChart
  data={ae_vs_de}
  x="skill"
  y={["ae_postings", "de_postings"]}
  title="Top 20 Skills — AE vs DE"
  swapXY=true
  type="stacked"
/>

## Full Skill Table

<DataTable data={skills} search=true />
