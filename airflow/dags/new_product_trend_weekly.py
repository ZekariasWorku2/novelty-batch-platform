import json
from datetime import timedelta
import boto3
import pendulum

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator

REGION = "us-east-1"
BUCKET = "novelty-margin-lakehouse-672350744457"
FAILURE_TOPIC = "arn:aws:sns:us-east-1:672350744457:new-product-trend-airflow-failures"
TZ = pendulum.timezone("America/New_York")

def notify_failure(context):
    ti = context.get("task_instance")
    dr = context.get("dag_run")
    boto3.client("sns", region_name=REGION).publish(
        TopicArn=FAILURE_TOPIC,
        Subject="New Product Trend Airflow task failure",
        Message=json.dumps({
            "dag_id": getattr(ti, "dag_id", None),
            "task_id": getattr(ti, "task_id", None),
            "run_id": getattr(dr, "run_id", None),
            "exception": str(context.get("exception")),
            "log_url": getattr(ti, "log_url", None),
        }, indent=2, default=str),
    )

def determine_processing_window(**context):
    end = context["data_interval_end"].in_timezone(TZ).start_of("day")
    start = end.subtract(days=7)
    last_day = end.subtract(days=1)
    week_end = end.to_date_string()
    return {
        "processing_week_start": start.to_date_string(),
        "processing_week_end": week_end,
        "manifest_key": f"reference/raw-validation/manifests/processing_week_end={week_end}/ingestion_manifest.json",
        "staging_prefix": f"staging/new_product_trend/features/as_of_year={last_day.year}/as_of_month={last_day.month:02d}/",
        "curated_prefix": f"curated/new_product_trend/features/as_of_year={last_day.year}/as_of_month={last_day.month:02d}/",
    }

def record_pipeline_audit(**context):
    dr = context["dag_run"]
    ti = context["task_instance"]
    w = ti.xcom_pull(task_ids="determine_processing_window") or {}
    safe_run = dr.run_id.replace(":", "_").replace("/", "_")
    key = (
        "audit/new_product_trend/"
        f"processing_week_end={w.get('processing_week_end','unknown')}/"
        f"run_id={safe_run}/pipeline-summary.json"
    )
    body = {
        "dag_id": dr.dag_id,
        "run_id": dr.run_id,
        "processing_week_start": w.get("processing_week_start"),
        "processing_week_end": w.get("processing_week_end"),
        "status": "SUCCEEDED",
    }
    boto3.client("s3", region_name=REGION).put_object(
        Bucket=BUCKET, Key=key,
        Body=json.dumps(body, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

def xp(key):
    return "{{ ti.xcom_pull(task_ids='determine_processing_window')['" + key + "'] }}"

def glue_task(task_id, job_name, script_args):
    return GlueJobOperator(
        task_id=task_id,
        job_name=job_name,
        aws_conn_id="aws_default",
        wait_for_completion=True,
        stop_job_run_on_kill=True,
        job_poll_interval=30,
        script_args=script_args,
    )

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notify_failure,
}

with DAG(
    dag_id="new_product_trend_weekly",
    description="Weekly orchestration for the New Product Trend feature pipeline",
    schedule="0 2 * * 0",
    start_date=pendulum.datetime(2026, 1, 4, 2, 0, tz=TZ),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["new-product-trend", "data-engineering", "weekly"],
    is_paused_upon_creation=True,
) as dag:
    start = EmptyOperator(task_id="start")
    window = PythonOperator(
        task_id="determine_processing_window",
        python_callable=determine_processing_window,
    )

    # Intended production integration points. These two Glue job definitions are
    # intentionally absent in the study account, adding a safety stop if triggered.
    extract = glue_task("extract_source_to_raw_s3", "reference-raw-ingest", {
        "--raw_bucket": BUCKET,
        "--processing_week_start": xp("processing_week_start"),
        "--processing_week_end": xp("processing_week_end"),
        "--manifest_key": xp("manifest_key"),
    })

    raw_validate = glue_task("validate_raw_data", "reference-raw-data-validation", {
        "--raw_bucket": BUCKET,
        "--processing_week_start": xp("processing_week_start"),
        "--processing_week_end": xp("processing_week_end"),
        "--config_key": "reference/raw-validation/config/expected_validation_config.json",
        "--manifest_key": xp("manifest_key"),
        "--audit_prefix": "reference/raw-validation/audit/",
    })

    transform = glue_task("transform_to_staging", "reference-transform-to-staging", {
        "--bucket": BUCKET,
        "--processing_week_start": xp("processing_week_start"),
        "--processing_week_end": xp("processing_week_end"),
        "--staging_prefix": xp("staging_prefix"),
    })

    staged_validate = glue_task("validate_staged_data", "reference-staged-data-validation", {
        "--bucket": BUCKET,
        "--staging_prefix": xp("staging_prefix"),
        "--processing_week_end": xp("processing_week_end"),
        "--config_key": "reference/staged-validation/config/staged_validation_config.json",
        "--sql_prefix": "reference/staged-validation/sql/",
        "--audit_prefix": "reference/staged-validation/audit/",
        "--dq_ruleset_name": "staged_trend_features_structural_rules",
        "--athena_database": "reference_new_product_trend",
        "--athena_workgroup": "reference-staged-validation",
    })

    promote = glue_task("promote_validated_to_curated", "reference-promote-staged-data", {
        "--bucket": BUCKET,
        "--staging_prefix": xp("staging_prefix"),
        "--curated_prefix": xp("curated_prefix"),
    })

    publish = glue_task("publish_curated_to_redshift", "reference-curated-to-redshift-load", {
        "--bucket": BUCKET,
        "--processing_week_end": xp("processing_week_end"),
        "--redshift_database": "analytics",
        "--redshift_workgroup_name": "reference-new-product-trend-wg",
        "--redshift_iam_role_arn": "arn:aws:iam::672350744457:role/ReferenceRedshiftCuratedLoadRole",
    })

    smoke = glue_task("post_load_smoke_validation", "reference-redshift-postload-smoke-validation", {
        "--bucket": BUCKET,
        "--processing_week_end": xp("processing_week_end"),
        "--redshift_database": "analytics",
        "--redshift_table": "product_trends.trend_features",
        "--redshift_workgroup_name": "reference-new-product-trend-wg",
        "--athena_database": "reference_new_product_trend",
        "--athena_workgroup": "reference-redshift-smoke-validation",
        "--curated_table": "curated_trend_features_reference",
        "--audit_prefix": "reference/redshift-smoke-validation/audit/",
    })

    audit = PythonOperator(
        task_id="record_pipeline_audit",
        python_callable=record_pipeline_audit,
    )
    end = EmptyOperator(task_id="end")

    start >> window >> extract >> raw_validate >> transform >> staged_validate >> promote >> publish >> smoke >> audit >> end
