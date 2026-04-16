"""Integration test: full pipeline from mock data to schema-validated output."""
import pytest
from seqera_workflow_metrics.config import RunConfig
from seqera_workflow_metrics.metrics import extract_workflow_metrics
from seqera_workflow_metrics.schema import SCHEMA_COLUMNS


def test_output_matches_schema_columns(sample_workflow_details, sample_tasks):
    """extract_workflow_metrics output has exactly the columns in SCHEMA_COLUMNS."""
    config = RunConfig()
    result = extract_workflow_metrics(sample_workflow_details, sample_tasks, config=config)
    assert set(result.keys()) == set(SCHEMA_COLUMNS)


def test_output_matches_schema_never_started(never_started_workflow_details):
    """Never-started workflow output also matches SCHEMA_COLUMNS (no extra 'note' field)."""
    config = RunConfig()
    result = extract_workflow_metrics(never_started_workflow_details, config=config)
    assert set(result.keys()) == set(SCHEMA_COLUMNS)
    assert "note" not in result


def test_config_flags_affect_output(sample_workflow_details, sample_tasks_with_failures):
    """RunConfig flags are threaded through and affect calculations."""
    config_include = RunConfig(exclude_failed_tasks=False)
    config_exclude = RunConfig(exclude_failed_tasks=True)

    result_include = extract_workflow_metrics(sample_workflow_details, sample_tasks_with_failures, config=config_include)
    result_exclude = extract_workflow_metrics(sample_workflow_details, sample_tasks_with_failures, config=config_exclude)

    assert result_exclude["calculated_cpu_hours"] < result_include["calculated_cpu_hours"]
