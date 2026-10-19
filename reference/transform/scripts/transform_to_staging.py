"""Build a leakage-aware 8-week new-product trend feature mart.

NEW implementation. Reads the accumulated weekly source snapshots from S3.
For every first-sale cohort, emits weeks 0..7 with missing weeks zero-filled;
cumulative features are historical-only. The target label is NULL until week 7
has finished. Category-quarter p75 is based only on completed 8-week cohorts.

SOURCE CONTRACT: raw/wwi/{invoice_lines,invoices,products,product_categories}/
  week_start=YYYY-MM-DD/part-*.csv.gz, written by raw_ingest.py.
"""
import csv
import io
import json
import sys
from datetime import date

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import Window, functions as F, types as T

args = getResolvedOptions(sys.argv, [
    "JOB_NAME", "bucket", "processing_week_start", "processing_week_end",
    "staging_prefix", "threshold_key"
])
bucket = args["bucket"]
end = date.fromisoformat(args["processing_week_end"])
date.fromisoformat(args["processing_week_start"])
if end <= date.fromisoformat(args["processing_week_start"]):
    raise ValueError("processing_week_end must be after processing_week_start")

glue_context = GlueContext(SparkContext.getOrCreate())
spark = glue_context.spark_session
spark.conf.set("spark.sql.session.timeZone", "UTC")
job = Job(glue_context)
job.init(args["JOB_NAME"], args)
s3 = boto3.client("s3")

def paths(table):
    """Discover historical weekly batches, not only the current week."""
    prefix = "raw/wwi/{}/".format(table)
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys += [o["Key"] for o in page.get("Contents", [])
                 if o["Key"].endswith(".csv.gz")
                 and o["Key"].rsplit("/", 1)[-1].startswith("part-")]
    return ["s3://{}/{}".format(bucket, k) for k in sorted(keys)]

def read(table):
    files = paths(table)
    if not files:
        raise ValueError("Missing source history for " + table)
    return (spark.read.option("header", True).option("inferSchema", True)
            .csv(files))

inv = read("invoices").select(
    F.col("invoice_id").cast("long").alias("invoice_id"),
    F.to_date("invoice_date").alias("invoice_date"),
    F.coalesce(F.col("is_credit_note").cast("boolean"), F.lit(False)).alias("is_credit_note"),
)
lines = read("invoice_lines").select(
    F.col("invoice_id").cast("long").alias("invoice_id"),
    F.col("stock_item_id").cast("long").alias("stock_item_id"),
    F.col("quantity").cast("long").alias("quantity"),
    F.col("unit_price").cast("double").alias("unit_price"),
    F.col("line_profit").cast("double").alias("line_profit"),
)
# Extracts for a given week contain disjoint invoices, but whole-history
# reprocessing and retries may have duplicate snapshots. Deduplicate by
# invoice ID. Invoice-line IDs must also be deduplicated for exactly-once math.
# Note: historical correction/deletion semantics require a CDC design.
inv = inv.dropDuplicates(["invoice_id"])
if "invoice_line_id" in read("invoice_lines").columns:
    raw_lines = read("invoice_lines")
    lines = raw_lines.dropDuplicates(["invoice_line_id"]).select(
        F.col("invoice_id").cast("long").alias("invoice_id"),
        F.col("stock_item_id").cast("long").alias("stock_item_id"),
        F.col("quantity").cast("long").alias("quantity"),
        F.col("unit_price").cast("double").alias("unit_price"),
        F.col("line_profit").cast("double").alias("line_profit"),
    )
sales = (lines.join(inv, "invoice_id")
         .filter((F.col("quantity") > 0) & (~F.col("is_credit_note"))
                 & (F.col("invoice_date") < F.lit(end.isoformat())))
         .withColumn("week_end",
             F.expr("date_add(invoice_date, 7 - dayofweek(invoice_date))")))
if sales.limit(1).count() == 0:
    raise ValueError("No eligible historical sales through processing cutoff")

first = (sales.groupBy("stock_item_id")
         .agg(F.min("invoice_date").alias("launch_date")))
