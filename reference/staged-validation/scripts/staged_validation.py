import sys
import json
import time
import statistics
import boto3

from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from awsgluedq.transforms import EvaluateDataQuality
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "bucket",
    "staging_prefix",
    "processing_week_end",
    "config_key",
    "sql_prefix",
    "audit_prefix",
    "dq_ruleset_name",
    "athena_database",
    "athena_workgroup",
])

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

s3 = boto3.client("s3")
athena = boto3.client("athena")
glue = boto3.client("glue")

bucket = args["bucket"]
staging_prefix = args["staging_prefix"].strip("/")
audit_prefix = args["audit_prefix"].strip("/")
processing_week_end = args["processing_week_end"]

def read_text(key):
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read().decode("utf-8")

def read_json(key):
    return json.loads(read_text(key))

def normalize_type(data_type):
    t = str(data_type).lower()
    if t in ("long", "bigint"):
        return "bigint"
    if t in ("integer", "int", "smallint", "short"):
        return "int"
    if t.startswith("decimal") or t in ("double", "float"):
        return "double"
    if t in ("bool", "boolean"):
        return "boolean"
    if t == "date":
        return "date"
    if t == "timestamp":
        return "timestamp"
    return "string"

def list_keys(prefix, suffix=None):
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if item.get("Size", 0) == 0:
                continue
            if suffix is None or key.endswith(suffix):
                keys.append(key)
    return sorted(keys)

def recent_row_counts(limit_count):
    prefix = audit_prefix + "/counts/"
    objects = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects.extend(page.get("Contents", []))
    objects = sorted(objects, key=lambda x: x["LastModified"], reverse=True)
    counts = []
    for item in objects[:limit_count]:
        try:
            doc = read_json(item["Key"])
            counts.append(int(doc["row_count"]))
        except Exception:
            pass
    return counts

