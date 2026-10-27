import csv
import json
import math
import os
import random
from datetime import date

START_YEAR, START_MONTH = 2024, 1

CEDENTS = [  # code, name, country, rating
    ("CED01", "Aseguradora Sierra", "MX", "A"),
    ("CED02", "Seguros Costa Azul", "MX", "A-"),
    ("CED03", "Meridiano Insurance Group", "CO", "BBB+"),
]
RATING_CHANGE = ("CED02", 9, "BBB+")  # cedent, month index, new rating

LINES = {  # line: treaty type, claims per month, median gross loss (USD), log sigma, annual gross premium
    "PROPERTY": ("XL", 1.5, 150_000, 0.9, 9_000_000),
    "MOTOR": ("QS", 6.0, 40_000, 0.8, 6_000_000),
    "MARINE": ("QS", 0.5, 200_000, 1.1, 3_000_000),
}
XL_RETENTION, XL_LIMIT, XL_RATE = 1_000_000, 4_000_000, 0.10
QS_SHARES = [0.30, 0.40, 0.50]
ENDORSEMENT = ("T-CED01-MOTOR-2024", 6, 0.35)  # treaty, month index, new ceded share
ORPHAN_CLAIM = ("CED01", 4, "T-CED01-AVIATION-2024")  # claim sent against a treaty we never wrote
DUPLICATE_RATE = 0.02  # CED03 re-sends some rows in the same file


def month_of(i):
    y, m = divmod(START_MONTH - 1 + i, 12)
    return date(START_YEAR + y, m + 1, 1)


