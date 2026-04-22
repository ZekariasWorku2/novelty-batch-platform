from datetime import datetime, timedelta
import time
import boto3

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator

AWS_REGION = "us-east-1"
GLUE_RAW_JOB = "novelty-np-trend-raw-ingest"
GLUE_TRANSFORM_JOB = "novelty-np-trend-transform"
ATHENA_DB = "novelty_ml_np"
ATHENA_WG = "novelty_np_athena_wg"
REDSHIFT_WORKGROUP = "novelty-np-rs-wg"
REDSHIFT_DB = "noveltyml"

def wait_for_glue_job(job_name, **context):
    glue = boto3.client("glue", region_name=AWS_REGION)
    run = glue.start_job_run(JobName=job_name)
    run_id = run["JobRunId"]

    while True:
        state = glue.get_job_run(JobName=job_name, RunId=run_id)["JobRun"]["JobRunState"]
        if state in ["SUCCEEDED"]:
            return
        if state in ["FAILED", "STOPPED", "TIMEOUT"]:
            raise Exception(f"Glue job {job_name} ended in state {state}")
        time.sleep(30)

def run_athena_validation(**context):
    athena = boto3.client("athena", region_name=AWS_REGION)
    query = """
    SELECT COUNT(*) AS row_count
    FROM mart_new_product_trend_features
    """
    resp = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": ATHENA_DB},
        WorkGroup=ATHENA_WG,
    )
    qid = resp["QueryExecutionId"]

    while True:
        status = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]["State"]
        if status == "SUCCEEDED":
            return
        if status in ["FAILED", "CANCELLED"]:
            raise Exception(f"Athena validation failed: {status}")
        time.sleep(10)

def publish_redshift(**context):
    redshift = boto3.client("redshift-data", region_name=AWS_REGION)
    sql = """
    truncate table mart.new_product_launch_cohort;
    copy mart.new_product_launch_cohort
    from 's3://REPLACE_ME_BUCKET/curated/new_product_trend/launch_cohort/'
    iam_role default
    format as parquet;

    truncate table mart.new_product_trend_features;
    copy mart.new_product_trend_features
    from 's3://REPLACE_ME_BUCKET/curated/new_product_trend/features/'
    iam_role default
    format as parquet;
    """
    resp = redshift.execute_statement(
        WorkgroupName=REDSHIFT_WORKGROUP,
        Database=REDSHIFT_DB,
        Sql=sql,
    )
    stmt_id = resp["Id"]

    while True:
        desc = redshift.describe_statement(Id=stmt_id)
        status = desc["Status"]
        if status == "FINISHED":
            return
        if status in ["FAILED", "ABORTED"]:
            raise Exception(f"Redshift publish failed: {status}")
        time.sleep(10)

default_args = {
    "owner": "novelty-data-eng",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="np_trend_batch_platform",
    default_args=default_args,
    description="Batch ML feature pipeline for new product trend prediction",
    start_date=datetime(2026, 1, 1),
    schedule="0 2 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["novelty", "batch", "ml", "mwaa"],
) as dag:

    start = EmptyOperator(task_id="start")

    raw_ingest = PythonOperator(
        task_id="raw_ingest_glue",
        python_callable=wait_for_glue_job,
        op_kwargs={"job_name": GLUE_RAW_JOB},
    )

    transform = PythonOperator(
        task_id="transform_glue",
        python_callable=wait_for_glue_job,
        op_kwargs={"job_name": GLUE_TRANSFORM_JOB},
    )

    validate = PythonOperator(
        task_id="athena_validation",
        python_callable=run_athena_validation,
    )

    publish = PythonOperator(
        task_id="publish_redshift",
        python_callable=publish_redshift,
    )

    end = EmptyOperator(task_id="end")

    start >> raw_ingest >> transform >> validate >> publish >> end
