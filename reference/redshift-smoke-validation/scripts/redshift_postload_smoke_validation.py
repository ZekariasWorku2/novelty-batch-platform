import sys
import json
import time
import boto3
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "bucket",
    "processing_week_end",
    "redshift_database",
    "redshift_table",
    "redshift_workgroup_name",
    "athena_database",
    "athena_workgroup",
    "curated_table",
    "audit_prefix"
])

bucket = args["bucket"]
week_end = args["processing_week_end"]
redshift_database = args["redshift_database"]
redshift_table = args["redshift_table"]
redshift_workgroup = args["redshift_workgroup_name"]
athena_database = args["athena_database"]
athena_workgroup = args["athena_workgroup"]
curated_table = args["curated_table"]
audit_prefix = args["audit_prefix"].strip("/")
tolerance = 0.01

s3 = boto3.client("s3")
athena = boto3.client("athena")
redshift_data = boto3.client("redshift-data")

def wait_athena(query_execution_id):
    while True:
        info = athena.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        state = info["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return state, info
        time.sleep(1)

def run_athena(sql):
    qid = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": athena_database},
        WorkGroup=athena_workgroup
    )["QueryExecutionId"]

    state, info = wait_athena(qid)
    if state != "SUCCEEDED":
        raise RuntimeError(
            "Athena baseline query failed: "
            + info["QueryExecution"]["Status"].get(
                "StateChangeReason", state
            )
        )

    result = athena.get_query_results(
        QueryExecutionId=qid,
        MaxResults=10
    )
    rows = result["ResultSet"].get("Rows", [])
    if len(rows) < 2:
        raise RuntimeError(
            "Athena baseline query returned no data row"
        )

    headers = [
        item.get("VarCharValue")
        for item in rows[0].get("Data", [])
    ]
    values = [
        item.get("VarCharValue")
        for item in rows[1].get("Data", [])
    ]
    return dict(zip(headers, values)), qid

def wait_redshift(statement_id):
    while True:
        info = redshift_data.describe_statement(
            Id=statement_id
        )
        if info["Status"] in (
            "FINISHED",
            "FAILED",
            "ABORTED"
        ):
            return info
        time.sleep(1)

def field_value(field):
    if field.get("isNull"):
        return None
    for key in (
        "longValue",
        "doubleValue",
        "stringValue",
        "booleanValue"
    ):
        if key in field:
            return field[key]
    return None

def run_redshift(sql):
    statement_id = redshift_data.execute_statement(
        WorkgroupName=redshift_workgroup,
        Database=redshift_database,
        Sql=sql
    )["Id"]

    info = wait_redshift(statement_id)
    if info["Status"] != "FINISHED":
        raise RuntimeError(
            "Redshift statement failed: "
            + info.get("Error", info["Status"])
        )

    result = redshift_data.get_statement_result(
        Id=statement_id
    )

    columns = [
        x["name"]
        for x in result.get("ColumnMetadata", [])
    ]

    output = []
    for record in result.get("Records", []):
        output.append(
            dict(
                zip(
                    columns,
                    [field_value(x) for x in record]
                )
            )
        )

    return output, statement_id

def numeric(value):
    if value is None:
        return 0.0
    return float(value)

summary = {
    "processing_week_end": week_end,
    "redshift_workgroup_name": redshift_workgroup,
    "redshift_database": redshift_database,
    "redshift_table": redshift_table,
    "checks": {},
    "statement_ids": {}
}
failures = []

# ---------------------------------------------------------------
# 1. Table can be queried.
# ---------------------------------------------------------------
_, statement_id = run_redshift(
    "SELECT 1 FROM "
    + redshift_table
    + " LIMIT 1"
)
summary["statement_ids"]["table_queryable"] = statement_id
summary["checks"]["table_queryable"] = "PASS"

# ---------------------------------------------------------------
# 2. Curated/Athena baseline.
# ---------------------------------------------------------------
curated_sql = """
SELECT
    COUNT(*) AS row_count,
    COALESCE(SUM(units_sold_week),0) AS units_total,
    COALESCE(SUM(sales_amount_week),0) AS sales_total,
    COALESCE(SUM(profit_week),0) AS profit_total
FROM {database}.{table}
WHERE as_of_week_end_date = DATE '{week_end}'
""".format(
    database=athena_database,
    table=curated_table,
    week_end=week_end
)

curated, athena_qid = run_athena(curated_sql)
summary["athena_query_execution_id"] = athena_qid
summary["curated_metrics"] = curated

# ---------------------------------------------------------------
# 3. Redshift row count and key totals.
# ---------------------------------------------------------------
redshift_metrics_sql = """
SELECT
    COUNT(*) AS row_count,
    COALESCE(SUM(units_sold_week),0) AS units_total,
    COALESCE(SUM(sales_amount_week),0) AS sales_total,
    COALESCE(SUM(profit_week),0) AS profit_total
FROM {table}
WHERE as_of_week_end_date = DATE '{week_end}'
""".format(
    table=redshift_table,
    week_end=week_end
)

