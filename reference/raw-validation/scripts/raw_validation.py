import sys
import json
import statistics
import boto3

from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "raw_bucket",
    "processing_week_start",
    "processing_week_end",
    "config_key",
    "manifest_key",
    "audit_prefix"
])

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

s3 = boto3.client("s3")
bucket = args["raw_bucket"]
week_start = args["processing_week_start"]
week_end = args["processing_week_end"]
audit_prefix = args["audit_prefix"].rstrip("/") + "/"

def load_json(key):
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))

def list_objects(prefix):
    paginator = s3.get_paginator("list_objects_v2")
    rows = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        rows.extend(page.get("Contents", []))
    return [x for x in rows if x.get("Size", 0) > 0]

def normalize_type(t):
    t = str(t).lower()
    if t in ("int", "integer", "smallint", "tinyint", "bigint", "long"):
        return "integer"
    if t.startswith("decimal") or t in ("double", "float"):
        return "decimal"
    if t in ("date",):
        return "date"
    if t in ("timestamp",):
        return "timestamp"
    if t in ("boolean", "bool"):
        return "boolean"
    return "string"

def recent_counts(table_name, limit_n):
    prefix = audit_prefix + "table=" + table_name + "/"
    objs = sorted(list_objects(prefix), key=lambda x: x["LastModified"], reverse=True)
    vals = []
    for item in objs[:limit_n]:
        try:
            doc = load_json(item["Key"])
            if "row_count" in doc:
                vals.append(int(doc["row_count"]))
        except Exception:
            pass
    return vals

config = load_json(args["config_key"])
manifest = load_json(args["manifest_key"])

errors = []
warnings = []
summary = {
    "run_id": manifest.get("run_id"),
    "processing_week_start": week_start,
    "processing_week_end_exclusive": week_end,
    "tables": {}
}

if manifest.get("processing_week_start") != week_start:
    errors.append("Manifest processing_week_start does not match workflow input.")
if manifest.get("processing_week_end_exclusive") != week_end:
    errors.append("Manifest processing_week_end_exclusive does not match workflow input.")

