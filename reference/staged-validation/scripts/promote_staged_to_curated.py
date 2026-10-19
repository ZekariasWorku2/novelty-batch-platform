import sys
import json
import boto3

from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext

args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "bucket",
    "staging_prefix",
    "curated_prefix"
])

sc = SparkContext()
glue_context = GlueContext(sc)
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

s3 = boto3.client("s3")

bucket = args["bucket"]
staging_prefix = args["staging_prefix"].strip("/") + "/"
curated_prefix = args["curated_prefix"].strip("/") + "/"

paginator = s3.get_paginator("list_objects_v2")
source_objects = []

for page in paginator.paginate(
    Bucket=bucket,
    Prefix=staging_prefix
):
    for item in page.get("Contents", []):
        key = item["Key"]
        if item.get("Size", 0) == 0:
            continue
        if key.split("/")[-1].startswith("."):
            continue
        source_objects.append(key)

if not source_objects:
    raise RuntimeError(
        "Promotion aborted: no staged objects were found under "
        + staging_prefix
    )

copied = []

for source_key in source_objects:
    relative_key = source_key[len(staging_prefix):]
    target_key = curated_prefix + relative_key

    s3.copy_object(
        Bucket=bucket,
        Key=target_key,
        CopySource={
            "Bucket": bucket,
            "Key": source_key
        }
    )

    copied.append({
        "source": source_key,
        "target": target_key
    })

manifest = {
    "source_prefix": staging_prefix,
    "curated_prefix": curated_prefix,
    "objects_promoted": len(copied),
    "objects": copied
}

s3.put_object(
    Bucket=bucket,
    Key=curated_prefix + "_PROMOTION_MANIFEST.json",
    Body=json.dumps(manifest, indent=2).encode("utf-8"),
    ContentType="application/json"
)

s3.put_object(
    Bucket=bucket,
    Key=curated_prefix + "_PROMOTED_SUCCESS",
    Body=b""
)

job.commit()
