import pytest
from seqera_workflow_metrics.metrics import (
    calculate_cpu_usage_from_tasks,
    parse_error_report,
    extract_workflow_metrics,
)
from seqera_workflow_metrics.config import RunConfig


class TestCalculateCpuUsage:
    def test_basic_calculation(self):
        tasks_data = {
            "tasks": [
                {
                    "task": {
                        "name": "FASTQC",
                        "status": "COMPLETED",
                        "cpus": 4,
                        "realtime": 3_600_000,
                        "start": "2025-01-15T10:00:00Z",
                        "complete": "2025-01-15T11:00:00Z",
                    }
                }
            ]
        }
        config = RunConfig()
        result = calculate_cpu_usage_from_tasks(tasks_data, "SUCCEEDED", config)
        assert result["calculated_cpu_hours"] == pytest.approx(4.0)
        assert result["non_cached_tasks"] == 1

    def test_cached_tasks_excluded(self):
        tasks_data = {
            "tasks": [
                {"task": {"name": "CACHED_TASK", "status": "CACHED", "cpus": 2, "realtime": 1000}},
                {"task": {"name": "REAL_TASK", "status": "COMPLETED", "cpus": 1, "realtime": 3_600_000}},
            ]
        }
        config = RunConfig()
        result = calculate_cpu_usage_from_tasks(tasks_data, "SUCCEEDED", config)
        assert result["non_cached_tasks"] == 1
        assert result["calculated_cpu_hours"] == pytest.approx(1.0)

    def test_exclude_failed_tasks(self):
        tasks_data = {
            "tasks": [
                {"task": {"name": "FAILED_TASK", "status": "FAILED", "cpus": 4, "realtime": 3_600_000}},
                {"task": {"name": "OK_TASK", "status": "COMPLETED", "cpus": 1, "realtime": 3_600_000}},
            ]
        }
        config = RunConfig(exclude_failed_tasks=True)
        result = calculate_cpu_usage_from_tasks(tasks_data, "SUCCEEDED", config)
        assert result["non_cached_tasks"] == 1
        assert result["calculated_cpu_hours"] == pytest.approx(1.0)

    def test_zero_cpus(self):
        tasks_data = {
            "tasks": [
                {"task": {"name": "EMPTY", "status": "COMPLETED", "cpus": 0, "realtime": 3_600_000}},
            ]
        }
        config = RunConfig()
        result = calculate_cpu_usage_from_tasks(tasks_data, "SUCCEEDED", config)
        assert result["calculated_cpu_hours"] == 0.0
        assert result["non_cached_tasks"] == 1

    def test_missing_timing_data_skipped(self):
        tasks_data = {
            "tasks": [
                {"task": {"name": "NO_TIME", "status": "COMPLETED", "cpus": 2, "realtime": 0}},
            ]
        }
        config = RunConfig()
        result = calculate_cpu_usage_from_tasks(tasks_data, "SUCCEEDED", config)
        assert result["non_cached_tasks"] == 0

    def test_start_complete_time_mode(self):
        tasks_data = {
            "tasks": [
                {
                    "task": {
                        "name": "TASK1",
                        "status": "COMPLETED",
                        "cpus": 2,
                        "realtime": 1_800_000,
                        "start": "2025-01-15T10:00:00Z",
                        "complete": "2025-01-15T11:00:00Z",
                    }
                }
            ]
        }
        config = RunConfig(use_start_complete_time=True)
        result = calculate_cpu_usage_from_tasks(tasks_data, "SUCCEEDED", config)
        assert result["calculated_cpu_hours"] == pytest.approx(2.0)

    def test_empty_tasks(self):
        config = RunConfig()
        result = calculate_cpu_usage_from_tasks({"tasks": []}, "SUCCEEDED", config)
        assert result["calculated_cpu_hours"] == 0.0
        assert result["non_cached_tasks"] == 0


class TestParseErrorReport:
    def test_standard_nextflow_error(self):
        report = (
            "Error executing process > 'FASTQC_RAW'\n\n"
            "Caused by:\n  Process died with exit code 137\n\n"
            "Command exit status:\n  137"
        )
        result = parse_error_report(report)
        assert result["failed_process"] == "FASTQC_RAW"
        assert "137" in result["error_cause"]
        assert result["exit_code"] == "137"

    def test_nonstandard_error(self):
        report = "Some compilation error that doesn't follow the pattern"
        result = parse_error_report(report)
        assert result["failed_process"] == ""
        assert result["error_cause"] == report
        assert result["exit_code"] == ""

    def test_empty_error(self):
        result = parse_error_report("")
        assert result == {"failed_process": "", "error_cause": "", "exit_code": ""}


class TestExtractWorkflowMetrics:
    def test_never_started_workflow_uses_error_cause(self):
        details = {
            "workflow": {
                "id": "wf1", "runName": "test", "projectName": "proj",
                "repository": "repo", "status": "FAILED", "userName": "user",
                "start": None, "complete": None, "stats": {},
            },
            "orgName": "org", "workspaceName": "ws",
        }
        config = RunConfig()
        result = extract_workflow_metrics(details, config=config)
        assert "note" not in result
        assert "never started" in result["error_cause"].lower()
        assert result["calculated_cpu_hours"] == 0

    def test_normal_workflow_with_tasks(self):
        details = {
            "workflow": {
                "id": "wf1", "runName": "test", "projectName": "proj",
                "repository": "repo", "status": "SUCCEEDED", "userName": "user",
                "start": "2025-01-15T10:00:00Z", "complete": "2025-01-15T11:00:00Z",
                "duration": 3_600_000,
                "stats": {"succeedCount": 1, "failedCount": 0, "cachedCount": 0, "ignoredCount": 0},
            },
            "orgName": "org", "workspaceName": "ws",
            "progress": {
                "workflowProgress": {"cpus": 0, "cpuTime": 0, "cpuEfficiency": 0, "readBytes": 0, "writeBytes": 0},
                "processesProgress": [],
            },
        }
        tasks = {"tasks": [{"task": {"name": "T1", "status": "COMPLETED", "cpus": 2, "realtime": 3_600_000}}]}
        config = RunConfig()
        result = extract_workflow_metrics(details, tasks, config=config)
        assert result["calculated_cpu_hours"] == pytest.approx(2.0)
        assert result["workflow_id"] == "wf1"