for table_name, rule in config["tables"].items():
    tresult = {"checks": {}}
    summary["tables"][table_name] = tresult
    m = manifest.get("tables", {}).get(table_name)

    if not m:
        errors.append(table_name + ": missing from ingestion manifest")
        tresult["checks"]["manifest_entry"] = "FAIL"
        continue

    prefix = m["prefix"]
    objects = list_objects(prefix)
    actual_keys = sorted([x["Key"] for x in objects])
    expected_keys = sorted(m.get("expected_files", []))

    # 1. Expected files exist and are readable at the S3 level.
    missing = sorted(set(expected_keys) - set(actual_keys))
    unexpected = sorted(set(actual_keys) - set(expected_keys)) if expected_keys else []
    if not actual_keys or missing:
        errors.append(table_name + ": expected raw files are missing")
        tresult["checks"]["expected_files"] = "FAIL"
    else:
        tresult["checks"]["expected_files"] = "PASS"

    # 2. Detect unexpected/duplicate physical file copies.
    # Exact expected-key reconciliation is the primary control.
    if unexpected:
        errors.append(table_name + ": unexpected extra raw files found: " + ",".join(unexpected))
        tresult["checks"]["duplicate_or_extra_files"] = "FAIL"
    else:
        fingerprints = {}
        dup_fingerprints = []
        for o in objects:
            fp = (str(o.get("ETag","")).strip('"'), int(o.get("Size",0)))
            if fp in fingerprints:
                dup_fingerprints.append((fingerprints[fp], o["Key"]))
            else:
                fingerprints[fp] = o["Key"]
        if dup_fingerprints:
            errors.append(table_name + ": files with duplicate content fingerprints detected")
            tresult["checks"]["duplicate_or_extra_files"] = "FAIL"
        else:
            tresult["checks"]["duplicate_or_extra_files"] = "PASS"

    if not actual_keys:
        continue

    # 3. Readability check plus row-level validations.
    try:
        df = (
            spark.read
                 .option("header", "true")
                 .option("inferSchema", "true")
                 .option("sep", m.get("delimiter", ","))
                 .csv(["s3://" + bucket + "/" + k for k in actual_keys])
        )
        row_count = df.count()
        tresult["row_count"] = row_count
        tresult["checks"]["readable"] = "PASS"
    except Exception as e:
        errors.append(table_name + ": Spark could not read the raw files: " + str(e))
        tresult["checks"]["readable"] = "FAIL"
        continue

    # 4. Source-to-raw row-count reconciliation and non-zero check.
    expected_count = int(m.get("source_row_count", -1))
    if row_count == 0:
        errors.append(table_name + ": raw row count is zero")
        tresult["checks"]["non_zero"] = "FAIL"
    else:
        tresult["checks"]["non_zero"] = "PASS"

    if expected_count >= 0 and row_count != expected_count:
        errors.append(table_name + ": source/raw row count mismatch. source=" + str(expected_count) + ", raw=" + str(row_count))
        tresult["checks"]["source_to_raw_count"] = "FAIL"
    else:
        tresult["checks"]["source_to_raw_count"] = "PASS"

    # 5. Compare row count to recent successful weekly validations.
    history = recent_counts(table_name, int(config.get("recent_runs_to_compare", 4)))
    if len(history) >= 3 and row_count > 0:
        baseline = statistics.median(history)
        variance = abs(row_count - baseline) / baseline if baseline else 0
        limit = float(config.get("row_count_variance_pct", 40)) / 100.0
        tresult["recent_median"] = baseline
        tresult["variance_from_recent_median"] = variance
        if variance > limit:
            errors.append(table_name + ": row count is abnormally different from recent weekly runs")
            tresult["checks"]["recent_row_count"] = "FAIL"
        else:
            tresult["checks"]["recent_row_count"] = "PASS"
    else:
        tresult["checks"]["recent_row_count"] = "NOT_ENOUGH_HISTORY"

    # 6. Required columns.
    actual_cols = set(df.columns)
    missing_cols = [c for c in rule.get("required_columns", []) if c not in actual_cols]
    if missing_cols:
        errors.append(table_name + ": required columns missing: " + ",".join(missing_cols))
        tresult["checks"]["required_columns"] = "FAIL"
    else:
        tresult["checks"]["required_columns"] = "PASS"

    # 7. Schema/type comparison to the schema captured from SQL Server at extraction time.
    actual_types = {c: normalize_type(t) for c, t in df.dtypes}
    source_schema = {c: normalize_type(t) for c, t in m.get("source_schema", {}).items()}
    type_mismatches = {}
    for c, expected_type in source_schema.items():
        if c in actual_types and actual_types[c] != expected_type:
            type_mismatches[c] = {"expected": expected_type, "actual": actual_types[c]}
    if type_mismatches:
        errors.append(table_name + ": unexpected data-type changes detected: " + json.dumps(type_mismatches))
        tresult["checks"]["schema_types"] = "FAIL"
    else:
        tresult["checks"]["schema_types"] = "PASS"

    # 8. Critical source keys cannot be NULL.
    null_failures = {}
    for c in rule.get("critical_keys", []):
        if c in actual_cols:
            n = df.filter(F.col(c).isNull()).count()
            if n:
                null_failures[c] = n
    if null_failures:
        errors.append(table_name + ": critical keys contain NULLs: " + json.dumps(null_failures))
        tresult["checks"]["critical_keys_not_null"] = "FAIL"
    else:
        tresult["checks"]["critical_keys_not_null"] = "PASS"

    # 9. Processing-window coverage.
    date_col = rule.get("date_column")
    if date_col and date_col in actual_cols:
        dated = df.withColumn("_validation_date", F.to_date(F.col(date_col)))
        outside = dated.filter(
            (F.col("_validation_date") < F.lit(week_start)) |
            (F.col("_validation_date") >= F.lit(week_end)) |
            F.col("_validation_date").isNull()
        ).count()
        daily_actual = {
            str(r["_validation_date"]): int(r["count"])
            for r in dated.groupBy("_validation_date").count().collect()
            if r["_validation_date"] is not None
        }
        daily_expected = {str(k): int(v) for k, v in m.get("daily_counts", {}).items()}
        if outside:
            errors.append(table_name + ": records exist outside the processing window or have invalid dates")
            tresult["checks"]["processing_window"] = "FAIL"
        elif daily_expected and daily_actual != daily_expected:
            errors.append(table_name + ": daily source/raw counts do not reconcile across the Sunday-to-Saturday window")
            tresult["checks"]["processing_window"] = "FAIL"
        else:
            tresult["checks"]["processing_window"] = "PASS"
    else:
        tresult["checks"]["processing_window"] = "NOT_APPLICABLE"

    # Store this table's count as audit history for future weekly comparisons.
    audit_doc = {
        "run_id": manifest.get("run_id"),
        "table": table_name,
        "processing_week_start": week_start,
        "processing_week_end_exclusive": week_end,
        "row_count": row_count
    }
    audit_key = audit_prefix + "table=" + table_name + "/week_start=" + week_start + ".json"
    s3.put_object(
        Bucket=bucket,
        Key=audit_key,
        Body=json.dumps(audit_doc, indent=2).encode("utf-8"),
        ContentType="application/json"
    )

summary["status"] = "FAIL" if errors else "PASS"
summary["errors"] = errors
summary["warnings"] = warnings

result_key = audit_prefix + "runs/run_id=" + str(manifest.get("run_id","unknown")) + "/validation-summary.json"
s3.put_object(
    Bucket=bucket,
    Key=result_key,
    Body=json.dumps(summary, indent=2).encode("utf-8"),
    ContentType="application/json"
)

if errors:
    raise RuntimeError("Raw-data validation failed. " + json.dumps(errors))

job.commit()