first = first.withColumn(
    "first_week_end",
    F.expr("date_add(launch_date, 7 - dayofweek(launch_date))"))
agg = (sales.groupBy("stock_item_id", "week_end")
       .agg(F.sum("quantity").cast("long").alias("units_sold_week"),
            F.sum(F.col("quantity") * F.col("unit_price")).alias("sales_amount_week"),
            F.sum("line_profit").alias("profit_week"),
            F.countDistinct("invoice_id").cast("long").alias("distinct_customers_week")))
# Zero-fill missing weeks only within the first 8-week period.
# Do not generate unfinished future weeks.
cutoff = end.toordinal()
last_complete_saturday = date.fromordinal(
    cutoff - 1 - ((date.fromordinal(cutoff - 1).weekday() + 2) % 7))
cohorts = first.withColumn("last_week_end",
    F.least(F.date_add("first_week_end", 49),
            F.lit(last_complete_saturday.isoformat()).cast("date")))
cohorts = cohorts.filter(F.col("last_week_end") >= F.col("first_week_end"))
weeks = (cohorts.withColumn(
    "week_end",
    F.explode(F.sequence("first_week_end", "last_week_end", F.expr("interval 7 days"))))
    .withColumn("weeks_since_launch",
        (F.datediff("week_end", "first_week_end") / 7).cast("int")))
weekly = (weeks.join(agg, ["stock_item_id", "week_end"], "left")
          .fillna({"units_sold_week": 0, "sales_amount_week": 0.0,
                   "profit_week": 0.0, "distinct_customers_week": 0}))
w = (Window.partitionBy("stock_item_id").orderBy("week_end")
     .rowsBetween(Window.unboundedPreceding, Window.currentRow))
prev = Window.partitionBy("stock_item_id").orderBy("week_end")
weekly = (weekly
    .withColumn("cumulative_units_to_date", F.sum("units_sold_week").over(w))
    .withColumn("cumulative_sales_to_date", F.sum("sales_amount_week").over(w))
    .withColumn("cumulative_customers_proxy", F.sum("distinct_customers_week").over(w))
    .withColumn("prev_week_units", F.lag("units_sold_week").over(prev))
    .withColumn("prev_week_sales", F.lag("sales_amount_week").over(prev))
    .withColumn("wow_units_growth_rate",
        F.when(F.col("prev_week_units").isNotNull() & (F.col("prev_week_units") != 0),
            (F.col("units_sold_week") - F.col("prev_week_units")) /
             F.col("prev_week_units")).otherwise(F.lit(None).cast("double")))
    .withColumn("avg_unit_price_week",
        F.when(F.col("units_sold_week") > 0,
            F.col("sales_amount_week") / F.col("units_sold_week"))
         .otherwise(F.lit(None).cast("double"))))
# Weekly records use the first known sale as an explicitly documented proxy
# for launch_date. A trusted product launch/master-data date should replace it.
products = (read("products")
    .select("stock_item_id", "stock_item_name", "supplier_id", "brand", "size",
            "lead_time_days", "quantity_per_outer", "is_chiller_stock",
            "unit_price", "recommended_retail_price", "quantity_on_hand",
            "reorder_level", "target_stock_level")
    .dropDuplicates(["stock_item_id"]))
categories = (read("product_categories")
    .groupBy("stock_item_id")
    .agg(F.min("stock_group_name").alias("primary_stock_group_name")))
weekly = (weekly.join(products, "stock_item_id", "left")
          .join(categories, "stock_item_id", "left"))
weekly = weekly.withColumn("launch_quarter", F.concat(
    F.year("launch_date").cast("string"), F.lit("-Q"),
    F.quarter("launch_date").cast("string")))
finished = (weekly.filter(F.col("weeks_since_launch") == 7)
    .select("stock_item_id", "launch_quarter",
        F.col("cumulative_units_to_date").alias("first_8wk_units"),
        F.col("cumulative_sales_to_date").alias("first_8wk_sales"),
        F.col("cumulative_customers_proxy").alias("first_8wk_customers")))
