"""
DAG Validation Tests
=====================
Parametrized tests for all 5 MR. HEALTH Airflow DAGs.
Validates: import, existence, schedule, tags, cycles, catchup, owner.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("airflow.models", reason="Airflow not available (requires Python 3.11)")
from airflow.models import DagBag  # noqa: E402

_root = Path(__file__).resolve().parent.parent.parent
os.environ.setdefault("MRHEALTH_CONFIG_PATH", str(_root / "config" / "project_config.yaml"))
os.environ.setdefault("MRHEALTH_SQL_PATH", str(_root / "sql"))
os.environ.setdefault("GCP_PROJECT_ID", "test-project-id")
os.environ.setdefault("GCS_BUCKET_NAME", "test-bucket")

EXPECTED_DAGS = {
    "mrhealth_daily_pipeline": {"schedule": "0 2 * * *"},
    "mrhealth_data_quality": {"schedule": "0 3 * * *"},
    "mrhealth_data_retention": {"schedule": "0 4 * * 0"},
    "mrhealth_reference_refresh": {"schedule": "0 1 * * *"},
    "mrhealth_backfill_monitor": {"schedule": "0 6 * * 1"},
}


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder=str(_root / "dags"), include_examples=False)


def test_no_import_errors(dagbag):
    assert dagbag.import_errors == {}, f"DAG import errors: {dagbag.import_errors}"


@pytest.mark.parametrize("dag_id", EXPECTED_DAGS.keys())
def test_dag_exists(dagbag, dag_id):
    assert dagbag.get_dag(dag_id) is not None, f"DAG {dag_id} not found"


@pytest.mark.parametrize("dag_id,expected", EXPECTED_DAGS.items())
def test_dag_schedule(dagbag, dag_id, expected):
    dag = dagbag.get_dag(dag_id)
    assert dag.schedule_interval == expected["schedule"]


@pytest.mark.parametrize("dag_id", EXPECTED_DAGS.keys())
def test_dag_no_cycles(dagbag, dag_id):
    dag = dagbag.get_dag(dag_id)
    dag.topological_sort()


@pytest.mark.parametrize("dag_id", EXPECTED_DAGS.keys())
def test_dag_has_mrhealth_tag(dagbag, dag_id):
    dag = dagbag.get_dag(dag_id)
    assert "mrhealth" in dag.tags, f"DAG {dag_id} missing 'mrhealth' tag"


@pytest.mark.parametrize("dag_id", EXPECTED_DAGS.keys())
def test_dag_catchup_disabled(dagbag, dag_id):
    dag = dagbag.get_dag(dag_id)
    assert dag.catchup is False, f"DAG {dag_id} has catchup enabled"


@pytest.mark.parametrize("dag_id", EXPECTED_DAGS.keys())
def test_dag_owner(dagbag, dag_id):
    dag = dagbag.get_dag(dag_id)
    assert dag.default_args["owner"] == "mrhealth-data-team"
