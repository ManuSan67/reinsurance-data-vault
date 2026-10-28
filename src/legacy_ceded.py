from pyspark.sql import Window
from pyspark.sql import functions as F


def ceded_claims(claims, treaties, as_of):
    claims = claims.where(F.col("load_date") <= as_of)
    current = (
        claims.withColumn("last_load", F.max("load_date").over(Window.partitionBy("claim_number")))
        .where(F.col("load_date") == F.col("last_load"))
    )
    terms = (
        treaties.withColumn(
            "rn", F.row_number().over(Window.partitionBy("treaty_number").orderBy(F.col("load_date").desc()))
        )
        .where("rn = 1")
        .select("treaty_number", "treaty_type", "ceded_share", "retention", "limit_amount")
    )
    gross = F.col("paid_to_date") + F.col("outstanding")
    ceded = F.when(F.col("treaty_type") == "QS", gross * F.col("ceded_share")).otherwise(
        F.least(F.greatest(gross - F.col("retention"), F.lit(0)), F.col("limit_amount"))
    )
    return current.join(terms, "treaty_number").select(
        F.lit(as_of).cast("date").alias("as_of_date"),
        "claim_number",
        "treaty_number",
        gross.alias("gross_incurred"),
        F.round(ceded, 2).cast("decimal(18,2)").alias("ceded_incurred"),
    )