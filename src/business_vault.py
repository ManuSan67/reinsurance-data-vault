PITS = {
    "pit_cedent": ("hk_cedent", "sat_cedent"),
    "pit_treaty": ("hk_treaty", "sat_treaty_terms"),
    "pit_claim": ("hk_claim", "sat_claim_status"),
}

CAUSES = ["incendio", "inundación", "sismo", "choque", "robo", "avería de carga"]

CEDED = """CREATE OR REPLACE TABLE {bv}.claim_ceded AS
WITH claims AS (
  SELECT pc.hk_claim, l.hk_treaty, pc.snapshot_date, c.loss_date, c.status,
         c.paid_to_date + c.outstanding AS gross_incurred
  FROM {bv}.pit_claim pc
  JOIN {rv}.sat_claim_status c ON c.hk_claim = pc.hk_claim AND c.load_date = pc.sat_claim_status_ldts
  JOIN {rv}.link_claim_treaty l ON l.hk_claim = pc.hk_claim
)
SELECT c.*, t.treaty_type,
       CAST(CASE t.treaty_type
         WHEN 'QS' THEN c.gross_incurred * t.ceded_share
         WHEN 'XL' THEN least(greatest(c.gross_incurred - t.retention, 0), t.limit_amount)
       END AS decimal(18,2)) AS ceded_incurred
FROM claims c
LEFT JOIN {bv}.pit_treaty pt ON pt.hk_treaty = c.hk_treaty AND pt.snapshot_date = trunc(c.loss_date, 'MM')
LEFT JOIN {rv}.sat_treaty_terms t ON t.hk_treaty = pt.hk_treaty AND t.load_date = pt.sat_treaty_terms_ldts"""

CAUSE_TABLE = """CREATE TABLE IF NOT EXISTS {bv}.claim_cause (
  hk_claim STRING, hd_claim_note STRING, note STRING, predicted_cause STRING, classified_at TIMESTAMP)"""

CAUSE_LOAD = """INSERT INTO {bv}.claim_cause
SELECT n.hk_claim, n.hd_claim_note, n.note,
       ai_classify(n.note, ARRAY({causes})), current_timestamp()
FROM {rv}.sat_claim_note n
LEFT ANTI JOIN {bv}.claim_cause c ON c.hk_claim = n.hk_claim AND c.hd_claim_note = n.hd_claim_note"""


def pit(rv, bv, table, parent, sat):
    loads = " UNION ALL ".join(f"SELECT load_date FROM {rv}.{s}" for _, s in PITS.values())
    return f"""CREATE OR REPLACE TABLE {bv}.{table} AS
WITH snapshots AS (
  SELECT explode(sequence(first_month, last_month, interval 1 month)) AS snapshot_date
  FROM (SELECT min(load_date) AS first_month, max(load_date) AS last_month FROM ({loads}))
)
SELECT x.{parent}, s.snapshot_date, max(x.load_date) AS {sat}_ldts
FROM snapshots s
JOIN {rv}.{sat} x ON x.load_date <= s.snapshot_date
GROUP BY x.{parent}, s.snapshot_date"""


def statements(rv, bv):
    yield f"CREATE SCHEMA IF NOT EXISTS {bv}"
    for table, spec in PITS.items():
        yield pit(rv, bv, table, *spec)
    yield CEDED.format(rv=rv, bv=bv)
    yield CAUSE_TABLE.format(bv=bv)
    yield CAUSE_LOAD.format(rv=rv, bv=bv, causes=", ".join(f"'{c}'" for c in CAUSES))