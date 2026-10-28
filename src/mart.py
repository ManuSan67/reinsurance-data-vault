TABLES = {
    "dim_cedent": """
SELECT h.hk_cedent, h.cedent_code, s.cedent_name, s.country, s.rating
FROM {rv}.hub_cedent h
JOIN {rv}.sat_cedent s ON s.hk_cedent = h.hk_cedent
QUALIFY row_number() OVER (PARTITION BY h.hk_cedent ORDER BY s.load_date DESC) = 1""",
    "dim_treaty": """
SELECT h.hk_treaty, h.treaty_number, l.hk_cedent, s.line_of_business, s.treaty_type,
       s.underwriting_year, s.inception_date, s.expiry_date, s.currency,
       s.ceded_share, s.retention, s.limit_amount
FROM {rv}.hub_treaty h
JOIN {rv}.sat_treaty_terms s ON s.hk_treaty = h.hk_treaty
JOIN {rv}.link_treaty_cedent l ON l.hk_treaty = h.hk_treaty
QUALIFY row_number() OVER (PARTITION BY h.hk_treaty ORDER BY s.load_date DESC) = 1""",
    "fact_premium": """
SELECT hk_treaty, load_date AS month,
       CAST(gross_premium AS decimal(18,2)) AS gross_premium,
       CAST(ceded_premium AS decimal(18,2)) AS ceded_premium
FROM {rv}.nhl_treaty_premium""",
    "fact_claim_month": """
SELECT hk_treaty, snapshot_date AS month, count(*) AS claims,
       sum(gross_incurred) AS gross_incurred, sum(ceded_incurred) AS ceded_incurred
FROM {bv}.claim_ceded
WHERE treaty_type IS NOT NULL
GROUP BY hk_treaty, snapshot_date""",
    "loss_ratio": """
WITH premium AS (
  SELECT hk_treaty, sum(gross_premium) AS gross_premium, sum(ceded_premium) AS ceded_premium
  FROM {mart}.fact_premium
  GROUP BY hk_treaty
),
claims AS (
  SELECT hk_treaty, claims, gross_incurred, ceded_incurred
  FROM {mart}.fact_claim_month
  WHERE month = (SELECT max(month) FROM {mart}.fact_claim_month)
)
SELECT t.treaty_number, c.cedent_name, t.line_of_business, t.treaty_type, t.underwriting_year,
       coalesce(cl.claims, 0) AS claims,
       p.gross_premium, coalesce(cl.gross_incurred, 0) AS gross_incurred,
       round(coalesce(cl.gross_incurred, 0) / nullif(p.gross_premium, 0), 3) AS gross_loss_ratio,
       p.ceded_premium, coalesce(cl.ceded_incurred, 0) AS ceded_incurred,
       round(coalesce(cl.ceded_incurred, 0) / nullif(p.ceded_premium, 0), 3) AS ceded_loss_ratio
FROM {mart}.dim_treaty t
JOIN {mart}.dim_cedent c ON c.hk_cedent = t.hk_cedent
LEFT JOIN premium p ON p.hk_treaty = t.hk_treaty
LEFT JOIN claims cl ON cl.hk_treaty = t.hk_treaty""",
}


def statements(rv, bv, mart):
    yield f"CREATE SCHEMA IF NOT EXISTS {mart}"
    for table, sql in TABLES.items():
        yield f"CREATE OR REPLACE TABLE {mart}.{table} AS" + sql.format(rv=rv, bv=bv, mart=mart)