cutoffs = finished.groupBy("launch_quarter").agg(
    F.expr("percentile_approx(first_8wk_units, 0.75, 10000)").alias("p75_cutoff"))
threshold_obj = s3.get_object(Bucket=bucket, Key=args["threshold_key"])
threshold_rows = list(csv.DictReader(io.StringIO(
    threshold_obj["Body"].read().decode("utf-8"))))
minimum_units = next(
    (int(r["min_8week_units"]) for r in threshold_rows
     if r["product_category"] == "DEFAULT"), 0)
weekly = (weekly.join(finished, ["stock_item_id", "launch_quarter"], "left")
          .join(cutoffs, "launch_quarter", "left"))
# Critical leakage safeguard: final labels only available at completed week 7.
weekly = (weekly
    .withColumn("is_trending_8wk",
        F.when(F.col("weeks_since_launch") == 7,
            (F.col("first_8wk_units") >= F.col("p75_cutoff")) &
            (F.col("first_8wk_units") >= F.lit(minimum_units)))
         .cast("int"))
    .withColumn("first_8wk_units",
        F.when(F.col("weeks_since_launch") == 7, F.col("first_8wk_units")))
    .withColumn("first_8wk_sales",
        F.when(F.col("weeks_since_launch") == 7, F.col("first_8wk_sales")))
    .withColumn("first_8wk_customers",
        F.when(F.col("weeks_since_launch") == 7, F.col("first_8wk_customers"))))
mapping = [
    ("stock_item_id", "StockItemID", "long"),
    ("stock_item_name", "StockItemName", "string"),
    ("supplier_id", "SupplierID", "long"),
    ("brand", "Brand", "string"),
    ("size", "Size", "string"),
    ("lead_time_days", "LeadTimeDays", "int"),
    ("quantity_per_outer", "QuantityPerOuter", "int"),
    ("is_chiller_stock", "IsChillerStock", "boolean"),
    ("unit_price", "BaseUnitPrice", "double"),
    ("recommended_retail_price", "RecommendedRetailPrice", "double"),
    ("primary_stock_group_name", "PrimaryStockGroupName", "string"),
    ("quantity_on_hand", "QuantityOnHand", "int"),
    ("reorder_level", "ReorderLevel", "int"),
    ("target_stock_level", "TargetStockLevel", "int"),
    ("launch_date", "launch_date", "date"),
    ("launch_quarter", "launch_quarter", "string"),
    ("week_end", "as_of_week_end_date", "date"),
    ("weeks_since_launch", "weeks_since_launch", "int"),
    ("units_sold_week", "units_sold_week", "long"),
    ("sales_amount_week", "sales_amount_week", "double"),
    ("profit_week", "profit_week", "double"),
    ("distinct_customers_week", "distinct_customers_week", "long"),
    ("avg_unit_price_week", "avg_unit_price_week", "double"),
    ("cumulative_units_to_date", "cumulative_units_to_date", "long"),
    ("cumulative_sales_to_date", "cumulative_sales_to_date", "double"),
    ("cumulative_customers_proxy", "cumulative_customers_proxy", "long"),
    ("prev_week_units", "prev_week_units", "long"),
    ("prev_week_sales", "prev_week_sales", "double"),
    ("wow_units_growth_rate", "wow_units_growth_rate", "double"),
    ("first_8wk_units", "first_8wk_units", "long"),
    ("first_8wk_sales", "first_8wk_sales", "double"),
    ("first_8wk_customers", "first_8wk_customers", "long"),
    ("is_trending_8wk", "is_trending_8wk", "int"),
]
output = weekly.select(*(F.col(src).cast(kind).alias(dest)
                         for src, dest, kind in mapping))
if output.limit(1).count() == 0:
    raise ValueError("Refusing to publish empty feature mart")
path = "s3://{}/{}".format(bucket, args["staging_prefix"].lstrip("/"))
output.write.mode("overwrite").parquet(path)
job.commit()
