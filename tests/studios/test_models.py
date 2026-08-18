import pytest
from pydantic import ValidationError

from seqera_workflow_metrics.studios.models import CheckpointRecord, StudioRecord


class TestStudioRecord:
    def test_parses_full_record(self):
        raw = {
            "sessionId": "abc123",
            "name": "my-studio",
            "user": {"userName": "alice"},
            "configuration": {"cpu": 4, "gpu": 0, "memory": 8192},
            "computeEnv": {"id": "ce-1"},
            "statusInfo": {"status": "stopped"},
            "dateCreated": "2026-08-01T10:00:00Z",
        }
        s = StudioRecord.model_validate(raw)
        assert s.session_id == "abc123"
        assert s.user_name == "alice"
        assert s.cpu == 4
        assert not s.cpu_unresolved

    def test_cpu_zero_sets_unresolved(self):
        raw = {
            "sessionId": "abc123",
            "name": "my-studio",
            "user": {"userName": "alice"},
            "configuration": {"cpu": 0, "gpu": 0, "memory": 0},
            "computeEnv": {"id": "ce-1"},
            "statusInfo": {"status": "stopped"},
            "dateCreated": "2026-08-01T10:00:00Z",
        }
        s = StudioRecord.model_validate(raw)
        assert s.cpu == 0
        assert s.cpu_unresolved

    def test_missing_user_name_defaults_to_unknown(self):
        raw = {
            "sessionId": "abc123",
            "name": "my-studio",
            "user": {},
            "configuration": {"cpu": 2, "gpu": 0, "memory": 0},
            "computeEnv": {"id": "ce-1"},
            "statusInfo": {"status": "stopped"},
            "dateCreated": "2026-08-01T10:00:00Z",
        }
        s = StudioRecord.model_validate(raw)
        assert s.user_name == "unknown"


class TestCheckpointRecord:
    def test_parses_complete_checkpoint(self):
        raw = {
            "id": 42,
            "dateCreated": "2026-08-01T10:00:00Z",
            "dateSaved": "2026-08-01T12:00:00Z",
            "status": "finalized",
        }
        cp = CheckpointRecord.model_validate(raw)
        assert cp.checkpoint_id == 42
        assert cp.runtime_hours == pytest.approx(2.0)
        assert cp.is_complete

    def test_missing_date_saved_is_incomplete(self):
        raw = {
            "id": 99,
            "dateCreated": "2026-08-01T10:00:00Z",
            "dateSaved": None,
            "status": "active",
        }
        cp = CheckpointRecord.model_validate(raw)
        assert not cp.is_complete
        assert cp.runtime_hours is None
