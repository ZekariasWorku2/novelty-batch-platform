"""Dependency-free, read-only repository contract validation."""
import ast
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DAG = ROOT / "airflow/dags/new_product_trend_weekly.py"
EXPECTED_TASKS = [
    "start", "determine_processing_window", "extract_source_to_raw_s3",
    "validate_raw_data", "transform_to_staging", "validate_staged_data",
    "promote_validated_to_curated", "publish_curated_to_redshift",
    "post_load_smoke_validation", "record_pipeline_audit", "end",
]
JOBS = {
    "reference-raw-ingest": "reference/raw-ingest/scripts/raw_ingest.py",
    "reference-raw-data-validation": "reference/raw-validation/scripts/raw_validation.py",
    "reference-transform-to-staging": "reference/transform/scripts/transform_to_staging.py",
    "reference-staged-data-validation": "reference/staged-validation/scripts/staged_validation.py",
    "reference-promote-staged-data": "reference/staged-validation/scripts/promote_staged_to_curated.py",
    "reference-curated-to-redshift-load": "reference/redshift-load/scripts/curated_to_redshift_load.py",
    "reference-redshift-postload-smoke-validation":
        "reference/redshift-smoke-validation/scripts/redshift_postload_smoke_validation.py",
}

def verify():
    problems = []
    source = DAG.read_text()
    ast.parse(source)
    if 'dag_id="new_product_trend_weekly"' not in source:
        problems.append("Incorrect DAG id")
    if 'is_paused_upon_creation=True' not in source:
        problems.append("DAG must initially be paused")
    for task in EXPECTED_TASKS:
        if task not in source:
            problems.append("Missing DAG task: " + task)
    for name, relative in JOBS.items():
        file = ROOT / relative
        if not file.is_file():
            problems.append("Missing Glue job script: " + relative)
        else:
            ast.parse(file.read_text())
        if name not in source:
            problems.append("DAG missing job reference: " + name)
    specification = json.loads(
        (ROOT / "terraform/recovered/glue_jobs.json").read_text()
    )
    actual = {job["Name"] for job in specification["jobs"]}
    if actual != set(JOBS):
        problems.append("Terraform Glue job list mismatches DAG")
    for file in (ROOT / "reference").rglob("*.py"):
        ast.parse(file.read_text())
    for file in (ROOT / "reference").rglob("*.json"):
        json.loads(file.read_text())
    for file in (ROOT / "stepfunctions").glob("*.json"):
        doc = json.loads(file.read_text())
        if not {"StartAt", "States"} <= doc.keys():
            problems.append("Invalid Step Functions document: " + str(file))
    sqls = list((ROOT / "reference").rglob("*.sql"))
    if len(sqls) != 23:
        problems.append("Expected 23 recovered SQL scripts, got {}".format(len(sqls)))
    for file in sqls:
        if not file.read_text().strip():
            problems.append("Empty SQL file: " + str(file))
    tfdir = ROOT / "terraform"
    required = ("glue.tf", "iam.tf", "network.tf", "mwaa.tf", "redshift.tf",
                "storage.tf", "cicd.tf", "catalog.tf", "workflows.tf",
                "observability.tf", "variables.tf", "versions.tf")
    for name in required:
        if not (tfdir / name).exists():
            problems.append("Missing Terraform module: " + name)
    for relative in ("reference/raw-ingest/config/source_tables.json",
                     "reference/staged-validation/config/staged_validation_config.json"):
        doc = json.loads((ROOT / relative).read_text())
        if not doc:
            problems.append("Empty configuration: " + relative)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        raise SystemExit(1)
    print("PASS: {} Glue jobs, {} ordered task names, {} SQL scripts, IaC and configs".format(
        len(JOBS), len(EXPECTED_TASKS), len(sqls)))

if __name__ == "__main__":
    verify()
