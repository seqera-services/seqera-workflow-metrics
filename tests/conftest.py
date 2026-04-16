"""Shared fixtures for tests."""
import pytest


@pytest.fixture
def sample_workflow_details():
    return {
        "workflow": {
            "id": "wf1",
            "runName": "test_run",
            "projectName": "nf-core/rnaseq",
            "repository": "https://github.com/nf-core/rnaseq",
            "status": "SUCCEEDED",
            "userName": "testuser",
            "start": "2025-01-15T10:00:00Z",
            "complete": "2025-01-15T11:00:00Z",
            "duration": 3_600_000,
            "errorReport": None,
            "stats": {"succeedCount": 2, "failedCount": 0, "cachedCount": 0, "ignoredCount": 0},
        },
        "orgName": "TestOrg",
        "workspaceName": "TestWS",
        "progress": {
            "workflowProgress": {"cpus": 0, "cpuTime": 0, "cpuEfficiency": 95.0, "readBytes": 1024, "writeBytes": 512},
            "processesProgress": [],
        },
    }


@pytest.fixture
def sample_tasks():
    return {
        "tasks": [
            {"task": {"name": "FASTQC", "status": "COMPLETED", "cpus": 4, "realtime": 1_800_000}},
            {"task": {"name": "TRIM", "status": "COMPLETED", "cpus": 2, "realtime": 3_600_000}},
        ]
    }


@pytest.fixture
def sample_tasks_with_failures():
    return {
        "tasks": [
            {"task": {"name": "FASTQC", "status": "COMPLETED", "cpus": 4, "realtime": 1_800_000}},
            {"task": {"name": "ALIGN", "status": "FAILED", "cpus": 8, "realtime": 7_200_000}},
        ]
    }


@pytest.fixture
def never_started_workflow_details():
    return {
        "workflow": {
            "id": "wf_never",
            "runName": "never_started",
            "projectName": "proj",
            "repository": "repo",
            "status": "FAILED",
            "userName": "user",
            "start": None,
            "complete": None,
            "stats": {},
        },
        "orgName": "org",
        "workspaceName": "ws",
    }
