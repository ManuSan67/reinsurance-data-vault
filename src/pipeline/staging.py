from pyspark import pipelines as dp
from pyspark.sql import functions as F

CATALOG = spark.conf.get("catalog", "reinsurance")
LANDING = f"/Volumes/{CATALOG}/landing/bordereaux"


def files(folder, fmt):
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", fmt)
        .option("cloudFiles.inferColumnTypes", str(fmt == "json").lower())
        .option("header", "true")
        .load(f"{LANDING}/{folder}")
        .select("*", "_metadata")
    )


def audit(df, source):
    month = F.regexp_extract("_metadata.file_path", r"_(\d{4}-\d{2})\.\w+$", 1)
    return (
        df.withColumn("load_date", F.to_date(F.concat(month, F.lit("-01"))))
        .withColumn("record_source", F.lit(source))
        .withColumn("source_file", F.col("_metadata.file_path"))
        .drop("_metadata")
    )


def hash_key(*cols):
    return F.sha2(F.concat_ws("||", *[F.upper(F.trim(F.col(c).cast("string"))) for c in cols]), 256)


def hash_diff(*cols):
    return F.sha2(F.concat_ws("||", *[F.coalesce(F.trim(F.col(c).cast("string")), F.lit("")) for c in cols]), 256)


def money(c):
    return F.col(c).cast("decimal(18,2)")


@dp.table(name="staging.stg_cedents", comment="Cedent master data with hash key and hashdiff.")
def stg_cedents():
    return (
        audit(files("cedents", "json"), "reinsurer.cedents")
        .withColumn("hk_cedent", hash_key("cedent_code"))
        .withColumn("hd_cedent", hash_diff("cedent_name", "country", "rating"))
    )


@dp.table(name="staging.stg_treaties", comment="Treaty terms, including endorsements, with hash keys.")
def stg_treaties():
    return (
        audit(files("treaties", "json"), "reinsurer.treaties")
        .withColumnRenamed("limit", "limit_amount")
        .withColumn("inception_date", F.to_date("inception_date"))
        .withColumn("expiry_date", F.to_date("expiry_date"))
        .withColumn("hk_treaty", hash_key("treaty_number"))
        .withColumn("hk_cedent", hash_key("cedent_code"))
        .withColumn("hk_treaty_cedent", hash_key("treaty_number", "cedent_code"))
        .withColumn("hd_treaty", hash_diff(
            "line_of_business", "treaty_type", "underwriting_year", "inception_date", "expiry_date",
            "currency", "ceded_share", "retention", "limit_amount"))
    )


@dp.table(name="staging.stg_premiums", comment="Monthly premium bordereaux per treaty.")
def stg_premiums():
    return (
        audit(files("premiums", "json"), "reinsurer.premiums")
        .withColumn("gross_premium", money("gross_premium"))
        .withColumn("ceded_premium", money("ceded_premium"))
        .withColumn("hk_treaty", hash_key("treaty_number"))
    )


dp.create_streaming_table(
    name="staging.stg_claims",
    comment="Claims bordereaux from all cedents in one layout. Rows are kept even when they fail a rule.",
    expect_all={
        "claim_number_present": "claim_number IS NOT NULL",
        "loss_date_parsed": "loss_date IS NOT NULL",
        "status_known": "status IS NOT NULL",
    },
)


def claims(df, cedent):
    return (
        audit(df, f"{cedent}.claims_bordereau")
        .withColumn("cedent_code", F.lit(cedent))
        .withColumn("hk_claim", hash_key("claim_number"))
        .withColumn("hk_treaty", hash_key("treaty_number"))
        .withColumn("hk_claim_treaty", hash_key("claim_number", "treaty_number"))
        .withColumn("hd_claim", hash_diff("loss_date", "paid_to_date", "outstanding", "status"))
    )


@dp.append_flow(target="staging.stg_claims", name="claims_ced01")
def claims_ced01():
    df = files("claims/CED01", "csv").select(
        F.col("numero_siniestro").alias("claim_number"),
        F.col("numero_contrato").alias("treaty_number"),
        F.to_date("fecha_siniestro", "dd/MM/yyyy").alias("loss_date"),
        money("pagado_acumulado").alias("paid_to_date"),
        money("reserva").alias("outstanding"),
        F.when(F.col("estatus") == "ABIERTO", "OPEN").when(F.col("estatus") == "CERRADO", "CLOSED").alias("status"),
        "_metadata",
    )
    return claims(df, "CED01")


@dp.append_flow(target="staging.stg_claims", name="claims_ced02")
def claims_ced02():
    df = files("claims/CED02", "json").select(
        "claim_number",
        "treaty_number",
        F.to_date("loss_date").alias("loss_date"),
        money("paid_to_date").alias("paid_to_date"),
        money("outstanding").alias("outstanding"),
        "status",
        "_metadata",
    )
    return claims(df, "CED02")


@dp.append_flow(target="staging.stg_claims", name="claims_ced03")
def claims_ced03():
    df = files("claims/CED03", "csv").select(
        F.col("ClaimRef").alias("claim_number"),
        F.col("TreatyRef").alias("treaty_number"),
        F.to_date("DateOfLoss", "yyyyMMdd").alias("loss_date"),
        money("Paid").alias("paid_to_date"),
        money("Reserve").alias("outstanding"),
        F.when(F.col("Status") == "O", "OPEN").when(F.col("Status") == "C", "CLOSED").alias("status"),
        "_metadata",
    )
    return claims(df, "CED03")