def wait_for_athena(query_execution_id):
    while True:
        response = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = response["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return state, response
        time.sleep(1)

config = read_json(args["config_key"])
errors = []
summary = {
    "processing_week_end": processing_week_end,
    "staging_prefix": staging_prefix,
    "checks": {},
    "athena_checks": []
}

# -------------------------------------------------------------------
# 1. Readability check: read the actual persisted staged Parquet.
# -------------------------------------------------------------------
staging_path = "s3://" + bucket + "/" + staging_prefix + "/"

try:
    staged_df = spark.read.parquet(staging_path)
    staged_row_count = staged_df.count()
    summary["staged_row_count"] = staged_row_count
    summary["checks"]["parquet_readable"] = "PASS"
except Exception as exc:
    raise RuntimeError("Staged Parquet files are not readable: " + str(exc))

# -------------------------------------------------------------------
# 2. Schema and data-type validation.
# -------------------------------------------------------------------
actual_schema = {name: normalize_type(dtype) for name, dtype in staged_df.dtypes}
expected_schema = {
    name: normalize_type(dtype)
    for name, dtype in config["expected_schema"].items()
}

schema_failures = {}
for column_name, expected_type in expected_schema.items():
    actual_type = actual_schema.get(column_name)
    if actual_type is None:
        schema_failures[column_name] = {
            "expected": expected_type,
            "actual": "MISSING"
        }
    elif actual_type != expected_type:
        schema_failures[column_name] = {
            "expected": expected_type,
            "actual": actual_type
        }

if schema_failures:
    summary["checks"]["schema_and_types"] = "FAIL"
    summary["schema_failures"] = schema_failures
    errors.append("Schema/data-type validation failed")
else:
    summary["checks"]["schema_and_types"] = "PASS"

# -------------------------------------------------------------------
# 3. Expected row-count reasonableness.
# -------------------------------------------------------------------
if staged_row_count == 0:
    summary["checks"]["reasonable_row_count"] = "FAIL"
    errors.append("Staged row count is zero")
else:
    history = recent_row_counts(int(config.get("recent_runs_to_compare", 4)))
    if len(history) >= 3:
        baseline = statistics.median(history)
        variance = abs(staged_row_count - baseline) / baseline if baseline else 0
        allowed = float(config.get("row_count_variance_pct", 40)) / 100.0
        summary["recent_row_count_median"] = baseline
        summary["row_count_variance"] = variance
        if variance > allowed:
            summary["checks"]["reasonable_row_count"] = "FAIL"
            errors.append("Staged row count is abnormally different from recent runs")
        else:
            summary["checks"]["reasonable_row_count"] = "PASS"
    else:
        summary["checks"]["reasonable_row_count"] = "PASS_NOT_ENOUGH_HISTORY"

# -------------------------------------------------------------------
# 4. Glue Data Quality:
#    required non-null columns, ranges, weeks_since_launch,
#    and is_trending_8wk allowed domain.
# -------------------------------------------------------------------
ruleset_response = glue.get_data_quality_ruleset(
    Name=args["dq_ruleset_name"]
)
ruleset = ruleset_response["Ruleset"]

dq_results = EvaluateDataQuality.apply(
    frame=DynamicFrame.fromDF(staged_df, glue_context, "staged_trend_features"),
    ruleset=ruleset,
    publishing_options={
        "dataQualityEvaluationContext": "reference-staged-trend-features",
        "enableDataQualityCloudWatchMetrics": True,
        "enableDataQualityResultsPublishing": False
    }
)

dq_df = dq_results.toDF()
failed_rules = (
    dq_df
    .filter(F.col("Outcome") != F.lit("Passed"))
    .select("Rule", "Outcome", "FailureReason")
    .collect()
)

summary["dq_rule_results"] = [
    {
        "rule": row["Rule"],
        "outcome": row["Outcome"],
        "failure_reason": row["FailureReason"]
    }
    for row in failed_rules
]

if failed_rules:
    summary["checks"]["glue_data_quality"] = "FAIL"
    errors.append("One or more Glue Data Quality rules failed")
else:
    summary["checks"]["glue_data_quality"] = "PASS"

# -------------------------------------------------------------------
# 5. Athena calculation/reconciliation/business-rule validation.
#    Every SQL file must return one value named failure_count.
#    0 = PASS; anything else = FAIL.
# -------------------------------------------------------------------
sql_keys = list_keys(args["sql_prefix"], ".sql")

for sql_key in sql_keys:
    query_text = read_text(sql_key)

    started = athena.start_query_execution(
        QueryString=query_text,
        QueryExecutionContext={
            "Database": args["athena_database"]
        },
        WorkGroup=args["athena_workgroup"]
    )

    query_execution_id = started["QueryExecutionId"]
    state, execution = wait_for_athena(query_execution_id)

    check_result = {
        "sql_key": sql_key,
        "query_execution_id": query_execution_id,
        "state": state
    }

    if state != "SUCCEEDED":
        reason = execution["QueryExecution"]["Status"].get(
            "StateChangeReason",
            "Unknown Athena failure"
        )
        check_result["reason"] = reason
        summary["athena_checks"].append(check_result)
        errors.append("Athena check could not execute: " + sql_key)
        continue

    result = athena.get_query_results(
        QueryExecutionId=query_execution_id,
        MaxResults=10
    )

    rows = result["ResultSet"].get("Rows", [])
    if len(rows) < 2 or not rows[1].get("Data"):
        check_result["failure_count"] = None
        summary["athena_checks"].append(check_result)
        errors.append("Athena check did not return failure_count: " + sql_key)
        continue

    failure_count = int(
        float(rows[1]["Data"][0].get("VarCharValue", "0"))
    )

    check_result["failure_count"] = failure_count
    summary["athena_checks"].append(check_result)

    if failure_count != 0:
        errors.append(
            "Athena validation failed: "
            + sql_key
            + " failure_count="
            + str(failure_count)
        )

summary["checks"]["athena_validation"] = "FAIL" if any(
    x.get("failure_count", 0) not in (0, None)
    or x.get("state") != "SUCCEEDED"
    for x in summary["athena_checks"]
) else "PASS"

# -------------------------------------------------------------------
# 6. Persist audit output for future row-count comparisons.
# -------------------------------------------------------------------
summary["status"] = "FAIL" if errors else "PASS"
summary["errors"] = errors

summary_key = (
    audit_prefix
    + "/runs/week_end="
    + processing_week_end
    + "/validation-summary.json"
)

s3.put_object(
    Bucket=bucket,
    Key=summary_key,
    Body=json.dumps(summary, indent=2).encode("utf-8"),
    ContentType="application/json"
)

count_key = (
    audit_prefix
    + "/counts/week_end="
    + processing_week_end
    + ".json"
)

s3.put_object(
    Bucket=bucket,
    Key=count_key,
    Body=json.dumps(
        {
            "processing_week_end": processing_week_end,
            "row_count": staged_row_count,
            "validation_status": summary["status"]
        },
        indent=2
    ).encode("utf-8"),
    ContentType="application/json"
)

# -------------------------------------------------------------------
# 7. Gate the pipeline.
# -------------------------------------------------------------------
if errors:
    raise RuntimeError(
        "Comprehensive staged-data validation failed: "
        + json.dumps(errors)
    )

job.commit()
