"""End-to-end: raw API dicts → schema-valid output rows."""

from seqera_workflow_metrics.studios.metrics import extract_studio_session_metrics
from seqera_workflow_metrics.studios.models import CheckpointRecord, StudioRecord
from seqera_workflow_metrics.studios.schema import STUDIOS_SCHEMA_COLUMNS


def test_full_pipeline_output_matches_schema():
    studio = StudioRecord.model_validate({
        "sessionId": "abc", "name": "lab",
        "user": {"userName": "bob"},
        "configuration": {"cpu": 8, "gpu": 0, "memory": 0},
        "computeEnv": {"id": "ce-99"},
        "statusInfo": {"status": "stopped"},
        "dateCreated": "2026-08-01T09:00:00Z",
    })
    cp = CheckpointRecord.model_validate({
        "id": 10, "dateCreated": "2026-08-01T10:00:00Z",
        "dateSaved": "2026-08-01T14:00:00Z", "status": "finalized",
    })
    rows = extract_studio_session_metrics(studio, [cp], org_name="Org", workspace_name="WS")
    assert len(rows) == 1
    assert set(rows[0].keys()) == set(STUDIOS_SCHEMA_COLUMNS)
    assert rows[0]["cpu_hours"] == 32.0   # 4h × 8 cpus
    assert rows[0]["month"] == "2026-08"
    assert not rows[0]["cpu_unresolved"]


def test_cpu_unresolved_full_pipeline():
    studio = StudioRecord.model_validate({
        "sessionId": "xyz", "name": "lab2",
        "user": {"userName": "carol"},
        "configuration": {"cpu": 0, "gpu": 0, "memory": 0},
        "computeEnv": {"id": "ce-1"},
        "statusInfo": {"status": "stopped"},
        "dateCreated": "2026-08-01T09:00:00Z",
    })
    cp = CheckpointRecord.model_validate({
        "id": 11, "dateCreated": "2026-08-01T10:00:00Z",
        "dateSaved": "2026-08-01T11:00:00Z", "status": "finalized",
    })
    rows = extract_studio_session_metrics(studio, [cp], org_name="Org", workspace_name="WS")
    assert rows[0]["cpu_hours"] == 0.0
    assert rows[0]["runtime_hours"] == 1.0
    assert rows[0]["cpu_unresolved"]
