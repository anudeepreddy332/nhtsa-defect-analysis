-- Component Cost Analysis with Savings Potential
WITH component_costs AS (
  SELECT
    COMPDESC,
    COUNT(*) AS total_complaints,
    SUM(CASE WHEN CRASH = 'Y' THEN 1 ELSE 0 END) AS crash_count,
    SUM(INJURED) AS total_injuries,
    (COUNT(*) * 5000
     + SUM(CASE WHEN CRASH = 'Y' THEN 1 ELSE 0 END) * 50000
     + SUM(INJURED) * 100000
    )::bigint AS estimated_cost
  FROM flat_cmpl
  WHERE YEARTXT BETWEEN '2015' AND '2024'
    AND MAKETXT NOT IN ('UNKNOWN','FIRESTONE')
  GROUP BY COMPDESC
),
top10 AS (
  SELECT
    COMPDESC,
    total_complaints,
    crash_count,
    total_injuries,
    estimated_cost,
    (estimated_cost * 0.10)::bigint AS savings_10pct_numeric
  FROM component_costs
  ORDER BY estimated_cost DESC
  LIMIT 10
)
SELECT
  COMPDESC,
  total_complaints,
  crash_count,
  total_injuries,
  TO_CHAR(estimated_cost, 'FM$999,999,999') AS total_cost,
  TO_CHAR(savings_10pct_numeric, 'FM$999,999,999') AS savings_if_reduced_10pct
FROM top10
ORDER BY estimated_cost DESC;