def _next(d):
    return date(d.year + d.month // 12, d.month % 12 + 1, 1)


def _poisson(rng, lam):
    k, p, limit = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p < limit:
            return k
        k += 1


def build_treaties(seed, year):
    rng = random.Random(seed * 31 + year)
    treaties = []
    for code, *_ in CEDENTS:
        for line, (ttype, *_) in LINES.items():
            treaties.append({
                "treaty_number": f"T-{code}-{line}-{year}",
                "cedent_code": code,
                "line_of_business": line,
                "treaty_type": ttype,
                "underwriting_year": year,
                "inception_date": f"{year}-01-01",
                "expiry_date": f"{year}-12-31",
                "currency": "USD",
                "ceded_share": rng.choice(QS_SHARES) if ttype == "QS" else None,
                "retention": XL_RETENTION if ttype == "XL" else None,
                "limit": XL_LIMIT if ttype == "XL" else None,
                "updated_at": f"{year}-01-01",
            })
    return treaties


def ceded_premium(t, gross):
    if t["treaty_type"] == "QS":
        return round(gross * t["ceded_share"], 2)
    return round(XL_RATE * XL_LIMIT / 12, 2)


class Book:
    """Replays the history month by month, so every run produces the same files."""

    def __init__(self, seed):
        self.seed = seed
        self.treaties = {}
        self.claims = {}
        self.seq = 0

    def step(self, i):
        rng = random.Random(self.seed * 7_919 + i)
        period = month_of(i)
        out = {"cedents": [], "treaties": [], "premiums": [], "claims": {c[0]: [] for c in CEDENTS}}

        if i == 0:
            out["cedents"] = [{"cedent_code": c, "cedent_name": n, "country": k, "rating": r,
                               "updated_at": period.isoformat()} for c, n, k, r in CEDENTS]
        code, at, rating = RATING_CHANGE
        if i == at:
            _, name, country, _ = next(c for c in CEDENTS if c[0] == code)
            out["cedents"] = [{"cedent_code": code, "cedent_name": name, "country": country,
                               "rating": rating, "updated_at": period.isoformat()}]

        if period.month == 1:
            new = build_treaties(self.seed, period.year)
            self.treaties.update({t["treaty_number"]: t for t in new})
            out["treaties"] += new
        number, at, share = ENDORSEMENT
        if i == at:
            t = self.treaties[number] = dict(self.treaties[number], ceded_share=share,
                                             updated_at=period.isoformat())
            out["treaties"].append(t)

        for t in (t for t in self.treaties.values() if t["underwriting_year"] == period.year):
            _, freq, median, sigma, annual = LINES[t["line_of_business"]]
            gross = round(annual / 12 * rng.uniform(0.9, 1.1), 2)
            out["premiums"].append({"treaty_number": t["treaty_number"], "period": period.isoformat()[:7],
                                    "gross_premium": gross, "ceded_premium": ceded_premium(t, gross)})
            for _ in range(_poisson(rng, freq)):
                self._open_claim(rng, t["treaty_number"], t["cedent_code"], period, median, sigma)

        code, at, treaty = ORPHAN_CLAIM
        if i == at:
            self._open_claim(rng, treaty, code, period, 200_000, 0.5)

        for c in self.claims.values():
            if c["status"] == "CLOSED" or c["reported"] > period:
                continue
            self._develop(rng, c)
            out["claims"][c["cedent_code"]].append({k: c[k] for k in (
                "claim_number", "treaty_number", "loss_date", "paid_to_date", "outstanding", "status")})
        return out

    def _open_claim(self, rng, treaty_number, cedent, period, median, sigma):
        self.seq += 1
        number = f"{cedent}-C{self.seq:06d}"
        self.claims[number] = {
            "claim_number": number,
            "treaty_number": treaty_number,
            "cedent_code": cedent,
            "loss_date": period.replace(day=rng.randint(1, 28)).isoformat(),
            "reported": period if rng.random() < 0.7 else _next(period),
            "ultimate": rng.lognormvariate(math.log(median), sigma),
            "months_left": rng.randint(3, 12),
            "paid_to_date": 0.0,
            "outstanding": 0.0,
            "status": "OPEN",
        }

    @staticmethod
    def _develop(rng, c):
        c["months_left"] -= 1
        if c["months_left"] <= 0:
            c["paid_to_date"], c["outstanding"], c["status"] = round(c["ultimate"], 2), 0.0, "CLOSED"
            return
        c["paid_to_date"] = round(min(c["ultimate"], c["paid_to_date"] + c["ultimate"] * rng.uniform(0.05, 0.25)), 2)
        c["outstanding"] = round(max(0.0, c["ultimate"] * rng.uniform(0.9, 1.15) - c["paid_to_date"]), 2)


# Each cedent sends its claims bordereau in its own layout.
def _ced01(rows):
    status = {"OPEN": "ABIERTO", "CLOSED": "CERRADO"}
    header = ["numero_siniestro", "numero_contrato", "fecha_siniestro", "pagado_acumulado", "reserva", "estatus"]
    return header, [[r["claim_number"], r["treaty_number"], date.fromisoformat(r["loss_date"]).strftime("%d/%m/%Y"),
                     r["paid_to_date"], r["outstanding"], status[r["status"]]] for r in rows]


def _ced03(rows, rng):
    header = ["ClaimRef", "TreatyRef", "DateOfLoss", "Paid", "Reserve", "Status"]
    out = [[r["claim_number"], r["treaty_number"], r["loss_date"].replace("-", ""),
            r["paid_to_date"], r["outstanding"], r["status"][0]] for r in rows]
    return header, out + [list(r) for r in out if rng.random() < DUPLICATE_RATE]


def _write_json(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)


def _write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def next_month(root):
    """Index of the first month not yet written (0 if the landing folder is empty)."""
    folder = os.path.join(root, "premiums")
    return len(os.listdir(folder)) if os.path.isdir(folder) else 0


def write_months(root, n_months, seed=7):
    """Write the next `n_months` monthly bordereaux after whatever is already in `root`."""
    first = next_month(root)
    book = Book(seed)
    for i in range(first + n_months):
        out = book.step(i)
        if i < first:
            continue
        ym = month_of(i).isoformat()[:7]
        if out["cedents"]:
            _write_json(f"{root}/cedents/cedents_{ym}.json", out["cedents"])
        if out["treaties"]:
            _write_json(f"{root}/treaties/treaties_{ym}.json", out["treaties"])
        _write_json(f"{root}/premiums/premiums_{ym}.json", out["premiums"])
        _write_csv(f"{root}/claims/CED01/claims_{ym}.csv", *_ced01(out["claims"]["CED01"]))
        _write_json(f"{root}/claims/CED02/claims_{ym}.json", out["claims"]["CED02"])
        _write_csv(f"{root}/claims/CED03/claims_{ym}.csv", *_ced03(out["claims"]["CED03"], random.Random(seed * 13 + i)))
    return first, first + n_months - 1