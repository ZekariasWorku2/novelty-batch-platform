import sys, json, time, boto3
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, [
    "bucket",
    "processing_week_end",
    "redshift_database",
    "redshift_workgroup_name",
    "redshift_iam_role_arn"
])

bucket = args["bucket"]
week_end = args["processing_week_end"]
database = args["redshift_database"]
workgroup = args["redshift_workgroup_name"]
iam_role = args["redshift_iam_role_arn"]

redshift = boto3.client("redshift-data")
s3 = boto3.client("s3")

schema = "product_trends"
stage_table = f"{schema}.trend_features_load"
final_table = f"{schema}.trend_features"

def execute(sql):
    started = redshift.execute_statement(
        WorkgroupName=workgroup,
        Database=database,
        Sql=sql
    )
    statement_id = started["Id"]
    while True:
        status = redshift.describe_statement(Id=statement_id)
        state = status["Status"]
        if state == "FINISHED":
            return statement_id
        if state in ("FAILED", "ABORTED"):
            raise RuntimeError(status.get("Error", "Redshift statement failed"))
        time.sleep(2)

create_sql = f"""
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE IF NOT EXISTS {final_table} (
    StockItemID INTEGER NOT NULL,
    StockItemName VARCHAR(255),
    SupplierID INTEGER,
    Brand VARCHAR(255),
    Size VARCHAR(100),
    LeadTimeDays INTEGER,
    QuantityPerOuter INTEGER,
    IsChillerStock BOOLEAN,
    BaseUnitPrice DOUBLE PRECISION,
    RecommendedRetailPrice DOUBLE PRECISION,
    PrimaryStockGroupName VARCHAR(255),
    QuantityOnHand INTEGER,
    ReorderLevel INTEGER,
    TargetStockLevel INTEGER,
    launch_date DATE,
    launch_quarter VARCHAR(20),
    as_of_week_end_date DATE NOT NULL,
    weeks_since_launch INTEGER,
    units_sold_week BIGINT,
    sales_amount_week DOUBLE PRECISION,
    profit_week DOUBLE PRECISION,
    distinct_customers_week BIGINT,
    avg_unit_price_week DOUBLE PRECISION,
    cumulative_units_to_date BIGINT,
    cumulative_sales_to_date DOUBLE PRECISION,
    cumulative_customers_proxy BIGINT,
    prev_week_units BIGINT,
    prev_week_sales DOUBLE PRECISION,
    wow_units_growth_rate DOUBLE PRECISION,
    first_8wk_units BIGINT,
    first_8wk_sales DOUBLE PRECISION,
    first_8wk_customers BIGINT,
    is_trending_8wk INTEGER,
    as_of_year INTEGER,
    as_of_month VARCHAR(2)
);

CREATE TABLE IF NOT EXISTS {stage_table} (LIKE {final_table});
"""

truncate_sql = f"TRUNCATE TABLE {stage_table};"

# Reference design: COPY from the validated curated Parquet dataset.
# In production, point this at the exact successful batch prefix or manifest.
copy_sql = f"""
COPY {stage_table}
FROM 's3://{bucket}/curated/new_product_trend/features/'
IAM_ROLE '{iam_role}'
FORMAT AS PARQUET;
"""

merge_sql = f"""
BEGIN;

DELETE FROM {final_table}
WHERE as_of_week_end_date = DATE '{week_end}';

INSERT INTO {final_table}
SELECT *
FROM {stage_table}
WHERE as_of_week_end_date = DATE '{week_end}';

END;
"""

statement_ids = {}
statement_ids["create_objects"] = execute(create_sql)
statement_ids["truncate_stage"] = execute(truncate_sql)
statement_ids["copy_curated"] = execute(copy_sql)
statement_ids["publish_week"] = execute(merge_sql)

summary = {
    "processing_week_end": week_end,
    "database": database,
    "workgroup": workgroup,
    "stage_table": stage_table,
    "final_table": final_table,
    "status": "SUCCEEDED",
    "statement_ids": statement_ids
}
s3.put_object(
    Bucket=bucket,
    Key=f"reference/redshift-load/audit/week_end={week_end}/load-summary.json",
    Body=json.dumps(summary, indent=2).encode("utf-8"),
    ContentType="application/json"
)
print(json.dumps(summary))