rows, statement_id = run_redshift(
    redshift_metrics_sql
)
summary["statement_ids"]["week_metrics"] = statement_id
redshift_metrics = rows[0] if rows else {}
summary["redshift_metrics"] = redshift_metrics

redshift_count = int(
    numeric(redshift_metrics.get("row_count"))
)
curated_count = int(
    numeric(curated.get("row_count"))
)

# Expected processing week exists.
if redshift_count > 0:
    summary["checks"]["expected_processing_week_exists"] = "PASS"
else:
    summary["checks"]["expected_processing_week_exists"] = "FAIL"
    failures.append(
        "Expected processing week does not exist in Redshift"
    )

# Row counts match curated/Athena.
if redshift_count == curated_count:
    summary["checks"]["row_counts_match_curated"] = "PASS"
else:
    summary["checks"]["row_counts_match_curated"] = "FAIL"
    failures.append(
        "Redshift row count does not match curated/Athena"
    )

# ---------------------------------------------------------------
# 4. No unexpected duplicate Product + Week rows.
# ---------------------------------------------------------------
duplicate_sql = """
SELECT COUNT(*) AS failure_count
FROM (
    SELECT StockItemID, as_of_week_end_date, COUNT(*) AS cnt
    FROM {table}
    WHERE as_of_week_end_date = DATE '{week_end}'
    GROUP BY StockItemID, as_of_week_end_date
    HAVING COUNT(*) > 1
) d
""".format(
    table=redshift_table,
    week_end=week_end
)

rows, statement_id = run_redshift(duplicate_sql)
summary["statement_ids"]["duplicates"] = statement_id

duplicate_count = int(
    numeric(
        rows[0].get("failure_count")
        if rows else 0
    )
)

if duplicate_count == 0:
    summary["checks"]["no_unexpected_duplicates"] = "PASS"
else:
    summary["checks"]["no_unexpected_duplicates"] = "FAIL"
    failures.append(
        "Unexpected duplicate Product + Week rows exist"
    )

# ---------------------------------------------------------------
# 5. Required columns are populated.
# ---------------------------------------------------------------
required_sql = """
SELECT COUNT(*) AS failure_count
FROM {table}
WHERE as_of_week_end_date = DATE '{week_end}'
  AND (
      StockItemID IS NULL
      OR as_of_week_end_date IS NULL
      OR weeks_since_launch IS NULL
      OR units_sold_week IS NULL
      OR sales_amount_week IS NULL
  )
""".format(
    table=redshift_table,
    week_end=week_end
)

rows, statement_id = run_redshift(required_sql)
summary["statement_ids"]["required_columns"] = statement_id

null_count = int(
    numeric(
        rows[0].get("failure_count")
        if rows else 0
    )
)

if null_count == 0:
    summary["checks"]["required_columns_populated"] = "PASS"
else:
    summary["checks"]["required_columns_populated"] = "FAIL"
    failures.append(
        "Required Redshift columns contain NULL values"
    )

# ---------------------------------------------------------------
# 6. Key totals match curated data.
# ---------------------------------------------------------------
metric_failures = {}

for metric, allowed_delta in [
    ("units_total", 0.0),
    ("sales_total", tolerance),
    ("profit_total", tolerance)
]:
    rs_value = numeric(
        redshift_metrics.get(metric)
    )
    curated_value = numeric(
        curated.get(metric)
    )

    delta = abs(
        rs_value - curated_value
    )

    if delta > allowed_delta:
        metric_failures[metric] = {
            "redshift": rs_value,
            "curated": curated_value,
            "delta": delta,
            "allowed_delta": allowed_delta
        }

if metric_failures:
    summary["checks"]["key_totals_match_curated"] = "FAIL"
    summary["metric_failures"] = metric_failures
    failures.append(
        "Key totals do not match curated/Athena"
    )
else:
    summary["checks"]["key_totals_match_curated"] = "PASS"

# ---------------------------------------------------------------
# 7. Persist audit result and gate pipeline.
# ---------------------------------------------------------------
summary["status"] = (
    "FAIL"
    if failures
    else "PASS"
)
summary["failures"] = failures

audit_key = (
    audit_prefix
    + "/week_end="
    + week_end
    + "/validation-summary.json"
)

s3.put_object(
    Bucket=bucket,
    Key=audit_key,
    Body=json.dumps(
        summary,
        indent=2,
        default=str
    ).encode("utf-8"),
    ContentType="application/json"
)

if failures:
    raise RuntimeError(
        "Redshift post-load smoke validation failed: "
        + json.dumps(failures)
    )

print(json.dumps(summary, indent=2, default=str))
