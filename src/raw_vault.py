HUBS = {
    "hub_cedent": (["hk_cedent"], ["cedent_code"], ["stg_cedents", "stg_treaties"]),
    "hub_treaty": (["hk_treaty"], ["treaty_number"], ["stg_treaties", "stg_premiums", "stg_claims"]),
    "hub_claim": (["hk_claim"], ["claim_number"], ["stg_claims"]),
}
LINKS = {
    "link_treaty_cedent": (["hk_treaty_cedent"], ["hk_treaty", "hk_cedent"], ["stg_treaties"]),
    "link_claim_treaty": (["hk_claim_treaty"], ["hk_claim", "hk_treaty"], ["stg_claims"]),
    "nhl_treaty_premium": (["hk_treaty", "period"], ["gross_premium", "ceded_premium"], ["stg_premiums"]),
}
SATELLITES = {
    "sat_cedent": ("hk_cedent", "hd_cedent", ["cedent_name", "country", "rating"], "stg_cedents"),
    "sat_treaty_terms": ("hk_treaty", "hd_treaty", [
        "line_of_business", "treaty_type", "underwriting_year", "inception_date", "expiry_date",
        "currency", "ceded_share", "retention", "limit_amount"], "stg_treaties"),
    "sat_claim_status": ("hk_claim", "hd_claim", ["loss_date", "paid_to_date", "outstanding", "status"], "stg_claims"),
}


def insert_new_keys(stg, rv, table, keys, cols, sources):
    select = ", ".join(keys + cols + ["load_date", "record_source"])
    union = " UNION ALL ".join(f"SELECT {select} FROM {stg}.{s}" for s in sources)
    on = " AND ".join(f"s.{k} = t.{k}" for k in keys)
    return [
        f"CREATE TABLE IF NOT EXISTS {rv}.{table} AS SELECT {select} FROM {stg}.{sources[0]} LIMIT 0",
        f"""INSERT INTO {rv}.{table}
SELECT {select} FROM (
  SELECT *, row_number() OVER (PARTITION BY {", ".join(keys)} ORDER BY load_date, record_source) AS rn
  FROM ({union})
) s
LEFT ANTI JOIN {rv}.{table} t ON {on}
WHERE s.rn = 1""",
    ]


def insert_changes(stg, rv, table, parent, hd, cols, source):
    select = ", ".join([parent, hd] + cols + ["load_date", "record_source"])
    return [
        f"CREATE TABLE IF NOT EXISTS {rv}.{table} AS SELECT {select} FROM {stg}.{source} LIMIT 0",
        f"""INSERT INTO {rv}.{table}
SELECT {select} FROM (
  SELECT s.*,
         lag(s.{hd}) OVER (PARTITION BY s.{parent} ORDER BY s.load_date) AS prev_hd,
         l.last_hd
  FROM (SELECT DISTINCT {select} FROM {stg}.{source}) s
  LEFT JOIN (
    SELECT {parent}, {hd} AS last_hd, load_date AS last_load FROM (
      SELECT {parent}, {hd}, load_date,
             row_number() OVER (PARTITION BY {parent} ORDER BY load_date DESC) AS rn
      FROM {rv}.{table}
    ) WHERE rn = 1
  ) l ON s.{parent} = l.{parent}
  WHERE l.last_load IS NULL OR s.load_date > l.last_load
)
WHERE NOT ({hd} <=> coalesce(prev_hd, last_hd))""",
    ]


def statements(stg, rv):
    for table, spec in {**HUBS, **LINKS}.items():
        yield from insert_new_keys(stg, rv, table, *spec)
    for table, spec in SATELLITES.items():
        yield from insert_changes(stg, rv, table, *spec)