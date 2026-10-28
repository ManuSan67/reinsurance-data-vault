from datetime import date
from decimal import Decimal

from pyspark.sql import SparkSession

from legacy_ceded import ceded_claims

spark = SparkSession.builder.master("local[1]").getOrCreate()


def test_reproduces_stored_procedure():
    treaties = spark.createDataFrame(
        [
            ("T-QS", "QS", 0.50, 0.0, 0.0, date(2024, 1, 1)),
            ("T-QS", "QS", 0.35, 0.0, 0.0, date(2024, 7, 1)),
            ("T-XL", "XL", 0.0, 1_000_000.0, 4_000_000.0, date(2024, 1, 1)),
        ],
        "treaty_number string, treaty_type string, ceded_share double, retention double, limit_amount double, load_date date",
    )
    claims = spark.createDataFrame(
        [
            ("C1", "T-QS", 50_000.0, 10_000.0, date(2024, 2, 1)),
            ("C1", "T-QS", 60_000.0, 40_000.0, date(2024, 3, 1)),
            ("C2", "T-XL", 300_000.0, 500_000.0, date(2024, 3, 1)),
            ("C3", "T-XL", 2_000_000.0, 4_000_000.0, date(2024, 3, 1)),
            ("C4", "T-XL", 1_500_000.0, 1_000_000.0, date(2024, 3, 1)),
            ("C5", "T-NONE", 10_000.0, 0.0, date(2024, 3, 1)),
            ("C6", "T-QS", 10_000.0, 0.0, date(2025, 1, 1)),
        ],
        "claim_number string, treaty_number string, paid_to_date double, outstanding double, load_date date",
    )

    result = {r.claim_number: r.ceded_incurred for r in ceded_claims(claims, treaties, date(2024, 12, 1)).collect()}

    assert result == {
        "C1": Decimal("35000.00"),
        "C2": Decimal("0.00"),
        "C3": Decimal("4000000.00"),
        "C4": Decimal("1500000.00"),
    }
