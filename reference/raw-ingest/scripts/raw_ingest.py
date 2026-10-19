"""Weekly SQL Server -> raw S3 extraction. NEW implementation, not present in original AWS account.

Requires a read-only SQL Server login stored in Secrets Manager and a VPC Glue JDBC
connection. Writes one gzipped CSV dataset per source and an exact ingestion
manifest consumed by the recovered raw_validation.py.
"""
import json
import re
import sys
import uuid
from collections import OrderedDict

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F

REQUIRED = [
    "JOB_NAME", "raw_bucket", "processing_week_start", "processing_week_end",
    "manifest_key", "source_tables_key", "secret_arn", "jdbc_url",
]
args = getResolvedOptions(sys.argv, REQUIRED)
for k in ("processing_week_start", "processing_week_end"):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args[k]):
        raise ValueError("Date must be YYYY-MM-DD: " + k)
if not args["secret_arn"] or not args["jdbc_url"]:
    raise ValueError("Configure Secrets Manager ARN and JDBC URL before running ingestion")

glue_context = GlueContext(SparkContext.getOrCreate())
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)
s3 = boto3.client("s3")
sm = boto3.client("secretsmanager")
bucket = args["raw_bucket"]
start = args["processing_week_start"]
end = args["processing_week_end"]
secret = json.loads(sm.get_secret_value(SecretId=args["secret_arn"])["SecretString"])
user = secret.get("username") or secret.get("user")
password = secret.get("password")
if not user or not password:
    raise ValueError("SQL Server secret must contain username and password")
config = json.loads(s3.get_object(Bucket=bucket, Key=args["source_tables_key"])["Body"].read())
manifest = {
    "run_id": uuid.uuid4().hex,
    "processing_week_start": start,
    "processing_week_end_exclusive": end,
    "tables": {},
}
for table, spec in config["tables"].items():
    sql = spec["query"].replace("{week_start}", start).replace("{week_end}", end)
    if "{" in sql or "}" in sql:
        raise ValueError("Unresolved SQL template placeholder in " + table)
    df = (spark.read.format("jdbc")
          .option("url", args["jdbc_url"])
          .option("dbtable", "(" + sql + ") AS source_rows")
          .option("user", user)
          .option("password", password)
          .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
          .option("fetchsize", "10000").load())
    row_count = df.count()
    if row_count == 0:
        raise RuntimeError("Refusing empty source extract: " + table)
    daily_counts = OrderedDict()
    date_col = spec.get("date_column")
    if date_col:
        rows = (df.groupBy(F.to_date(F.col(date_col)).alias("dt"))
                .count().collect())
        daily_counts = OrderedDict(sorted(
            (str(row["dt"]), int(row["count"])) for row in rows if row["dt"] is not None
        ))
    prefix = "raw/wwi/{}/week_start={}/".format(table, start)
    path = "s3://{}/{}".format(bucket, prefix)
    (df.write.mode("overwrite").option("header", "true")
       .option("compression", "gzip").csv(path))
    listed = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    files = sorted(
        o["Key"] for o in listed.get("Contents", [])
        if o["Key"].rsplit("/", 1)[-1].startswith("part-") and o["Key"].endswith(".csv.gz")
    )
    if not files:
        raise RuntimeError("Spark wrote no raw data files for " + table)
    manifest["tables"][table] = {
        "prefix": prefix,
        "expected_files": files,
        "source_row_count": row_count,
        "source_schema": {field.name: field.dataType.simpleString() for field in df.schema.fields},
        "date_column": date_col,
        "daily_counts": daily_counts,
        "delimiter": ",",
    }
s3.put_object(
    Bucket=bucket, Key=args["manifest_key"],
    Body=json.dumps(manifest, indent=2).encode("utf-8"),
    ContentType="application/json",
)
job.commit()
