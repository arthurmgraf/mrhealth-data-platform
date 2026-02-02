"""
DAG Integrity Tests for mrhealth_daily_pipeline
================================================

Validates DAG structure, task count, dependencies, and configuration
without requiring a running Airflow instance or GCP credentials.

Usage:
    pytest tests/unit/test_dag_integrity.py -v

Requires:
    pip install apache-airflow apache-airflow-providers-google pyyaml
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Point config/sql paths to the project root before importing the DAG
_project_root = Path(__file__).resolve().parent.parent.parent
os.environ.setdefault("MRHEALTH_CONFIG_PATH", str(_project_root / "config" / "project_config.yaml"))
os.environ.setdefault("MRHEALTH_SQL_PATH", str(_project_root / "sql"))

from airflow.models import DagBag


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder=str(_project_root / "dags"), include_examples=False)


@pytest.fixture(scope="module")
def dag(dagbag):
    return dagbag.get_dag("mrhealth_daily_pipeline")


def test_dag_import(dagbag):
    assert dagbag.import_errors == {}, f"DAG import errors: {dagbag.import_errors}"


def test_dag_has_correct_id(dag):
    assert dag is not None
    assert dag.dag_id == "mrhealth_daily_pipeline"


def test_dag_has_correct_tasks(dag):
    expected = {
        "sense_new_files",
        "validate_bronze",
        "build_silver",
        "build_gold_dimensions",
        "build_gold_facts",
        "build_aggregations",
        "validate_gold",
        "notify_completion",
    }
    assert set(dag.task_ids) == expected


def test_dag_task_count(dag):
    assert len(dag.tasks) == 8


def test_dag_dependencies_silver_fans_out(dag):
    silver = dag.get_task("build_silver")
    downstream_ids = {t.task_id for t in silver.downstream_list}
    assert downstream_ids == {"build_gold_dimensions", "build_gold_facts"}


def test_dag_dependencies_aggs_fans_in(dag):
    aggs = dag.get_task("build_aggregations")
    upstream_ids = {t.task_id for t in aggs.upstream_list}
    assert upstream_ids == {"build_gold_dimensions", "build_gold_facts"}


def test_dag_linear_chain_sense_to_silver(dag):
    sense = dag.get_task("sense_new_files")
    assert {t.task_id for t in sense.downstream_list} == {"validate_bronze"}

    validate = dag.get_task("validate_bronze")
    assert {t.task_id for t in validate.downstream_list} == {"build_silver"}


def test_dag_linear_chain_aggs_to_notify(dag):
    aggs = dag.get_task("build_aggregations")
    assert {t.task_id for t in aggs.downstream_list} == {"validate_gold"}

    validate = dag.get_task("validate_gold")
    assert {t.task_id for t in validate.downstream_list} == {"notify_completion"}


def test_dag_no_cycles(dag):
    from airflow.exceptions import AirflowDagCycleException
    try:
        dag.test_cycle()
    except AirflowDagCycleException:
        pytest.fail("DAG has a cycle")


def test_dag_default_args(dag):
    assert dag.default_args["retries"] == 2
    assert dag.default_args["email_on_failure"] is True
    assert dag.default_args["owner"] == "mrhealth-data-team"


def test_dag_tags(dag):
    assert "mrhealth" in dag.tags
    assert "pipeline" in dag.tags
    assert "medallion" in dag.tags


def test_dag_schedule(dag):
    assert dag.schedule_interval == "0 2 * * *"


def test_dag_catchup_disabled(dag):
    assert dag.catchup is False


def test_notify_trigger_rule(dag):
    notify = dag.get_task("notify_completion")
    assert notify.trigger_rule == "all_done"


def test_sensor_soft_fail(dag):
    sensor = dag.get_task("sense_new_files")
    assert sensor.soft_fail is True
