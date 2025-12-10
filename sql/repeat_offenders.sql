-- Repeat Offenders: Vehicles in Top 10 Complaints for Multiple Years
WITH yearly_aggregates AS (
  SELECT
    MAKETXT,
    MODELTXT,
    YEARTXT,
    COUNT(*) AS complaints
  FROM flat_cmpl
  WHERE YEARTXT BETWEEN '2015' AND '2024'
  GROUP BY MAKETXT, MODELTXT, YEARTXT
),
yearly_rankings AS (
  SELECT
    MAKETXT,
    MODELTXT,
    YEARTXT,
    complaints,
    ROW_NUMBER() OVER (PARTITION BY YEARTXT ORDER BY complaints DESC) AS rank_in_year
  FROM yearly_aggregates
)
SELECT
  MAKETXT,
  MODELTXT,
  COUNT(DISTINCT YEARTXT) AS years_in_top10,
  SUM(complaints) AS total_complaints,
  STRING_AGG(YEARTXT, ', ' ORDER BY YEARTXT) AS problem_years
FROM yearly_rankings
WHERE rank_in_year <= 10
GROUP BY MAKETXT, MODELTXT
HAVING COUNT(DISTINCT YEARTXT) >= 3
ORDER BY years_in_top10 DESC, total_complaints DESC;