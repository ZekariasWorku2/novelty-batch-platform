"""Contract tests avoid real Glue/Redshift execution or AWS credentials."""
import ast
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ContractTests(unittest.TestCase):
    def test_all_seven_glue_scripts_are_valid_python(self):
        jobs = json.loads((ROOT / "terraform/recovered/glue_jobs.json").read_text())["jobs"]
        self.assertEqual(len(jobs), 7)
        for job in jobs:
            location = job["Command"]["ScriptLocation"]
            path = location.split("/reference/", 1)[-1]
            file = ROOT / "reference" / path
            self.assertTrue(file.is_file(), str(file))
            ast.parse(file.read_text())

    def test_dag_is_paused_and_weekly(self):
        dag = (ROOT / "airflow/dags/new_product_trend_weekly.py").read_text()
        self.assertIn('schedule="0 2 * * 0"', dag)
        self.assertIn("is_paused_upon_creation=True", dag)
        self.assertIn("extract >> raw_validate >> transform", dag)
        ast.parse(dag)

    def test_extract_uses_secret_manager_and_writes_manifest(self):
        code = (ROOT / "reference/raw-ingest/scripts/raw_ingest.py").read_text()
        self.assertIn("get_secret_value", code)
        self.assertIn('"source_row_count"', code)
        self.assertIn('"expected_files"', code)
        self.assertIn('"daily_counts"', code)

    def test_transform_has_leakage_safe_labels(self):
        code = (ROOT / "reference/transform/scripts/transform_to_staging.py").read_text()
        self.assertIn('F.col("weeks_since_launch") == 7', code)
        self.assertIn('"is_trending_8wk"', code)
        self.assertIn('"wow_units_growth_rate"', code)
        self.assertIn('"cumulative_units_to_date"', code)

    def test_source_config_matches_expected_validation_tables(self):
        spec = json.loads((ROOT / "reference/raw-ingest/config/source_tables.json").read_text())
        config = json.loads((ROOT / "reference/raw-validation/config/expected_validation_config.json").read_text())
        self.assertEqual(set(spec["tables"]), set(config["tables"]))
        for table, cfg in spec["tables"].items():
            self.assertTrue(cfg["query"].startswith("SELECT "), table)
            for date in ("{week_start}", "{week_end}"):
                if cfg["date_column"]:
                    self.assertIn(date, cfg["query"])

    def test_no_terraform_auto_apply_in_ci(self):
        for file in (ROOT / ".github/workflows").rglob("*"):
            if file.is_file():
                self.assertNotIn("terraform apply", file.read_text())
        deploy = (ROOT / "cicd/buildspec-dag-deploy.yml").read_text()
        self.assertIn("ALLOW_PIPELINE_DEPLOY", deploy)
        self.assertNotIn("terraform apply", deploy)

if __name__ == "__main__":
    unittest.main()
